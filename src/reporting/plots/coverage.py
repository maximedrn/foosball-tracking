"""Render coverage and detection timelines from measured JSON statistics."""

from pathlib import Path
from typing import Final, cast

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.text import Text

from reporting.models.coverage import VideoStatistics
from reporting.models.plotting import (
    ChartLayout,
    GitHubColor,
    PlotAxis,
    PlotFigure,
)
from reporting.services.coverage import (
    aggregate_statistics,
    percentage,
)
from reporting.utils.messages import (
    ALL_VIDEOS,
    COVERAGE_COLUMN,
    COVERAGE_DESCRIPTION,
    COVERAGE_FOOTNOTE,
    COVERAGE_SUMMARY_TEMPLATE,
    COVERAGE_TITLE,
    DETECTED_LABEL,
    ESTIMATED_LABEL,
    MISSING_LABEL,
    PERCENT_TEMPLATE,
    PERCENT_TICK_TEMPLATE,
    TIMELINE_AXIS,
    TIMELINE_DESCRIPTION,
    TIMELINE_TITLE,
    VIDEO_ROW_TEMPLATE,
)
from reporting.utils.svg import embed_adaptive_theme
from reporting.utils.theme import configure_plot_theme
from tracking.models.export import DetectionStatus

STATUS_COLORS: Final[dict[DetectionStatus, GitHubColor]] = {
    DetectionStatus.DETECTED: GitHubColor.BLUE,
    DetectionStatus.ESTIMATED: GitHubColor.PURPLE,
    DetectionStatus.MISSING: GitHubColor.BORDER,
}
STATUS_LABELS: Final[dict[DetectionStatus, str]] = {
    DetectionStatus.DETECTED: DETECTED_LABEL,
    DetectionStatus.ESTIMATED: ESTIMATED_LABEL,
    DetectionStatus.MISSING: MISSING_LABEL,
}


def percentage_labels(ticks: tuple[int, ...]) -> list[str]:
    """Format horizontal tick positions as percentages.

    :param ticks: Percentage positions to label.
    :type ticks: tuple[int, ...]
    :return: Percentage labels in the same order as the input ticks.
    :rtype: list[str]
    """
    labels: list[str] = []
    for tick in ticks:
        labels.append(PERCENT_TICK_TEMPLATE.format(value=tick))
    return labels


def style_axis(axis: Axes) -> None:
    """Use the same neutral axis treatment on both subplots.

    :param axis: Matplotlib axis to style.
    :type axis: Axes
    :return: None.
    :rtype: None
    """
    axis.set_facecolor("none")
    for spine in axis.spines.values():
        spine.set_visible(False)
    cast(PlotAxis, axis).tick_params(axis="both", which="both", length=0)
    for label in axis.get_yticklabels():
        label.set_color(GitHubColor.TEXT)
    for label in axis.get_xticklabels():
        label.set_color(GitHubColor.MUTED)


def add_coverage_bar(
    axis: Axes,
    video: VideoStatistics,
    *,
    y_position: int,
    total: VideoStatistics,
    layout: ChartLayout,
) -> None:
    """Draw the three status segments and coverage label for one row.

    :param axis: Matplotlib axis receiving the coverage bar.
    :type axis: Axes
    :param video: Frame counts to display in this row.
    :type video: VideoStatistics
    :param y_position: Vertical position of the row.
    :type y_position: int
    :param total: Aggregate row whose labels use bold text.
    :type total: VideoStatistics
    :param layout: Bar dimensions and percentage label threshold.
    :type layout: ChartLayout
    :return: None.
    :rtype: None
    """
    plot: PlotAxis = cast(PlotAxis, axis)
    left: float = 0.0
    counts: tuple[tuple[DetectionStatus, int], ...] = (
        (DetectionStatus.DETECTED, video.detected),
        (DetectionStatus.ESTIMATED, video.estimated),
        (DetectionStatus.MISSING, video.missing),
    )
    for status, count in counts:
        width: float = percentage(count, video.frames)
        plot.barh(
            y_position,
            width,
            left=left,
            color=STATUS_COLORS[status],
            height=layout.bar_height,
            edgecolor="none",
            zorder=3,
        )
        if width >= layout.label_threshold:
            label_color: GitHubColor = (
                GitHubColor.TEXT
                if status is DetectionStatus.MISSING
                else GitHubColor.SURFACE
            )
            plot.text(
                left + width / 2.0,
                y_position,
                PERCENT_TEMPLATE.format(value=width),
                ha="center",
                va="center",
                color=label_color,
                fontsize=9,
                fontweight="bold" if video is total else "normal",
                zorder=4,
            )
        left += width

    plot.text(
        103.2,
        y_position,
        PERCENT_TEMPLATE.format(value=video.coverage_rate),
        ha="left",
        va="center",
        color=GitHubColor.TEXT,
        fontsize=10,
        fontweight="bold" if video is total else "normal",
    )


def add_coverage_chart(
    axis: Axes,
    videos: list[VideoStatistics],
    *,
    layout: ChartLayout,
) -> None:
    """Show visual detections, motion estimates, and missing frames.

    :param axis: Matplotlib axis receiving the stacked coverage chart.
    :type axis: Axes
    :param videos: Per-video frame counts to display and aggregate.
    :type videos: list[VideoStatistics]
    :param layout: Bar dimensions, label threshold, and axis tick positions.
    :type layout: ChartLayout
    :return: None.
    :rtype: None
    """
    plot: PlotAxis = cast(PlotAxis, axis)
    total: VideoStatistics = aggregate_statistics(videos)
    rows: list[VideoStatistics] = [*videos, total]
    positions: list[int] = list(range(len(rows) - 1, -1, -1))
    labels: list[str] = []
    for video in rows:
        labels.append(
            VIDEO_ROW_TEMPLATE.format(name=video.name, frames=video.frames)
        )

    y_position: int
    for video, y_position in zip(rows, positions, strict=True):
        add_coverage_bar(
            axis, video, y_position=y_position, total=total, layout=layout
        )

    plot.axhline(0.5, color=GitHubColor.BORDER, linewidth=1)
    plot.set_yticks(positions, labels)
    plot.tick_params(axis="y", pad=12, labelsize=10)
    axis.set_xlim(0, layout.coverage_xlim)
    axis.set_ylim(-0.55, len(rows) - 0.45)
    plot.set_xticks(layout.ticks, percentage_labels(layout.ticks))
    plot.tick_params(axis="x", labelsize=9, pad=8)
    plot.grid(axis="x", color=GitHubColor.BORDER, zorder=0)
    plot.text(
        102.5,
        len(rows) - 0.29,
        COVERAGE_COLUMN,
        color=GitHubColor.MUTED,
        fontsize=8,
        fontweight="bold",
    )
    style_axis(axis)
    tick: Text
    for tick in axis.get_yticklabels():
        if tick.get_text().startswith(ALL_VIDEOS):
            tick.set_fontweight("bold")


def add_observation_timeline(
    axis: Axes,
    videos: list[VideoStatistics],
    *,
    layout: ChartLayout,
) -> None:
    """Show continuous visual-detection coverage in fixed time windows.

    :param axis: Matplotlib axis receiving the observation timeline.
    :type axis: Axes
    :param videos: Per-video visual-detection percentages by time segment.
    :type videos: list[VideoStatistics]
    :param layout: Timeline cell dimensions and percentage tick positions.
    :type layout: ChartLayout
    :return: None.
    :rtype: None
    """
    plot: PlotAxis = cast(PlotAxis, axis)
    window_width: float = 100.0 / layout.window_count

    for row, video in enumerate(videos):
        y_position: int = len(videos) - row - 1
        bottom: float = y_position - layout.timeline_height / 2.0
        index: int
        rate: float
        for index, rate in enumerate(video.observed_windows):
            x_position: float = index * window_width + layout.window_gap / 2.0
            cell_width: float = window_width - layout.window_gap
            axis.add_patch(
                Rectangle(
                    (x_position, bottom),
                    cell_width,
                    layout.timeline_height,
                    facecolor=GitHubColor.BLUE_BACKGROUND,
                    edgecolor="none",
                )
            )
            if rate > 0.0:
                observed_height: float = layout.timeline_height * rate / 100.0
                axis.add_patch(
                    Rectangle(
                        (x_position, bottom),
                        cell_width,
                        observed_height,
                        facecolor=GitHubColor.BLUE,
                        edgecolor="none",
                    )
                )

    axis.set_xlim(0, 100)
    axis.set_ylim(-0.56, len(videos) - 0.44)
    labels: list[str] = []
    for video in videos:
        labels.append(video.name)
    plot.set_yticks(
        list(range(len(videos) - 1, -1, -1)),
        labels,
    )
    plot.tick_params(axis="y", pad=12, labelsize=10)
    plot.set_xticks(layout.ticks, percentage_labels(layout.ticks))
    plot.tick_params(axis="x", labelsize=9, pad=8)
    style_axis(axis)


def add_status_legend(figure: Figure) -> None:
    """Keep the legend compact and tied to the status enum.

    :param figure: Matplotlib figure receiving the status legend.
    :type figure: Figure
    :return: None.
    :rtype: None
    """
    plot: PlotFigure = cast(PlotFigure, figure)
    for index, status in enumerate(STATUS_COLORS):
        x_position: float = 0.165 + index * 0.205
        figure.add_artist(
            Rectangle(
                (x_position, 0.825),
                0.012,
                0.014,
                transform=figure.transFigure,
                facecolor=STATUS_COLORS[status],
                edgecolor="none",
            )
        )
        plot.text(
            x_position + 0.018,
            0.832,
            STATUS_LABELS[status],
            va="center",
            fontsize=9,
            color=GitHubColor.MUTED,
        )


def make_figure(
    videos: list[VideoStatistics],
    *,
    layout: ChartLayout,
) -> Figure:
    """Compose coverage and temporal detection charts.

    :param videos: Per-video statistics used by both charts.
    :type videos: list[VideoStatistics]
    :param layout: Figure dimensions and chart sampling settings.
    :type layout: ChartLayout
    :return: Figure containing coverage bars, a timeline, and their labels.
    :rtype: Figure
    """
    total: VideoStatistics = aggregate_statistics(videos)

    configure_plot_theme()
    figure: Figure = Figure(
        figsize=(layout.figure_width, layout.figure_height),
        facecolor=GitHubColor.CANVAS,
    )
    plot: PlotFigure = cast(PlotFigure, figure)
    coverage_axis: Axes = plot.add_axes((0.18, 0.485, 0.75, 0.32))
    timeline_axis: Axes = plot.add_axes((0.18, 0.167, 0.75, 0.215))

    plot.text(
        0.055,
        0.957,
        COVERAGE_TITLE,
        color=GitHubColor.TEXT,
        fontsize=22,
        fontweight="bold",
    )
    plot.text(
        0.055,
        0.920,
        COVERAGE_SUMMARY_TEMPLATE.format(
            videos=len(videos), frames=total.frames
        ),
        fontsize=10,
        color=GitHubColor.MUTED,
    )
    plot.text(
        0.055,
        0.869,
        PERCENT_TEMPLATE.format(value=total.coverage_rate),
        color=GitHubColor.TEXT,
        fontsize=23,
        fontweight="bold",
    )
    plot.text(
        0.190,
        0.875,
        COVERAGE_DESCRIPTION,
        color=GitHubColor.MUTED,
        fontsize=10,
    )

    add_status_legend(figure)
    add_coverage_chart(coverage_axis, videos, layout=layout)

    plot.text(
        0.055,
        0.432,
        TIMELINE_TITLE,
        fontsize=15,
        fontweight="bold",
        color=GitHubColor.TEXT,
    )
    plot.text(
        0.055,
        0.407,
        TIMELINE_DESCRIPTION,
        fontsize=9,
        color=GitHubColor.MUTED,
    )
    add_observation_timeline(timeline_axis, videos, layout=layout)
    plot.text(
        0.18,
        0.130,
        TIMELINE_AXIS,
        fontsize=8,
        color=GitHubColor.MUTED,
    )
    plot.text(
        0.055,
        0.037,
        COVERAGE_FOOTNOTE,
        fontsize=9,
        color=GitHubColor.MUTED,
    )
    return figure


def render_coverage(
    videos: list[VideoStatistics], destination: Path, theme: Path
) -> None:
    """Save a coverage chart from persisted, validated statistics.

    :param videos: Coverage counts and equal-duration window rates.
    :type videos: list[VideoStatistics]
    :param destination: Output SVG path.
    :type destination: Path
    :param theme: Shared adaptive SVG stylesheet.
    :type theme: Path
    :return: None.
    :rtype: None
    :raises ValueError: If no videos or a non-SVG destination is supplied.
    """
    if not videos or destination.suffix.lower() != ".svg":
        raise ValueError("Coverage needs video statistics and an SVG output")
    layout: ChartLayout = ChartLayout(
        window_count=len(videos[0].observed_windows)
    )
    figure: Figure = make_figure(videos, layout=layout)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cast(PlotFigure, figure).savefig(
        destination, transparent=False, format="svg"
    )
    embed_adaptive_theme(destination, theme)
