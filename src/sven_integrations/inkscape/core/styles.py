"""CSS style helpers for SVG elements in the Inkscape harness.

All style data is stored as a CSS inline-style string on
``element.style``.  Convenience functions build or mutate that string
while also keeping the legacy ``element.fill`` / ``element.stroke``
fields in sync when those properties are changed.
"""

from __future__ import annotations

from typing import Any

from ..project import InkscapeProject

# ---------------------------------------------------------------------------
# Allowed CSS property registry

STYLE_PROPERTIES: dict[str, str] = {
    "fill": "Paint for fill area",
    "stroke": "Paint for stroke",
    "stroke-width": "Width of the stroke in user units",
    "opacity": "Overall element opacity (0.0–1.0)",
    "fill-opacity": "Opacity of the fill only (0.0–1.0)",
    "stroke-opacity": "Opacity of the stroke only (0.0–1.0)",
    "stroke-dasharray": "Dash pattern (e.g. '5,3')",
    "stroke-linecap": "Line cap style: butt | round | square",
    "stroke-linejoin": "Line join style: miter | round | bevel",
    "font-size": "Font size for text elements (e.g. '12px')",
    "font-family": "Font family name for text elements",
}

# ---------------------------------------------------------------------------
# Low-level parse / render


def parse_style_string(style_str: str) -> dict[str, str]:
    """Parse a CSS inline-style string into a property → value dict.

    Empty or whitespace-only declarations are ignored.

    Examples
    --------
    >>> parse_style_string("fill:red;stroke:black;stroke-width:2")
    {'fill': 'red', 'stroke': 'black', 'stroke-width': '2'}
    """
    result: dict[str, str] = {}
    for declaration in style_str.split(";"):
        declaration = declaration.strip()
        if not declaration or ":" not in declaration:
            continue
        prop, _, value = declaration.partition(":")
        prop = prop.strip()
        value = value.strip()
        if prop:
            result[prop] = value
    return result


def render_style_string(style_dict: dict[str, str]) -> str:
    """Render a property → value dict back into a CSS inline-style string.

    Properties are emitted in the same order as the input dict.

    Examples
    --------
    >>> render_style_string({'fill': 'red', 'stroke': 'black'})
    'fill:red;stroke:black'
    """
    return ";".join(f"{k}:{v}" for k, v in style_dict.items() if k and v is not None)


# ---------------------------------------------------------------------------
# Internal helpers


def _require_element(project: InkscapeProject, element_id: str):  # type: ignore[return]
    elem = project.find_by_id(element_id)
    if elem is None:
        raise KeyError(f"No element with id {element_id!r} found in project")
    return elem


def _update_style(project: InkscapeProject, element_id: str, prop: str, value: str) -> dict[str, Any]:
    """Set a single CSS property on an element's style string."""
    elem = _require_element(project, element_id)
    style = parse_style_string(elem.style)
    style[prop] = value
    elem.style = render_style_string(style)
    return {
        "action": "set_style_property",
        "element_id": element_id,
        "prop": prop,
        "value": value,
        "style": elem.style,
    }


# ---------------------------------------------------------------------------
# Public style setters


def set_fill(project: InkscapeProject, element_id: str, color: str) -> dict[str, Any]:
    """Set the fill colour of an element.

    Updates both ``element.fill`` and the ``fill`` property in
    ``element.style``.
    """
    elem = _require_element(project, element_id)
    elem.fill = color
    result = _update_style(project, element_id, "fill", color)
    result["action"] = "set_fill"
    return result


def set_stroke(
    project: InkscapeProject,
    element_id: str,
    color: str,
    width: float | None = None,
) -> dict[str, Any]:
    """Set the stroke colour and optionally the stroke width."""
    elem = _require_element(project, element_id)
    elem.stroke = color
    _update_style(project, element_id, "stroke", color)
    if width is not None:
        _update_style(project, element_id, "stroke-width", str(width))
    style = parse_style_string(elem.style)
    return {
        "action": "set_stroke",
        "element_id": element_id,
        "color": color,
        "width": width,
        "style": render_style_string(style),
    }


def set_opacity(
    project: InkscapeProject,
    element_id: str,
    opacity: float,
) -> dict[str, Any]:
    """Set the overall CSS ``opacity`` of an element (0.0–1.0)."""
    clamped = max(0.0, min(1.0, float(opacity)))
    return _update_style(project, element_id, "opacity", str(clamped))


def set_style_property(
    project: InkscapeProject,
    element_id: str,
    prop: str,
    value: str,
) -> dict[str, Any]:
    """Set an arbitrary CSS property on an element.

    Raises
    ------
    ValueError
        If *prop* is not in :data:`STYLE_PROPERTIES`.
    """
    if prop not in STYLE_PROPERTIES:
        raise ValueError(
            f"Unknown style property {prop!r}. "
            f"Allowed: {', '.join(sorted(STYLE_PROPERTIES))}"
        )
    return _update_style(project, element_id, prop, value)


def get_element_style(project: InkscapeProject, element_id: str) -> dict[str, Any]:
    """Return the element's style parsed into a property → value dict.

    Also includes the raw ``style`` string under the ``"raw"`` key.
    """
    elem = _require_element(project, element_id)
    parsed = parse_style_string(elem.style)
    return {
        "element_id": element_id,
        "raw": elem.style,
        "properties": parsed,
    }


def list_style_properties() -> list[dict[str, Any]]:
    """Return all entries in :data:`STYLE_PROPERTIES` as a list of dicts."""
    return [
        {"prop": prop, "description": desc}
        for prop, desc in STYLE_PROPERTIES.items()
    ]
