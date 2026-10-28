"""Define chart presentation settings and typed Matplotlib interfaces."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import (
    Literal,
    NamedTuple,
    NotRequired,
    Protocol,
    Self,
    TypedDict,
    Unpack,
)

from matplotlib.axes import Axes
from matplotlib.axis import Tick
from matplotlib.container import BarContainer
from matplotlib.image import AxesImage
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.text import Text

from tracking.models import Image


class GitHubColor(StrEnum):
    """Use only the light palette supported by the shared GitHub SVG theme."""

    CANVAS = "#ffffff"
    TEXT = "#1f2328"
    MUTED = "#59636e"
    BORDER = "#d1d9e0"
    SURFACE = "#f6f8fa"
    BLUE = "#0969da"
    BLUE_BACKGROUND = "#ddf4ff"
    GREEN = "#1a7f37"
    GREEN_BACKGROUND = "#dafbe1"
    PURPLE = "#8250df"
    PURPLE_BACKGROUND = "#fbefff"
    ORANGE = "#bc4c00"
    YELLOW = "#9a6700"
    YELLOW_BACKGROUND = "#fff8c5"
    RED = "#cf222e"
    RED_BACKGROUND = "#ffebe9"


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


class ObservationStyle(NamedTuple):
    """Describe the presentation of one observation category.

    :param label: Legend description.
    :type label: str
    :param color: Marker color.
    :type color: str
    :param marker: Matplotlib marker symbol.
    :type marker: str
    """

    label: str
    color: str
    marker: str


class PlotAxis(Protocol):
    """Type the Matplotlib axis methods with incomplete upstream hints."""

    def imshow(
        self: Self, image: Image, *, interpolation: str = "nearest"
    ) -> AxesImage:
        """Display a source-image crop using its original aspect ratio.

        :param image: RGB pixels to display.
        :type image: Image
        :param interpolation: Image sampling method.
        :type interpolation: str
        :return: Displayed image artist.
        :rtype: AxesImage
        """
        ...

    def axvspan(
        self: Self, xmin: float, xmax: float, **kwargs: float | str
    ) -> Patch:
        """Shade a time interval without a readable annotation center.

        :param xmin: Beginning of the interval.
        :type xmin: float
        :param xmax: End of the interval.
        :type xmax: float
        :param kwargs: Fill color, opacity or border style.
        :type kwargs: float | str
        :return: Added shaded interval.
        :rtype: Patch
        """
        ...

    def plot(
        self: Self,
        x: Sequence[float],
        y: Sequence[float],
        fmt: str = "",
        **kwargs: float | str,
    ) -> list[Line2D]:
        """Draw a line or markers using numeric source coordinates.

        :param x: Horizontal coordinates.
        :type x: Sequence[float]
        :param y: Vertical coordinates.
        :type y: Sequence[float]
        :param fmt: Matplotlib line and marker format.
        :type fmt: str
        :param kwargs: Line color, width, opacity or marker size.
        :type kwargs: float | str
        :return: Added line artists.
        :rtype: list[Line2D]
        """
        ...

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


class FigureSaveOptions(TypedDict):
    """Describe the keyword options used to save report figures.

    :param transparent: Whether to preserve a transparent background.
    :type transparent: bool
    :param format: Output image format.
    :type format: Literal["svg", "jpg"]
    :param dpi: Raster output resolution.
    :type dpi: int
    """

    transparent: NotRequired[bool]
    format: Literal["svg", "jpg"]
    dpi: NotRequired[int]


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

    def savefig(
        self: Self, fname: Path, **kwargs: Unpack[FigureSaveOptions]
    ) -> None:
        """Save the figure in its declared report format.

        :param fname: Destination SVG path.
        :type fname: Path
        :param kwargs: Transparency and SVG format options.
        :type kwargs: Unpack[FigureSaveOptions]
        :return: None.
        :rtype: None
        """
        ...
