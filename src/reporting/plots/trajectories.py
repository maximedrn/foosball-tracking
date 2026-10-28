"""Show every observation alongside its reference-conditioned error."""

from collections import Counter
from pathlib import Path
from typing import cast

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.lines import Line2D

from reporting.models.plotting import (
    GitHubColor,
    ObservationStyle,
    PlotAxis,
    PlotFigure,
)
from reporting.models.positions import ComparisonStatus, PositionComparison
from reporting.models.provenance import ReferenceProvenance
from reporting.paths import THEME_STYLESHEET
from reporting.services.positions import compare_frames
from reporting.utils.messages import (
    ANNOTATIONS_LABEL,
    COMPARISON_SUMMARY_TEMPLATE,
    COMPARISON_TITLE,
    CORRECT_OBSERVATIONS_LABEL,
    ERROR_CRITERION_TEMPLATE,
    ERROR_DISTANCE_LABEL,
    ERROR_FOOTNOTE_TEMPLATE,
    ERROR_TIME_LABEL,
    ERROR_TITLE,
    NEGATIVE_SUMMARY_TEMPLATE,
    NO_NEGATIVE_FRAMES,
    NO_READABLE_CENTERS,
    OBSERVATION_COUNT_TEMPLATE,
    OBSERVATIONS_FOOTNOTE_TEMPLATE,
    POSITION_X_LABEL,
    POSITION_Y_LABEL,
    POSITIONS_TITLE,
    READABLE_SUMMARY_TEMPLATE,
    UNSCORED_OBSERVATIONS_LABEL,
    WRONG_OBSERVATIONS_LABEL,
)
from reporting.utils.svg import embed_adaptive_theme
from reporting.utils.theme import configure_plot_theme
from tracking.models import Point
from tracking.models.export import DetectionExport, MetadataExport


def plot_observations(
    axis: Axes,
    frames: list[PositionComparison],
    statuses: tuple[ComparisonStatus, ...],
    style: ObservationStyle,
) -> Line2D:
    """Show one observation category as points, including every outlier.

    :param axis: Source-coordinate plot receiving the points.
    :type axis: Axes
    :param frames: Aligned positions with explicit scoring outcomes.
    :type frames: list[PositionComparison]
    :param statuses: Outcomes included in this visual category.
    :type statuses: tuple[ComparisonStatus, ...]
    :param style: Legend, color and marker settings for the category.
    :type style: ObservationStyle
    :return: Artist used in the legend.
    :rtype: Line2D
    """
    points: list[Point] = [
        frame.observation
        for frame in frames
        if frame.status in statuses and frame.observation is not None
    ]
    return cast(PlotAxis, axis).plot(
        [point[0] for point in points],
        [point[1] for point in points],
        style.marker,
        linestyle="none",
        color=style.color,
        markersize=5 if style.marker == "x" else 3.5,
        markeredgewidth=0.8,
        markerfacecolor="none",
        label=OBSERVATION_COUNT_TEMPLATE.format(
            label=style.label, count=len(points)
        ),
    )[0]


def draw_positions(
    axis: Axes, frames: list[PositionComparison], metadata: MetadataExport
) -> None:
    """Overlay all observations while keeping unknown references distinct.

    :param axis: Axis receiving positions in original image pixels.
    :type axis: Axes
    :param frames: Aligned annotation and observation records.
    :type frames: list[PositionComparison]
    :param metadata: Source image dimensions.
    :type metadata: MetadataExport
    :return: None.
    :rtype: None
    """
    reference_x: list[float] = [
        frame.annotation[0] if frame.annotation is not None else float("nan")
        for frame in frames
    ]
    reference_y: list[float] = [
        frame.annotation[1] if frame.annotation is not None else float("nan")
        for frame in frames
    ]
    annotation: Line2D = cast(PlotAxis, axis).plot(
        reference_x,
        reference_y,
        color=GitHubColor.GREEN,
        linewidth=1.2,
        label=ANNOTATIONS_LABEL,
    )[0]
    correct: Line2D = plot_observations(
        axis,
        frames,
        (ComparisonStatus.CORRECT,),
        ObservationStyle(CORRECT_OBSERVATIONS_LABEL, GitHubColor.ORANGE, "o"),
    )
    wrong: Line2D = plot_observations(
        axis,
        frames,
        (ComparisonStatus.WRONG, ComparisonStatus.FALSE_POSITIVE),
        ObservationStyle(WRONG_OBSERVATIONS_LABEL, GitHubColor.RED, "x"),
    )
    uncertain: Line2D = plot_observations(
        axis,
        frames,
        (ComparisonStatus.UNCERTAIN,),
        ObservationStyle(UNSCORED_OBSERVATIONS_LABEL, GitHubColor.MUTED, "+"),
    )
    handles: list[Line2D] = [annotation, correct, wrong, uncertain]
    axis.add_artist(
        Legend(
            axis,
            handles,
            [str(line.get_label()) for line in handles],
            loc="lower right",
            fontsize=8,
        )
    )
    axis.set_xlim(0, metadata.width)
    axis.set_ylim(metadata.height, 0)
    axis.set_aspect("equal")
    axis.title.set_text(POSITIONS_TITLE)
    axis.title.set_fontsize(12)
    axis.xaxis.label.set_text(POSITION_X_LABEL)
    axis.yaxis.label.set_text(POSITION_Y_LABEL)


def draw_errors(
    axis: Axes,
    frames: list[PositionComparison],
    *,
    fps: float,
    threshold_px: float,
) -> None:
    """Display all measurable errors and shade unavailable reference centers.

    :param axis: Axis receiving the time-dependent error plot.
    :type axis: Axes
    :param frames: Aligned records retaining unavailable errors as None.
    :type frames: list[PositionComparison]
    :param fps: Source frame rate defining shaded frame intervals.
    :type fps: float
    :param threshold_px: Displayed scoring threshold.
    :type threshold_px: float
    :return: None.
    :rtype: None
    """
    plot: PlotAxis = cast(PlotAxis, axis)
    frame: PositionComparison
    for frame in frames:
        if frame.annotation is None:
            plot.axvspan(
                frame.timestamp_seconds,
                frame.timestamp_seconds + 1 / fps,
                color=GitHubColor.MUTED,
                alpha=0.12,
                linewidth=0,
            )
    plot.plot(
        [frame.timestamp_seconds for frame in frames],
        [
            frame.error_px if frame.error_px is not None else float("nan")
            for frame in frames
        ],
        "o",
        color=GitHubColor.ORANGE,
        markersize=3,
    )
    wrong: list[PositionComparison] = [
        frame for frame in frames if frame.status is ComparisonStatus.WRONG
    ]
    plot.plot(
        [frame.timestamp_seconds for frame in wrong],
        [
            frame.error_px if frame.error_px is not None else float("nan")
            for frame in wrong
        ],
        "x",
        color=GitHubColor.RED,
        markersize=6,
    )
    threshold: Line2D = plot.axhline(
        threshold_px, color=GitHubColor.RED, linestyle="--", linewidth=0.9
    )
    axis.add_artist(
        Legend(
            axis,
            [threshold],
            [ERROR_CRITERION_TEMPLATE.format(threshold=threshold_px)],
            loc="upper right",
            fontsize=9,
        )
    )
    available: list[float] = [
        frame.error_px for frame in frames if frame.error_px is not None
    ]
    axis.set_xlim(0, frames[-1].timestamp_seconds + 1 / fps)
    axis.set_ylim(0, max(30.0, max(available, default=0.0) * 1.1))
    axis.title.set_text(ERROR_TITLE)
    axis.title.set_fontsize(12)
    axis.xaxis.label.set_text(ERROR_TIME_LABEL)
    axis.yaxis.label.set_text(ERROR_DISTANCE_LABEL)
    plot.grid(axis="y", color=GitHubColor.BORDER, linewidth=0.6)


def add_summary(
    figure: Figure, frames: list[PositionComparison], threshold_px: float
) -> None:
    """State the scoring denominators and the complete observation count.

    :param figure: Figure receiving the summary and explanatory footer.
    :type figure: Figure
    :param frames: All aligned source records.
    :type frames: list[PositionComparison]
    :param threshold_px: Correct-location distance threshold.
    :type threshold_px: float
    :return: None.
    :rtype: None
    """
    counts: Counter[ComparisonStatus] = Counter(
        frame.status for frame in frames
    )
    visible: int = sum(
        counts[status]
        for status in (
            ComparisonStatus.CORRECT,
            ComparisonStatus.WRONG,
            ComparisonStatus.MISSED,
        )
    )
    negative: int = (
        counts[ComparisonStatus.FALSE_POSITIVE]
        + counts[ComparisonStatus.ABSENT]
    )
    summary: str = (
        READABLE_SUMMARY_TEMPLATE.format(
            correct=counts[ComparisonStatus.CORRECT],
            visible=visible,
            threshold=threshold_px,
        )
        if visible
        else NO_READABLE_CENTERS
    )
    negative_summary: str = (
        NEGATIVE_SUMMARY_TEMPLATE.format(
            false_positive=counts[ComparisonStatus.FALSE_POSITIVE],
            negative=negative,
        )
        if negative
        else NO_NEGATIVE_FRAMES
    )
    plot: PlotFigure = cast(PlotFigure, figure)
    measurable: int = sum(frame.error_px is not None for frame in frames)
    plot.text(
        0.04,
        0.96,
        COMPARISON_TITLE,
        fontsize=16,
        fontweight="bold",
    )
    plot.text(
        0.04,
        0.91,
        COMPARISON_SUMMARY_TEMPLATE.format(
            readable=summary, negative=negative_summary
        ),
        fontsize=10,
    )
    plot.text(
        0.04,
        0.065,
        OBSERVATIONS_FOOTNOTE_TEMPLATE.format(
            count=sum(frame.observation is not None for frame in frames)
        ),
        fontsize=10,
        color=GitHubColor.MUTED,
    )
    plot.text(
        0.04,
        0.025,
        ERROR_FOOTNOTE_TEMPLATE.format(count=measurable),
        fontsize=10,
        color=GitHubColor.MUTED,
    )


def render_plots(
    reference: DetectionExport,
    automatic: DetectionExport,
    destination: Path,
    *,
    provenance: ReferenceProvenance,
) -> None:
    """Generate a complete position audit from JSON inputs only.

    :param reference: Annotations in original source-image coordinates.
    :type reference: DetectionExport
    :param automatic: Code output to align by source index.
    :type automatic: DetectionExport
    :param destination: SVG output path.
    :type destination: Path
    :param provenance: Readable, uncertain and nonvisible frame decisions.
    :type provenance: ReferenceProvenance
    :return: None.
    :rtype: None
    """
    frames: list[PositionComparison] = compare_frames(
        reference, automatic, provenance
    )
    configure_plot_theme()
    figure: Figure = Figure(figsize=(12, 6.5), facecolor=GitHubColor.CANVAS)
    figure.subplots_adjust(
        left=0.07, right=0.98, bottom=0.18, top=0.82, wspace=0.35
    )
    positions: Axes = figure.add_subplot(1, 2, 1)
    errors: Axes = figure.add_subplot(1, 2, 2)
    draw_positions(positions, frames, reference.metadata)
    draw_errors(errors, frames, fps=reference.metadata.fps, threshold_px=20)
    add_summary(figure, frames, 20)
    cast(PlotFigure, figure).savefig(
        destination, transparent=False, format="svg"
    )
    embed_adaptive_theme(destination, THEME_STYLESHEET)
