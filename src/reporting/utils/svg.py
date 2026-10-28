"""Embed the shared light and dark SVG palettes."""

from __future__ import annotations

from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from typing import Final
from xml.etree import ElementTree

from reporting.models.plotting import ColorProperty

SVG_NAMESPACE: Final[str] = "http://www.w3.org/2000/svg"
SVG_STYLE_TAG: Final[str] = f"{{{SVG_NAMESPACE}}}style"
SVG_ROOT_TAG: Final[str] = f"{{{SVG_NAMESPACE}}}svg"
THEME_STYLE_ID: Final[str] = "github-adaptive-theme"
STYLE_COLOR_PATTERN: Final[Pattern[str]] = compile_pattern(
    rf"\b(?P<property>{ColorProperty.FILL}|{ColorProperty.STROKE})"
    r"\s*:\s*(?P<color>#[0-9a-fA-F]{6})\b"
)


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


def apply_adaptive_theme(
    root: ElementTree.Element[str], stylesheet: str
) -> None:
    """Normalize colors and replace the shared style on an SVG root.

    :param root: Parsed SVG root receiving the adaptive stylesheet.
    :type root: ElementTree.Element[str]
    :param stylesheet: Shared light and dark CSS rules.
    :type stylesheet: str
    :return: None.
    :rtype: None
    :raises ValueError: If the source root is not an SVG element.
    """
    if root.tag != SVG_ROOT_TAG:
        raise ValueError(f"Not an SVG document: {root.tag}")

    for child in list(root):
        if child.tag == SVG_STYLE_TAG and child.get("id") == THEME_STYLE_ID:
            root.remove(child)

    for element in root.iter():
        style: str | None = element.get("style")
        if style:
            element.set("style", normalize_inline_color_styles(style))

    style_element: ElementTree.Element[str] = ElementTree.Element(
        SVG_STYLE_TAG,
        attrib={"type": "text/css", "id": THEME_STYLE_ID},
    )
    style_element.text = stylesheet
    root.insert(0, style_element)


def embed_adaptive_theme(svg_path: Path, css_path: Path) -> None:
    """Embed the shared stylesheet in a generated SVG.

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
    ElementTree.register_namespace("", SVG_NAMESPACE)
    document: ElementTree.ElementTree[ElementTree.Element[str]] = (
        ElementTree.parse(svg_path)
    )
    apply_adaptive_theme(
        document.getroot(), css_path.read_text(encoding="utf-8")
    )
    document.write(svg_path, encoding="utf-8", xml_declaration=True)
