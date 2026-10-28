"""Dispatch reporting commands without changing video-processing behavior."""

from argparse import ArgumentParser
from sys import argv as process_arguments

from reporting.cli.coverage import main as coverage_main
from reporting.cli.diagrams import main as diagrams_main
from reporting.cli.evaluation import main as evaluation_main
from reporting.cli.figures import main as figures_main
from reporting.cli.review import main as review_main
from reporting.models.arguments import ReportArguments


def main(argv: list[str] | None = None) -> int:
    """Run a selected reporting or asset-generation operation.

    :param argv: Explicit arguments or None for process arguments.
    :type argv: list[str] | None
    :return: Exit status of the selected command.
    :rtype: int
    """
    parser: ArgumentParser = ArgumentParser(
        prog="reporting", description=__doc__
    )
    parser.add_argument(
        "command",
        choices=("evaluate", "figures", "coverage", "review", "diagrams"),
    )
    arguments: list[str] = process_arguments[1:] if argv is None else argv
    args: ReportArguments = parser.parse_args(
        arguments[:1], namespace=ReportArguments()
    )
    remainder: list[str] = arguments[1:]
    if args.command == "evaluate":
        return evaluation_main(remainder)
    if args.command == "figures":
        return figures_main(remainder)
    if args.command == "coverage":
        return coverage_main(remainder)
    if args.command == "review":
        return review_main(remainder)
    return diagrams_main(remainder)
