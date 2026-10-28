"""Visualize ball-tracking output coverage from validated detection exports.

Coverage measures availability of a detected or predicted position, not
accuracy. Ground-truth labels are required to quantify detection quality.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from typing import (
    Final,
    Literal,
    NamedTuple,
    Protocol,
    Self,
    TypedDict,
    Unpack,
    cast,
)
from xml.etree import ElementTree

from matplotlib import rcParams
from matplotlib.axes import Axes
from matplotlib.axis import Tick
from matplotlib.container import BarContainer
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.spines import Spine
from matplotlib.text import Text

from foosball_tracking.models.export import (
    DetectionExport,
    DetectionStatus,
    FrameExport,
    SummaryExport,
)


class GitHubColor(StrEnum):
    """Use only the light palette supported by the shared GitHub SVG theme."""

    TEXT = "#1f2328"
    MUTED = "#59636e"
    BORDER = "#d0d7de"
    SURFACE = "#f6f8fa"
    BLUE = "#0969da"
    BLUE_BACKGROUND = "#ddf4ff"
    GREEN = "#1a7f37"
    GREEN_BACKGROUND = "#dafbe1"
    PURPLE = "#8250df"
    PURPLE_BACKGROUND = "#fbefff"
    YELLOW = "#9a6700"
    YELLOW_BACKGROUND = "#fff1ba"
    RED = "#cf222e"
    RED_BACKGROUND = "#ffebe9"


class ChartText(StrEnum):
    """Centralize human-readable labels used in the performance chart."""

    TITLE = "Ball tracking coverage"
    SUMMARY = "Results from exported detections"
    COVERAGE = "of frames have a detected or predicted position"
    COVERAGE_COLUMN = "COVERAGE"
    ALL_VIDEOS = "All videos"
    FRAMES = "frames"
    VIDEOS = "videos"
    PROCESSED_FRAMES = "processed frames"
    DETECTED = "Visual detection"
    ESTIMATED = "Motion estimate"
    MISSING = "No position"
    TIMELINE_TITLE = "Detection consistency over time"
    TIMELINE_DESCRIPTION = (
        "Visual detections within equal-duration video segments"
    )
    TIMELINE_AXIS = "Progress within each video (normalized to 100%)"
    FOOTNOTE = (
        "Coverage is not accuracy: ground-truth ball positions are required "
        "to evaluate correctness."
    )


class ColorProperty(StrEnum):
    """SVG inline-style properties targeted by the shared CSS."""

    FILL = "fill"
    STROKE = "stroke"


class ChartLayout(NamedTuple):
    """Collect visual dimensions and sampling resolution in one place.

    :param window_count: Number of equal-duration timeline segments.
    :type window_count: int
    :param figure_width: Figure width in inches.
    :type figure_width: float
    :param figure_height: Figure height in inches.
    :type figure_height: float
    :param bar_height: Coverage bar height in axis units.
    :type bar_height: float
    :param timeline_height: Timeline cell height in axis units.
    :type timeline_height: float
    :param window_gap: Horizontal gap between timeline cells.
    :type window_gap: float
    :param label_threshold: Minimum percentage shown inside a bar segment.
    :type label_threshold: float
    :param coverage_xlim: Upper horizontal limit of the coverage chart.
    :type coverage_xlim: float
    :param ticks: Percentage positions used for horizontal axis ticks.
    :type ticks: tuple[int, ...]
    """

    window_count: int = 40
    figure_width: float = 11.3
    figure_height: float = 8.8
    bar_height: float = 0.69
    timeline_height: float = 0.62
    window_gap: float = 0.20
    label_threshold: float = 5.0
    coverage_xlim: float = 115.0
    ticks: tuple[int, ...] = (0, 25, 50, 75, 100)


@dataclass(frozen=True, slots=True)
class VideoStatistics:
    """Keep observed, extrapolated, and unavailable frames separate.

    :param name: Video label displayed beside the charts.
    :type name: str
    :param frames: Total number of processed frames.
    :type frames: int
    :param detected: Frames with a visual ball detection.
    :type detected: int
    :param estimated: Frames with a motion estimate only.
    :type estimated: int
    :param missing: Frames without a detected or estimated position.
    :type missing: int
    :param observed_windows: Visual-detection percentages per time segment.
    :type observed_windows: tuple[float, ...]
    """

    name: str
    frames: int
    detected: int
    estimated: int
    missing: int
    observed_windows: tuple[float, ...]

    @property
    def coverage_rate(self: Self) -> float:
        """Return the percentage with any available position.

        :return: Percentage of frames with a detected or estimated position.
        :rtype: float
        """
        return percentage(self.detected + self.estimated, self.frames)


@dataclass(init=False)
class PlotArguments(Namespace):
    """Describe command-line arguments for strict static checking.

    :param reports: Validated detection exports to aggregate and visualize.
    :type reports: list[Path]
    :param output: Destination SVG path.
    :type output: Path
    :param theme: Shared adaptive stylesheet path.
    :type theme: Path
    """

    reports: list[Path]
    output: Path
    theme: Path


class PlotAxis(Protocol):
    """Type the Matplotlib axis methods with incomplete upstream hints."""

    def tick_params(
        self: Self,
        *,
        axis: Literal["both", "x", "y"] = "both",
        **kwargs: float | str,
    ) -> None:
        """Configure tick appearance.

        :param axis: Axis whose ticks are updated.
        :type axis: Literal["both", "x", "y"]
        :param kwargs: Tick length, padding, label size, or tick selection.
        :type kwargs: float | str
        :return: None.
        :rtype: None
        """
        ...

    def text(
        self: Self, x: float, y: float, s: str, **kwargs: float | str
    ) -> Text:
        """Add text in axis coordinates.

        :param x: Horizontal text position.
        :type x: float
        :param y: Vertical text position.
        :type y: float
        :param s: Text to display.
        :type s: str
        :param kwargs: Text color, font size, weight, alignment, or draw order.
        :type kwargs: float | str
        :return: Added text artist.
        :rtype: Text
        """
        ...

    def barh(
        self: Self, y: float, width: float, **kwargs: float | str
    ) -> BarContainer:
        """Add a horizontal coverage segment.

        :param y: Vertical bar position.
        :type y: float
        :param width: Segment width in percentage points.
        :type width: float
        :param kwargs: Segment offset, height, colors, or draw order.
        :type kwargs: float | str
        :return: Container holding the added bar artists.
        :rtype: BarContainer
        """
        ...

    def axhline(self: Self, y: float, **kwargs: float | str) -> Line2D:
        """Add a horizontal separator.

        :param y: Vertical separator position.
        :type y: float
        :param kwargs: Line color and width.
        :type kwargs: float | str
        :return: Added line artist.
        :rtype: Line2D
        """
        ...

    def set_yticks(
        self: Self, ticks: Sequence[float], labels: Sequence[str]
    ) -> list[Tick]:
        """Set vertical tick positions and labels.

        :param ticks: Vertical tick positions.
        :type ticks: Sequence[float]
        :param labels: Text displayed at each tick.
        :type labels: Sequence[str]
        :return: Updated tick artists.
        :rtype: list[Tick]
        """
        ...

    def set_xticks(
        self: Self, ticks: Sequence[float], labels: Sequence[str]
    ) -> list[Tick]:
        """Set horizontal tick positions and labels.

        :param ticks: Horizontal tick positions.
        :type ticks: Sequence[float]
        :param labels: Text displayed at each tick.
        :type labels: Sequence[str]
        :return: Updated tick artists.
        :rtype: list[Tick]
        """
        ...

    def grid(self: Self, **kwargs: float | str) -> None:
        """Configure percentage grid lines.

        :param kwargs: Grid axis, color, and draw order.
        :type kwargs: float | str
        :return: None.
        :rtype: None
        """
        ...


class SvgOptions(TypedDict):
    """Describe the keyword options used to save the SVG figure.

    :param transparent: Whether to preserve a transparent background.
    :type transparent: bool
    :param format: Output image format.
    :type format: Literal["svg"]
    """

    transparent: bool
    format: Literal["svg"]


class PlotFigure(Protocol):
    """Type the Matplotlib figure methods with incomplete upstream hints."""

    def add_axes(self: Self, rect: tuple[float, float, float, float]) -> Axes:
        """Add an axis at a normalized figure rectangle.

        :param rect: Left, bottom, width, and height in figure coordinates.
        :type rect: tuple[float, float, float, float]
        :return: Added Matplotlib axis.
        :rtype: Axes
        """
        ...

    def text(
        self: Self, x: float, y: float, s: str, **kwargs: float | str
    ) -> Text:
        """Add text in normalized figure coordinates.

        :param x: Horizontal text position.
        :type x: float
        :param y: Vertical text position.
        :type y: float
        :param s: Text to display.
        :type s: str
        :param kwargs: Text color, font size, weight, or vertical alignment.
        :type kwargs: float | str
        :return: Added text artist.
        :rtype: Text
        """
        ...

    def savefig(self: Self, fname: Path, **kwargs: Unpack[SvgOptions]) -> None:
        """Save the figure as an SVG file.

        :param fname: Destination SVG path.
        :type fname: Path
        :param kwargs: Transparency and SVG format options.
        :type kwargs: Unpack[SvgOptions]
        :return: None.
        :rtype: None
        """
        ...


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT: Final[Path] = PROJECT_ROOT / "docs" / "performance.svg"
DEFAULT_THEME: Final[Path] = PROJECT_ROOT / "docs" / "theme-dark.css"
SVG_NAMESPACE: Final[str] = "http://www.w3.org/2000/svg"
SVG_STYLE_TAG: Final[str] = f"{{{SVG_NAMESPACE}}}style"
SVG_ROOT_TAG: Final[str] = f"{{{SVG_NAMESPACE}}}svg"
STYLE_COLOR_PATTERN: Final[Pattern[str]] = compile_pattern(
    rf"\b(?P<property>{ColorProperty.FILL}|{ColorProperty.STROKE})"
    r"\s*:\s*(?P<color>#[0-9a-fA-F]{6})\b"
)
LAYOUT: Final[ChartLayout] = ChartLayout()
STATUS_COLORS: Final[dict[DetectionStatus, GitHubColor]] = {
    DetectionStatus.DETECTED: GitHubColor.BLUE,
    DetectionStatus.ESTIMATED: GitHubColor.PURPLE,
    DetectionStatus.MISSING: GitHubColor.BORDER,
}
STATUS_LABELS: Final[dict[DetectionStatus, ChartText]] = {
    DetectionStatus.DETECTED: ChartText.DETECTED,
    DetectionStatus.ESTIMATED: ChartText.ESTIMATED,
    DetectionStatus.MISSING: ChartText.MISSING,
}


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


def percentage_labels(ticks: tuple[int, ...]) -> list[str]:
    """Format horizontal tick positions as percentages.

    :param ticks: Percentage positions to label.
    :type ticks: tuple[int, ...]
    :return: Percentage labels in the same order as the input ticks.
    :rtype: list[str]
    """
    labels: list[str] = []
    for tick in ticks:
        labels.append(f"{tick}%")
    return labels


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
        name=ChartText.ALL_VIDEOS,
        frames=frames,
        detected=detected,
        estimated=estimated,
        missing=missing,
        observed_windows=(),
    )


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
                f"{width:.1f}%",
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
        f"{video.coverage_rate:.1f}%",
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
        labels.append(f"{video.name}\n{video.frames:,} {ChartText.FRAMES}")

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
        ChartText.COVERAGE_COLUMN,
        color=GitHubColor.MUTED,
        fontsize=8,
        fontweight="bold",
    )
    style_axis(axis)
    tick: Text
    for tick in axis.get_yticklabels():
        if tick.get_text().startswith(ChartText.ALL_VIDEOS):
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

    rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "svg.fonttype": "path",
            "axes.unicode_minus": False,
        }
    )
    figure: Figure = Figure(
        figsize=(layout.figure_width, layout.figure_height),
        facecolor="none",
    )
    plot: PlotFigure = cast(PlotFigure, figure)
    coverage_axis: Axes = plot.add_axes((0.18, 0.485, 0.75, 0.32))
    timeline_axis: Axes = plot.add_axes((0.18, 0.167, 0.75, 0.215))

    plot.text(
        0.055,
        0.957,
        ChartText.TITLE,
        color=GitHubColor.TEXT,
        fontsize=22,
        fontweight="bold",
    )
    plot.text(
        0.055,
        0.920,
        f"{len(videos)} {ChartText.VIDEOS}  ·  "
        f"{total.frames:,} {ChartText.PROCESSED_FRAMES}"
        f"  ·  {ChartText.SUMMARY}",
        fontsize=10,
        color=GitHubColor.MUTED,
    )
    plot.text(
        0.055,
        0.869,
        f"{total.coverage_rate:.1f}%",
        color=GitHubColor.TEXT,
        fontsize=23,
        fontweight="bold",
    )
    plot.text(
        0.190,
        0.875,
        ChartText.COVERAGE,
        color=GitHubColor.MUTED,
        fontsize=10,
    )

    add_status_legend(figure)
    add_coverage_chart(coverage_axis, videos, layout=layout)

    plot.text(
        0.055,
        0.432,
        ChartText.TIMELINE_TITLE,
        fontsize=15,
        fontweight="bold",
        color=GitHubColor.TEXT,
    )
    plot.text(
        0.055,
        0.407,
        ChartText.TIMELINE_DESCRIPTION,
        fontsize=9,
        color=GitHubColor.MUTED,
    )
    add_observation_timeline(timeline_axis, videos, layout=layout)
    plot.text(
        0.18,
        0.130,
        ChartText.TIMELINE_AXIS,
        fontsize=8,
        color=GitHubColor.MUTED,
    )
    plot.text(
        0.055,
        0.037,
        ChartText.FOOTNOTE,
        fontsize=9,
        color=GitHubColor.MUTED,
    )
    return figure


def normalize_inline_color_styles(style: str) -> str:
    """Match the no-whitespace `style*` selectors in theme-dark.css.

    :param style: Inline SVG style declarations to normalize.
    :type style: str
    :return: Style declarations with lowercase hexadecimal color values.
    :rtype: str
    """

    def normalize_match(match: Match[str]) -> str:
        """Normalize one matched SVG color declaration.

        :param match: Matched fill or stroke declaration and its color value.
        :type match: Match[str]
        :return: Color declaration without whitespace around the colon.
        :rtype: str
        """
        return f"{match.group('property')}:{match.group('color').lower()}"

    return STYLE_COLOR_PATTERN.sub(normalize_match, style)


def embed_adaptive_theme(svg_path: Path, css_path: Path) -> None:
    """Embed the shared TikZ CSS without maintaining a second dark palette.

    :param svg_path: SVG file to update with normalized styles and CSS.
    :type svg_path: Path
    :param css_path: Shared adaptive stylesheet to embed.
    :type css_path: Path
    :return: None.
    :rtype: None
    :raises OSError: If the SVG or stylesheet cannot be read or written.
    :raises ElementTree.ParseError: If the SVG contains invalid XML.
    :raises ValueError: If the source root is not an SVG element.
    """
    stylesheet: str = css_path.read_text(encoding="utf-8")
    ElementTree.register_namespace("", SVG_NAMESPACE)
    document: ElementTree.ElementTree[ElementTree.Element[str]] = (
        ElementTree.parse(svg_path)
    )
    root: ElementTree.Element[str] = document.getroot()
    if root.tag != SVG_ROOT_TAG:
        raise ValueError(f"Not an SVG document: {svg_path}")

    element: ElementTree.Element[str]
    for element in root.iter():
        style: str | None = element.get("style")
        if style:
            element.set("style", normalize_inline_color_styles(style))

    style_element: ElementTree.Element[str] = ElementTree.Element(
        SVG_STYLE_TAG, attrib={"type": "text/css"}
    )
    style_element.text = stylesheet
    root.insert(0, style_element)
    document.write(svg_path, encoding="utf-8", xml_declaration=True)


def parse_arguments(argv: list[str] | None = None) -> PlotArguments:
    """Parse and type-check CLI arguments.

    :param argv: Arguments to parse, or None to use the process arguments.
    :type argv: list[str] | None
    :return: Detection export paths, destination SVG, and stylesheet path.
    :rtype: PlotArguments
    """
    parser: ArgumentParser = ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--theme", type=Path, default=DEFAULT_THEME)
    return parser.parse_args(argv, namespace=PlotArguments())


def main(argv: list[str] | None = None) -> int:
    """Generate a single font-independent, theme-adaptive SVG.

    :param argv: Arguments to parse, or None to use the process arguments.
    :type argv: list[str] | None
    :return: Zero after the SVG has been generated successfully.
    :rtype: int
    :raises OSError: If input files or the destination cannot be accessed.
    :raises ElementTree.ParseError: If the generated SVG contains invalid XML.
    :raises ValueError: If an export is invalid or the output is not an SVG.
    """
    args: PlotArguments = parse_arguments(argv)
    if args.output.suffix.lower() != ".svg":
        raise ValueError("Output must be an SVG file (.svg).")
    statistics: list[VideoStatistics] = []
    for path in args.reports:
        statistics.append(load_statistics(path, layout=LAYOUT))
    figure: Figure = make_figure(statistics, layout=LAYOUT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cast(PlotFigure, figure).savefig(
        args.output, transparent=True, format="svg"
    )
    embed_adaptive_theme(args.output, args.theme)

    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
