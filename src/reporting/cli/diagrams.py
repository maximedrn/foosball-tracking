"""Build or clean the documentation's method illustrations."""

from argparse import ArgumentParser
from pathlib import Path
from sys import stderr
from xml.etree import ElementTree

from reporting.models.arguments import (
    DiagramArguments,
    ExternalTool,
)
from reporting.paths import (
    BUILD_DIR,
    DIAGRAM_FIGURES_DIR,
    THEME_STYLESHEET,
)
from reporting.services.diagrams import (
    build_diagram,
    clean_diagrams,
    require_executable,
    select_diagrams,
)


def parse_arguments(argv: list[str] | None = None) -> DiagramArguments:
    """Parse the diagram CLI options.

    :param argv: Arguments to parse, or None to use the process arguments.
    :type argv: list[str] | None
    :return: Parsed diagram selection and cleanup options.
    :rtype: DiagramArguments
    """
    parser: ArgumentParser = ArgumentParser(description=__doc__)
    parser.add_argument("diagram", nargs="?", default=None)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args(argv, namespace=DiagramArguments())


def main(argv: list[str] | None = None) -> int:
    """Build one/all diagrams or remove generated artifacts.

    :param argv: Arguments to parse, or None to use the process arguments.
    :type argv: list[str] | None
    :return: Zero on success or one if diagram generation fails.
    :rtype: int
    """
    arguments: DiagramArguments = parse_arguments(argv)
    try:
        if arguments.clean:
            if arguments.diagram is not None:
                raise ValueError("--clean does not accept a diagram name")
            clean_diagrams()
            return 0

        selected: list[Path] = select_diagrams(arguments.diagram)
        css: str = THEME_STYLESHEET.read_text(encoding="utf-8")
        latex: str = require_executable(ExternalTool.LATEX)
        inkscape: str = require_executable(ExternalTool.INKSCAPE)

        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        DIAGRAM_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        for source in selected:
            build_diagram(source, latex=latex, inkscape=inkscape, css=css)
    except (
        OSError,
        ValueError,
        RuntimeError,
        ElementTree.ParseError,
    ) as error:
        print(f"Diagram build error: {error}", file=stderr)
        return 1
    return 0
