"""Compile standalone TikZ diagrams to theme-adaptive SVG files."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from re import Pattern
from re import compile as compile_pattern
from shutil import rmtree, which
from subprocess import CalledProcessError, run
from sys import stderr
from typing import Final
from xml.etree import ElementTree


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


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DIAGRAMS_DIR: Final[Path] = PROJECT_ROOT / "docs"
BUILD_DIR: Final[Path] = PROJECT_ROOT / "build" / "diagrams"
THEME_SOURCE: Final[Path] = DIAGRAMS_DIR / "theme.tex"
THEME_STYLESHEET: Final[Path] = DIAGRAMS_DIR / "theme-dark.css"
SVG_NAMESPACE: Final[str] = "http://www.w3.org/2000/svg"
SVG_ROOT_TAG: Final[str] = f"{{{SVG_NAMESPACE}}}svg"
SVG_STYLE_TAG: Final[str] = f"{{{SVG_NAMESPACE}}}style"
INVALID_XML_CHARACTERS: Final[Pattern[str]] = compile_pattern(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f]"
)
COMMAND_ERROR_LENGTH: Final[int] = 3_000
ALL_DIAGRAMS: Final[str] = "all"


def find_diagrams() -> list[Path]:
    """List diagram sources while excluding the shared TikZ preamble.

    :return: Standalone TeX source paths in alphabetical order.
    :rtype: list[Path]
    """
    diagrams: list[Path] = []
    for path in DIAGRAMS_DIR.glob("*.tex"):
        if path != THEME_SOURCE:
            diagrams.append(path)
    return sorted(diagrams)


def select_diagrams(name: str | None) -> list[Path]:
    """Select a standalone source by stem, without resolving user paths.

    :param name: Source stem, all, or None to select every diagram.
    :type name: str | None
    :return: Selected standalone TeX source paths.
    :rtype: list[Path]
    :raises ValueError: If no sources exist or the requested stem is unknown.
    """
    available: list[Path] = find_diagrams()

    if name is None or name == ALL_DIAGRAMS:
        if not available:
            raise ValueError(f"No diagram sources found in {DIAGRAMS_DIR}")
        return available

    source: Path
    for source in available:
        if source.stem == name:
            return [source]

    raise ValueError(f"Unknown diagram: {name}")


def require_executable(name: str) -> str:
    """Resolve an installed CLI tool from PATH on any supported OS.

    :param name: Executable name to locate on PATH.
    :type name: str
    :return: Resolved executable path.
    :rtype: str
    :raises RuntimeError: If the executable is unavailable.
    """
    executable: str | None = which(name)
    if executable is None:
        raise RuntimeError(f"Required executable not found on PATH: {name}")
    return executable


def run_command(command: list[str], *, cwd: Path) -> None:
    """Execute an external compiler and include its diagnostic on failure.

    :param command: Executable path followed by its arguments.
    :type command: list[str]
    :param cwd: Working directory used by the external command.
    :type cwd: Path
    :return: None.
    :rtype: None
    :raises OSError: If the process cannot be started.
    :raises RuntimeError: If the command exits with a nonzero status.
    """
    try:
        run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )
    except CalledProcessError as error:
        parts: list[str] = []
        for part in (error.stdout, error.stderr):
            if part:
                parts.append(part.strip())
        details: str = "\n".join(parts)
        message: str = (
            f"{Path(command[0]).name} exited with code {error.returncode}"
        )
        if details:
            message += f"\n{details[-COMMAND_ERROR_LENGTH:]}"
        raise RuntimeError(message) from error


def add_theme(source: Path, destination: Path, *, css: str) -> None:
    """Inject the shared dark stylesheet into a valid XML SVG.

    :param source: SVG file exported by Inkscape.
    :type source: Path
    :param destination: Path receiving the SVG with its embedded stylesheet.
    :type destination: Path
    :param css: Shared adaptive stylesheet to embed.
    :type css: str
    :return: None.
    :rtype: None
    :raises OSError: If an SVG file cannot be read or written.
    :raises ElementTree.ParseError: If the source contains invalid XML.
    :raises ValueError: If the source root is not an SVG element.
    """
    svg: str = INVALID_XML_CHARACTERS.sub(
        "", source.read_text(encoding="utf-8")
    )
    root: ElementTree.Element[str] = ElementTree.fromstring(svg)
    if root.tag != SVG_ROOT_TAG:
        raise ValueError(f"Unexpected SVG root: {root.tag}")

    style: ElementTree.Element[str] = ElementTree.Element(
        SVG_STYLE_TAG, {"type": "text/css"}
    )
    style.text = css
    root.insert(0, style)

    ElementTree.register_namespace("", SVG_NAMESPACE)
    ElementTree.ElementTree(root).write(
        destination,
        encoding="utf-8",
        xml_declaration=True,
    )


def build_diagram(
    source: Path,
    *,
    latex: str,
    inkscape: str,
    css: str,
) -> None:
    """Build one diagram and replace its final SVG only after success.

    :param source: Standalone TeX source to compile.
    :type source: Path
    :param latex: Resolved pdflatex executable path.
    :type latex: str
    :param inkscape: Resolved Inkscape executable path.
    :type inkscape: str
    :param css: Shared adaptive stylesheet to embed.
    :type css: str
    :return: None.
    :rtype: None
    :raises OSError: If compilation artifacts cannot be read or written.
    :raises RuntimeError: If an external compiler fails.
    :raises ElementTree.ParseError: If the exported SVG contains invalid XML.
    :raises ValueError: If the exported document is not an SVG.
    """
    pdf: Path = BUILD_DIR / f"{source.stem}.pdf"
    raw_svg: Path = BUILD_DIR / f"{source.stem}.raw.svg"
    themed_svg: Path = BUILD_DIR / f"{source.stem}.themed.svg"
    output: Path = source.with_suffix(".svg")

    print(f"Building {output.relative_to(PROJECT_ROOT)}", flush=True)
    try:
        run_command(
            [
                latex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-output-directory={BUILD_DIR}",
                source.name,
            ],
            cwd=DIAGRAMS_DIR,
        )
        run_command(
            [
                inkscape,
                str(pdf),
                "--export-plain-svg",
                f"--export-filename={raw_svg}",
            ],
            cwd=PROJECT_ROOT,
        )
        add_theme(raw_svg, themed_svg, css=css)
        themed_svg.replace(output)
    finally:
        raw_svg.unlink(missing_ok=True)
        themed_svg.unlink(missing_ok=True)


def clean_diagrams() -> None:
    """Remove diagram SVGs and this task's own temporary directory.

    :return: None.
    :rtype: None
    :raises OSError: If generated files cannot be removed.
    """
    for source in find_diagrams():
        source.with_suffix(".svg").unlink(missing_ok=True)
    if BUILD_DIR.exists():
        rmtree(BUILD_DIR)
    print("Removed generated diagrams and temporary files.")


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


if __name__ == "__main__":
    raise SystemExit(main())
