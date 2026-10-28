"""Summarize observed and predicted positions from validated exports."""

from pathlib import Path

from reporting.models.coverage import VideoStatistics
from reporting.models.plotting import ChartLayout
from reporting.utils.messages import ALL_VIDEOS
from tracking.models.export import (
    DetectionExport,
    DetectionStatus,
    FrameExport,
    SummaryExport,
)


def percentage(value: int, total: int) -> float:
    """Calculate a percentage using an explicit denominator.

    :param value: Number of frames in the selected category.
    :type value: int
    :param total: Nonzero total number of frames.
    :type total: int
    :return: Percentage of frames in the selected category.
    :rtype: float
    """
    return value / total * 100.0


def observation_rates(
    observations: list[int], totals: list[int]
) -> tuple[float, ...]:
    """Calculate the visual-detection percentage in each time segment.

    :param observations: Visual detections counted per segment.
    :type observations: list[int]
    :param totals: Total processed frames counted per segment.
    :type totals: list[int]
    :return: Segment percentages, with zero for empty segments.
    :rtype: tuple[float, ...]
    :raises ValueError: If the input lists have different lengths.
    """
    rates: list[float] = []
    for count, total in zip(observations, totals, strict=True):
        rates.append(percentage(count, total) if total else 0.0)
    return tuple(rates)


def load_statistics(path: Path, *, layout: ChartLayout) -> VideoStatistics:
    """Validate JSON with the existing Pydantic export model.

    :param path: Detection export to validate and summarize.
    :type path: Path
    :param layout: Sampling resolution used for the observation timeline.
    :type layout: ChartLayout
    :return: Per-video frame counts and visual-detection percentages.
    :rtype: VideoStatistics
    :raises OSError: If the export cannot be read.
    :raises ValueError: If the export is invalid, empty, or inconsistent.
    """
    report: DetectionExport = DetectionExport.model_validate_json(
        path.read_bytes()
    )
    frames: list[FrameExport] = report.frames
    frame_count: int = len(frames)

    if not frame_count:
        raise ValueError(f"No processed frames in {path}")

    detected: int = 0
    estimated: int = 0
    totals: list[int] = [0] * layout.window_count
    observations: list[int] = [0] * layout.window_count

    for index, frame in enumerate(frames):
        window_index: int = min(
            index * layout.window_count // frame_count,
            layout.window_count - 1,
        )
        totals[window_index] += 1

        if frame.status is DetectionStatus.DETECTED:
            detected += 1
            observations[window_index] += 1
        elif frame.status is DetectionStatus.ESTIMATED:
            estimated += 1

    missing: int = frame_count - detected - estimated
    summary: SummaryExport = report.summary
    if (
        summary.processed_frames != frame_count
        or summary.detected_frames != detected
        or summary.predicted_frames != estimated
    ):
        raise ValueError(f"Frame counts and export summary disagree: {path}")

    return VideoStatistics(
        name=report.source_video.stem,
        frames=frame_count,
        detected=detected,
        estimated=estimated,
        missing=missing,
        observed_windows=observation_rates(observations, totals),
    )


def aggregate_statistics(videos: list[VideoStatistics]) -> VideoStatistics:
    """Aggregate frame counts instead of averaging video percentages.

    :param videos: Per-video statistics to combine.
    :type videos: list[VideoStatistics]
    :return: Combined counts without a cross-video observation timeline.
    :rtype: VideoStatistics
    """
    frames: int = 0
    detected: int = 0
    estimated: int = 0
    missing: int = 0
    for video in videos:
        frames += video.frames
        detected += video.detected
        estimated += video.estimated
        missing += video.missing

    return VideoStatistics(
        name=ALL_VIDEOS,
        frames=frames,
        detected=detected,
        estimated=estimated,
        missing=missing,
        observed_windows=(),
    )
