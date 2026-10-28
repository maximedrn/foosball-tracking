"""Compile standalone TikZ sources into documentation SVG illustrations."""

from __future__ import annotations

from pathlib import Path
from re import Pattern
from re import compile as compile_pattern
from shutil import rmtree, which
from subprocess import CalledProcessError, run
from typing import Final
from xml.etree import ElementTree

from reporting.paths import (
    BUILD_DIR,
    DIAGRAM_FIGURES_DIR,
    PROJECT_ROOT,
)
from reporting.paths import (
    DIAGRAM_SOURCE_DIR as DIAGRAMS_DIR,
)
from reporting.utils.svg import SVG_NAMESPACE, apply_adaptive_theme

THEME_SOURCE: Final[Path] = DIAGRAMS_DIR / "theme.tex"
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
    apply_adaptive_theme(root, css)

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
    output: Path = DIAGRAM_FIGURES_DIR / f"{source.stem}.svg"

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
        (DIAGRAM_FIGURES_DIR / f"{source.stem}.svg").unlink(missing_ok=True)
    if BUILD_DIR.exists():
        rmtree(BUILD_DIR)
    print("Removed generated diagrams and temporary files.")
