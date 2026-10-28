"""Describe parsed reporting command arguments."""

from argparse import Namespace
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(init=False)
class EvaluationArguments(Namespace):
    """Describe the evaluation command-line arguments.

    :param reference: Reference export using the project's JSON schema.
    :type reference: Path
    :param detections: Automatic export to compare against the reference.
    :type detections: Path
    :param provenance: Sidecar containing reference visibility and hashes.
    :type provenance: Path
    :param output: Destination for the evaluation measurements.
    :type output: Path
    """

    reference: Path
    detections: Path
    provenance: Path
    output: Path


class ExternalTool(StrEnum):
    """External programs required to build the diagrams."""

    LATEX = "pdflatex"
    INKSCAPE = "inkscape"


@dataclass(init=False)
class DiagramArguments(Namespace):
    """Represent parsed diagram build arguments.

    :param diagram: Source stem, all, or None to select every diagram.
    :type diagram: str | None
    :param clean: Whether to remove generated diagrams instead of building.
    :type clean: bool
    """

    diagram: str | None
    clean: bool


@dataclass(init=False)
class PlotArguments(Namespace):
    """Describe command-line arguments for strict static checking.

    :param reports: Validated detection exports to aggregate and visualize.
    :type reports: list[Path]
    :param output: Destination SVG path.
    :type output: Path
    :param theme: Shared adaptive stylesheet path.
    :type theme: Path
    :param save_data: Optional compact JSON destination for future plotting.
    :type save_data: Path | None
    """

    reports: list[Path]
    output: Path
    theme: Path
    save_data: Path | None


@dataclass(init=False)
class FigureArguments(Namespace):
    """Select report data and figure output directories.

    :param data_dir: Folder containing persisted report JSON files.
    :type data_dir: Path
    :param output_dir: Folder receiving charts or example images.
    :type output_dir: Path
    """

    data_dir: Path
    output_dir: Path


@dataclass(init=False)
class ReportArguments(Namespace):
    """Select one reporting operation.

    :param command: Reporting command to execute.
    :type command: str
    """

    command: str
