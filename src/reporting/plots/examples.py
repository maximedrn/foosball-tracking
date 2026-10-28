"""Render legible example panels from source images and saved positions."""

from pathlib import Path
from typing import Final, cast

from cv2 import CAP_PROP_POS_FRAMES, COLOR_BGR2RGB, VideoCapture, cvtColor
from cv2.typing import MatLike
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from reporting.models.plotting import GitHubColor, PlotAxis, PlotFigure
from reporting.paths import PROJECT_ROOT, THEME_STYLESHEET
from reporting.services.inputs import index_frames
from reporting.services.review import (
    add_position_markers,
    example_caption,
)
from reporting.utils.messages import (
    EXAMPLE_FRAME_TEMPLATE,
    EXAMPLES_FOOTNOTE,
    EXAMPLES_LEGEND,
)
from reporting.utils.svg import embed_adaptive_theme
from reporting.utils.theme import configure_plot_theme
from tracking.models import Image
from tracking.models.export import DetectionExport, FrameExport

EXAMPLE_FRAMES: Final[tuple[int, ...]] = (0, 79, 432, 410)


def add_example_panel(
    axis: Axes,
    image: Image,
    reference: FrameExport,
    automatic: FrameExport,
    *,
    not_visible: bool,
) -> None:
    """Add a source crop with full-size captions outside the image.

    :param axis: Subplot receiving the frame and its caption.
    :type axis: Axes
    :param image: Original source frame.
    :type image: Image
    :param reference: Annotation at this source index.
    :type reference: FrameExport
    :param automatic: Code output at the same index.
    :type automatic: FrameExport
    :param not_visible: Whether the target is not visible in this frame.
    :type not_visible: bool
    :return: None.
    :rtype: None
    """
    marked: Image = add_position_markers(image, reference, automatic)
    crop: Image = marked[
        round(image.shape[0] * 0.13) : round(image.shape[0] * 0.78)
    ]
    rgb: Image = cast(Image, cvtColor(crop, COLOR_BGR2RGB))
    cast(PlotAxis, axis).imshow(rgb, interpolation="nearest")
    axis.set_axis_off()
    axis.title.set_text(
        EXAMPLE_FRAME_TEMPLATE.format(
            index=reference.frame_index,
            seconds=reference.timestamp_seconds,
            caption=example_caption(
                reference, automatic, not_visible=not_visible
            ),
        )
    )
    axis.title.set_fontsize(12)
    axis.title.set_linespacing(1.5)


def render_examples(
    reference: DetectionExport,
    automatic: DetectionExport,
    not_visible: set[int],
    *,
    destination: Path,
) -> None:
    """Show correct, missed, false-positive and absent-ball examples.

    :param reference: Annotation export in source-image coordinates.
    :type reference: DetectionExport
    :param automatic: Saved code observations.
    :type automatic: DetectionExport
    :param not_visible: Reviewed frames without a visible target.
    :type not_visible: set[int]
    :param destination: Adaptive SVG destination for the example figure.
    :type destination: Path
    :return: None.
    :rtype: None
    :raises RuntimeError: If a selected source frame cannot be decoded.
    """
    annotations: dict[int, FrameExport] = index_frames(reference)
    detections: dict[int, FrameExport] = index_frames(automatic)
    capture: VideoCapture = VideoCapture(
        str(PROJECT_ROOT / reference.source_video)
    )
    configure_plot_theme()
    figure: Figure = Figure(figsize=(10, 11.2), facecolor=GitHubColor.CANVAS)
    figure.subplots_adjust(
        left=0.02,
        right=0.98,
        bottom=0.085,
        top=0.93,
        hspace=0.26,
        wspace=0.08,
    )
    number: int
    index: int
    try:
        for number, index in enumerate(EXAMPLE_FRAMES, start=1):
            capture.set(CAP_PROP_POS_FRAMES, index)
            success: bool
            decoded: MatLike
            success, decoded = capture.read()
            if not success:
                raise RuntimeError(f"Unable to decode frame {index}")
            add_example_panel(
                figure.add_subplot(2, 2, number),
                cast(Image, decoded),
                annotations[index],
                detections[index],
                not_visible=index in not_visible,
            )
    finally:
        capture.release()
    plot: PlotFigure = cast(PlotFigure, figure)
    plot.text(
        0.5,
        0.975,
        EXAMPLES_LEGEND,
        ha="center",
        fontsize=13,
    )
    plot.text(
        0.5,
        0.025,
        EXAMPLES_FOOTNOTE,
        ha="center",
        fontsize=11,
        color=GitHubColor.MUTED,
    )
    plot.savefig(destination, format="svg", dpi=160)
    embed_adaptive_theme(destination, THEME_STYLESHEET)
