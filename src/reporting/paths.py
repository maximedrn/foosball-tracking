"""Locate report inputs and assets from the project working directory."""

from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path.cwd()
DATA_DIR: Final[Path] = PROJECT_ROOT / "docs" / "data"
FIGURE_DIR: Final[Path] = PROJECT_ROOT / "docs" / "figures"
REVIEW_DIR: Final[Path] = PROJECT_ROOT / "output" / "evaluation"
DIAGRAM_SOURCE_DIR: Final[Path] = (
    PROJECT_ROOT / "docs" / "diagrams" / "sources"
)
DIAGRAM_FIGURES_DIR: Final[Path] = (
    PROJECT_ROOT / "docs" / "diagrams" / "figures"
)
BUILD_DIR: Final[Path] = PROJECT_ROOT / "build" / "diagrams"
THEME_STYLESHEET: Final[Path] = (
    PROJECT_ROOT / "docs" / "styles" / "theme-dark.css"
)
