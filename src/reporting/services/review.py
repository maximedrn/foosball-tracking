"""Overlay JSON positions on source frames for visual review."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from cv2 import (
    FONT_HERSHEY_SIMPLEX,
    LINE_AA,
    VideoCapture,
    VideoWriter,
    circle,
    imwrite,
    putText,
    rectangle,
    resize,
)
from cv2.typing import MatLike
from numpy import full, uint8

from reporting.models.positions import ComparisonStatus
from reporting.paths import PROJECT_ROOT
from reporting.services.inputs import index_frames
from reporting.services.positions import classify_position
from reporting.utils.messages import (
    EXAMPLE_ABSENT,
    EXAMPLE_CORRECT,
    EXAMPLE_ERROR_TEMPLATE,
    EXAMPLE_FALSE_POSITIVE,
    EXAMPLE_MISSED,
    EXAMPLE_UNCERTAIN,
    EXAMPLE_WRONG,
    REFERENCE_CENTER_TEMPLATE,
    REFERENCE_NOT_SAMPLED,
    REFERENCE_NOT_VISIBLE,
    REFERENCE_UNCERTAIN,
    REVIEW_DETAIL_TEMPLATE,
    REVIEW_FRAME_TEMPLATE,
    REVIEW_LEGEND,
)
from tracking.models import Image
from tracking.models.export import DetectionExport, FrameExport


def add_position_markers(
    image: Image,
    reference: FrameExport | None,
    automatic: FrameExport | None,
) -> Image:
    """Overlay only available reference and automatic centers.

    :param image: Raw source frame, left unchanged.
    :type image: Image
    :param reference: Sampled visual reference, or None on unsampled frames.
    :type reference: FrameExport | None
    :param automatic: Automatic result to overlay, or None for reference only.
    :type automatic: FrameExport | None
    :return: Copy with green reference and orange automatic markers.
    :rtype: Image
    """
    result: Image = image.copy()
    if reference is not None and reference.ball is not None:
        circle(result, reference.ball.center, 22, (40, 220, 40), 3, LINE_AA)
        circle(result, reference.ball.center, 3, (40, 220, 40), -1, LINE_AA)
    if automatic is not None and automatic.ball is not None:
        circle(result, automatic.ball.center, 28, (0, 140, 255), 3, LINE_AA)
        circle(result, automatic.ball.center, 3, (0, 140, 255), -1, LINE_AA)
    return result


def header(image: Image, title: str, detail: str) -> Image:
    """Add a readable caption without changing image coordinates.

    :param image: Source-sized image to caption.
    :type image: Image
    :param title: Main caption describing the frame or experiment.
    :type title: str
    :param detail: Visibility, coordinates or localization error.
    :type detail: str
    :return: Captioned copy of the image.
    :rtype: Image
    """
    result: Image = image.copy()
    rectangle(result, (0, 0), (image.shape[1], 88), (250, 250, 250), -1)
    putText(
        result, title, (12, 32), FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2
    )
    putText(
        result, detail, (12, 67), FONT_HERSHEY_SIMPLEX, 0.58, (20, 20, 20), 1
    )
    return result


def reference_caption(
    reference: FrameExport | None, *, not_visible: bool = False
) -> str:
    """Describe reference availability without interpolating missing labels.

    :param reference: Reference for this exact frame, if sampled.
    :type reference: FrameExport | None
    :param not_visible: Whether review confirms no discernible target ball.
    :type not_visible: bool
    :return: Original source coordinates or the reason no center is drawn.
    :rtype: str
    """
    if reference is None:
        return REFERENCE_NOT_SAMPLED
    if reference.ball is None:
        if not_visible:
            return REFERENCE_NOT_VISIBLE
        return REFERENCE_UNCERTAIN
    return REFERENCE_CENTER_TEMPLATE.format(center=reference.ball.center)


def example_caption(
    reference: FrameExport,
    automatic: FrameExport,
    *,
    not_visible: bool = False,
) -> str:
    """Describe an example without assigning an error to an unknown center.

    :param reference: Reference for the example's exact source frame.
    :type reference: FrameExport
    :param automatic: Result produced by the selected experiment.
    :type automatic: FrameExport
    :param not_visible: Whether no target ball is discernible in the frame.
    :type not_visible: bool
    :return: Source frame index and measured error or availability status.
    :rtype: str
    """
    status: ComparisonStatus
    error: float | None
    status, error = classify_position(
        reference.ball.center if reference.ball is not None else None,
        automatic.ball.center if automatic.ball is not None else None,
        uncertain=reference.ball is None and not not_visible,
        threshold_px=20.0,
    )
    labels: dict[ComparisonStatus, str] = {
        ComparisonStatus.CORRECT: EXAMPLE_CORRECT,
        ComparisonStatus.WRONG: EXAMPLE_WRONG,
        ComparisonStatus.MISSED: EXAMPLE_MISSED,
        ComparisonStatus.UNCERTAIN: EXAMPLE_UNCERTAIN,
        ComparisonStatus.FALSE_POSITIVE: EXAMPLE_FALSE_POSITIVE,
        ComparisonStatus.ABSENT: EXAMPLE_ABSENT,
    }
    return (
        EXAMPLE_ERROR_TEMPLATE.format(caption=labels[status], error=error)
        if error is not None
        else labels[status]
    )


def render_review(
    reference: DetectionExport,
    automatic: DetectionExport,
    not_visible: set[int],
    *,
    output_dir: Path,
) -> None:
    """Write review sheets and videos aligned by original frame index.

    :param reference: Visual reference export at original frame indices.
    :type reference: DetectionExport
    :param automatic: Complete automatic export for the source video.
    :type automatic: DetectionExport
    :param not_visible: Frames with no discernible target after visual review.
    :type not_visible: set[int]
    :param output_dir: Destination for review videos and contact sheets.
    :type output_dir: Path
    :return: None.
    :rtype: None
    :raises RuntimeError: If a source frame or output writer is unavailable.
    """
    lookup: dict[int, FrameExport] = index_frames(reference)
    capture: VideoCapture = VideoCapture(
        str(PROJECT_ROOT / reference.source_video)
    )
    reference_writer: VideoWriter = VideoWriter(
        str(output_dir / "video.reference.mp4"),
        VideoWriter.fourcc(*"mp4v"),
        reference.metadata.fps,
        (reference.metadata.width, reference.metadata.height),
    )
    comparison_writer: VideoWriter = VideoWriter(
        str(output_dir / "video.comparison.mp4"),
        VideoWriter.fourcc(*"mp4v"),
        reference.metadata.fps,
        (reference.metadata.width, reference.metadata.height),
    )
    if not reference_writer.isOpened() or not comparison_writer.isOpened():
        raise RuntimeError("Unable to create review videos")
    panels: list[Image] = []
    frame: FrameExport
    try:
        for frame in automatic.frames:
            success: bool
            decoded_frame: MatLike
            success, decoded_frame = capture.read()
            if not success:
                raise RuntimeError(f"Missing source frame {frame.frame_index}")
            sample: FrameExport | None = lookup.get(frame.frame_index)
            caption: str = reference_caption(
                sample, not_visible=frame.frame_index in not_visible
            )
            marked: Image = add_position_markers(
                cast(Image, decoded_frame), sample, None
            )
            reference_writer.write(
                header(
                    marked,
                    REVIEW_FRAME_TEMPLATE.format(index=frame.frame_index),
                    caption,
                )
            )
            comparison_writer.write(
                header(
                    add_position_markers(
                        cast(Image, decoded_frame), sample, frame
                    ),
                    REVIEW_LEGEND,
                    REVIEW_DETAIL_TEMPLATE.format(
                        index=frame.frame_index, caption=caption
                    ),
                )
            )
            if sample is not None:
                panels.append(
                    cast(
                        Image,
                        resize(
                            header(
                                marked,
                                REVIEW_FRAME_TEMPLATE.format(
                                    index=frame.frame_index
                                ),
                                caption,
                            ),
                            (449, 661),
                        ),
                    )
                )
    finally:
        capture.release()
        reference_writer.release()
        comparison_writer.release()
    write_sheets(panels, output_dir / "review")


def write_sheets(panels: list[Image], output_dir: Path) -> None:
    """Arrange reference-only frames in numbered contact sheets.

    :param panels: Captioned source images at half resolution.
    :type panels: list[Image]
    :param output_dir: Directory receiving numbered review sheets.
    :type output_dir: Path
    :return: None.
    :rtype: None
    :raises OSError: If a review sheet cannot be saved.
    """
    page: int
    for page in range((len(panels) + 9) // 10):
        sheet: Image = full((1322, 2245, 3), 255, dtype=uint8)
        cell: int
        panel: Image
        for cell, panel in enumerate(panels[page * 10 : (page + 1) * 10]):
            row: int
            column: int
            row, column = divmod(cell, 5)
            sheet[
                row * 661 : (row + 1) * 661,
                column * 449 : (column + 1) * 449,
            ] = panel
        destination: Path = output_dir / f"reference-review-{page + 1:02}.jpg"
        if not imwrite(str(destination), sheet, [1, 90]):
            raise OSError(f"Unable to save {destination}")
