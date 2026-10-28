"""Plot stored coverage data or summarize original detection exports."""

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path

from reporting.models.arguments import PlotArguments
from reporting.models.coverage import (
    CoverageReport,
    CoverageSource,
    VideoStatistics,
)
from reporting.models.plotting import ChartLayout
from reporting.paths import (
    DATA_DIR,
    FIGURE_DIR,
    THEME_STYLESHEET,
)
from reporting.plots.coverage import render_coverage
from reporting.services.coverage import load_statistics
from tracking.models.export import DetectionExport


def parse_arguments(argv: list[str] | None = None) -> PlotArguments:
    """Read optional export paths and coverage chart destinations.

    :param argv: Explicit arguments or None for process arguments.
    :type argv: list[str] | None
    :return: Typed source, SVG, stylesheet and compact JSON paths.
    :rtype: PlotArguments
    """
    parser: ArgumentParser = ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="*", type=Path)
    parser.add_argument(
        "--output", type=Path, default=FIGURE_DIR / "generic-videos.svg"
    )
    parser.add_argument("--theme", type=Path, default=THEME_STYLESHEET)
    parser.add_argument("--save-data", type=Path, default=None)
    return parser.parse_args(argv, namespace=PlotArguments())


def main(argv: list[str] | None = None) -> int:
    """Generate coverage from cached JSON or original exports.

    :param argv: Explicit arguments or None for process arguments.
    :type argv: list[str] | None
    :return: Zero after the chart and optional JSON have been saved.
    :rtype: int
    """
    args: PlotArguments = parse_arguments(argv)
    report: CoverageReport
    if args.reports:
        statistics: list[VideoStatistics] = []
        sources: list[CoverageSource] = []
        path: Path
        for path in args.reports:
            statistics.append(load_statistics(path, layout=ChartLayout()))
            source_bytes: bytes = path.read_bytes()
            source: DetectionExport = DetectionExport.model_validate_json(
                source_bytes
            )
            sources.append(
                CoverageSource(
                    path=path,
                    sha256=sha256(source_bytes).hexdigest(),
                    configuration=source.configuration,
                    metadata=source.metadata,
                )
            )
        report = CoverageReport(videos=statistics, sources=sources)
    else:
        report = CoverageReport.model_validate_json(
            (DATA_DIR / "generic-videos.json").read_bytes()
        )
    if args.save_data is not None:
        args.save_data.parent.mkdir(parents=True, exist_ok=True)
        args.save_data.write_text(report.model_dump_json(indent=2) + "\n")
    render_coverage(report.videos, args.output, args.theme)
    print(f"Saved {args.output}")
    return 0
