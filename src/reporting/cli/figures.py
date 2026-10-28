"""Regenerate quantitative figures exclusively from persisted JSON data."""

from argparse import ArgumentParser
from pathlib import Path

from reporting.models.arguments import FigureArguments
from reporting.models.coverage import CoverageReport
from reporting.models.inputs import ComparisonInputs
from reporting.paths import (
    DATA_DIR,
    FIGURE_DIR,
    THEME_STYLESHEET,
)
from reporting.plots.coverage import render_coverage
from reporting.plots.trajectories import render_plots
from reporting.services.inputs import load_comparison_data


def parse_arguments(argv: list[str] | None = None) -> FigureArguments:
    """Select JSON inputs and figure destinations.

    :param argv: Explicit arguments or None for process arguments.
    :type argv: list[str] | None
    :return: Input and output directories.
    :rtype: FigureArguments
    """
    parser: ArgumentParser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=FIGURE_DIR)
    return parser.parse_args(argv, namespace=FigureArguments())


def main(argv: list[str] | None = None) -> int:
    """Render trajectory and five-video charts without opening videos.

    :param argv: Explicit arguments or None for process arguments.
    :type argv: list[str] | None
    :return: Zero after both SVG figures have been generated.
    :rtype: int
    """
    args: FigureArguments = parse_arguments(argv)
    inputs: ComparisonInputs = load_comparison_data(args.data_dir)
    coverage: CoverageReport = CoverageReport.model_validate_json(
        (args.data_dir / "generic-videos.json").read_bytes()
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    render_plots(
        inputs.annotations,
        inputs.detections,
        args.output_dir / "trajectories.svg",
        provenance=inputs.provenance,
    )
    render_coverage(
        coverage.videos,
        args.output_dir / "generic-videos.svg",
        THEME_STYLESHEET,
    )
    print(f"Saved JSON-generated figures to {args.output_dir}")
    return 0
