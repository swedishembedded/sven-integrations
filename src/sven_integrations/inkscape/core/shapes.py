"""Shape creation helpers for the Inkscape harness.

Each ``add_*`` function inserts a new :class:`SvgElement` into
``project.elements`` and returns a result dict describing what was added.
Shape-specific SVG attributes are stored in ``element.attrs``; CSS style
properties in ``element.style``.
"""

from __future__ import annotations

import math
from typing import Any

from ..project import InkscapeProject, SvgElement

# ---------------------------------------------------------------------------
# Internal helpers


def _next_id(project: InkscapeProject, prefix: str = "elem") -> str:
    """Return a unique element-id string, incrementing a per-project counter."""
    counter: int = project.data.get("_id_counter", 0) + 1
    project.data["_id_counter"] = counter
    return f"{prefix}_{counter}"


def _build_style(fill: str, stroke: str, stroke_width: float) -> str:
    """Compose a minimal CSS style string from common paint properties."""
    return f"fill:{fill};stroke:{stroke};stroke-width:{stroke_width}"


def _make_element(
    project: InkscapeProject,
    tag: str,
    name: str | None,
    fill: str,
    stroke: str,
    stroke_width: float,
    layer_index: int,
    **attrs: Any,
) -> SvgElement:
    """Allocate an id, build an SvgElement, and register it in *project*."""
    elem_id = _next_id(project, prefix=tag)
    elem = SvgElement(
        element_id=elem_id,
        tag=tag,
        label=name or "",
        fill=fill,
        stroke=stroke,
        style=_build_style(fill, stroke, stroke_width),
        attrs={k: v for k, v in attrs.items() if v is not None},
    )
    project.add_element(elem)

    # Associate with layer if one is nominated
    layers: list[dict[str, Any]] = project.data.get("layers", [])
    if layers and 0 <= layer_index < len(layers):
        layers[layer_index].setdefault("element_ids", []).append(elem_id)

    return elem


def _result(action: str, elem: SvgElement, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "action": action,
        "element_id": elem.element_id,
        "tag": elem.tag,
        "label": elem.label,
    }
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------
# Public shape adders


def add_rect(
    project: InkscapeProject,
    x: float,
    y: float,
    width: float,
    height: float,
    rx: float = 0,
    ry: float = 0,
    name: str | None = None,
    fill: str = "none",
    stroke: str = "black",
    stroke_width: float = 1.0,
    layer_index: int = 0,
) -> dict[str, Any]:
    """Add a rectangle to *project*."""
    attrs: dict[str, Any] = {"x": x, "y": y, "width": width, "height": height}
    if rx:
        attrs["rx"] = rx
    if ry:
        attrs["ry"] = ry
    elem = _make_element(project, "rect", name, fill, stroke, stroke_width, layer_index, **attrs)
    return _result("add_shape", elem, {"x": x, "y": y, "width": width, "height": height})


def add_circle(
    project: InkscapeProject,
    cx: float,
    cy: float,
    r: float,
    name: str | None = None,
    fill: str = "none",
    stroke: str = "black",
    stroke_width: float = 1.0,
    layer_index: int = 0,
) -> dict[str, Any]:
    """Add a circle to *project*."""
    elem = _make_element(
        project, "circle", name, fill, stroke, stroke_width, layer_index,
        cx=cx, cy=cy, r=r,
    )
    return _result("add_shape", elem, {"cx": cx, "cy": cy, "r": r})


def add_ellipse(
    project: InkscapeProject,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    name: str | None = None,
    fill: str = "none",
    stroke: str = "black",
    stroke_width: float = 1.0,
) -> dict[str, Any]:
    """Add an ellipse to *project*."""
    elem = _make_element(
        project, "ellipse", name, fill, stroke, stroke_width, 0,
        cx=cx, cy=cy, rx=rx, ry=ry,
    )
    return _result("add_shape", elem, {"cx": cx, "cy": cy, "rx": rx, "ry": ry})


def add_line(
    project: InkscapeProject,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    name: str | None = None,
    stroke: str = "black",
    stroke_width: float = 1.0,
) -> dict[str, Any]:
    """Add a straight line to *project*."""
    elem = _make_element(
        project, "line", name, "none", stroke, stroke_width, 0,
        x1=x1, y1=y1, x2=x2, y2=y2,
    )
    return _result("add_shape", elem, {"x1": x1, "y1": y1, "x2": x2, "y2": y2})


def add_polygon(
    project: InkscapeProject,
    points: list[tuple[float, float]],
    name: str | None = None,
    fill: str = "none",
    stroke: str = "black",
    stroke_width: float = 1.0,
) -> dict[str, Any]:
    """Add a closed polygon to *project*.

    *points* is a list of ``(x, y)`` coordinate tuples.
    """
    pts_str = " ".join(f"{x},{y}" for x, y in points)
    elem = _make_element(
        project, "polygon", name, fill, stroke, stroke_width, 0,
        points=pts_str,
    )
    return _result("add_shape", elem, {"point_count": len(points)})


def add_path(
    project: InkscapeProject,
    d: str,
    name: str | None = None,
    fill: str = "none",
    stroke: str = "black",
    stroke_width: float = 1.0,
) -> dict[str, Any]:
    """Add a path element with the given SVG path data string *d*."""
    elem = _make_element(
        project, "path", name, fill, stroke, stroke_width, 0,
        d=d,
    )
    return _result("add_shape", elem, {"d_length": len(d)})


def add_star(
    project: InkscapeProject,
    cx: float,
    cy: float,
    num_points: int,
    outer_radius: float,
    inner_radius: float,
    name: str | None = None,
    fill: str = "none",
    stroke: str = "black",
) -> dict[str, Any]:
    """Add a regular star polygon to *project*.

    Computes alternating outer/inner vertices around *(cx, cy)* and
    encodes them as an SVG path ``d`` string.

    Parameters
    ----------
    num_points:
        Number of star tips (e.g. 5 for a five-pointed star).
    outer_radius:
        Distance from centre to tip vertices.
    inner_radius:
        Distance from centre to valley vertices.
    """
    if num_points < 3:
        raise ValueError("num_points must be at least 3")

    total_vertices = num_points * 2
    coords: list[str] = []
    for i in range(total_vertices):
        # Alternate between outer and inner radius
        radius = outer_radius if i % 2 == 0 else inner_radius
        # Start tips pointing upward (offset by -π/2)
        angle = math.pi * i / num_points - math.pi / 2
        vx = cx + radius * math.cos(angle)
        vy = cy + radius * math.sin(angle)
        cmd = "M" if i == 0 else "L"
        coords.append(f"{cmd}{vx:.4f},{vy:.4f}")
    coords.append("Z")

    d = " ".join(coords)
    elem = _make_element(
        project, "path", name, fill, stroke, 1.0, 0,
        d=d,
    )
    return _result(
        "add_shape",
        elem,
        {"num_points": num_points, "outer_radius": outer_radius, "inner_radius": inner_radius},
    )


# ---------------------------------------------------------------------------
# Object listing


def list_objects(project: InkscapeProject) -> list[dict[str, Any]]:
    """Return a summary list of all elements tracked in *project*."""
    result: list[dict[str, Any]] = []
    for elem in project.elements:
        entry: dict[str, Any] = {
            "element_id": elem.element_id,
            "tag": elem.tag,
            "label": elem.label,
            "fill": elem.fill,
            "stroke": elem.stroke,
            "style": elem.style,
            "transform": elem.transform,
        }
        # Include key geometric attrs for quick inspection
        for key in ("x", "y", "width", "height", "cx", "cy", "r", "rx", "ry", "d"):
            if key in elem.attrs:
                entry[key] = elem.attrs[key]
        result.append(entry)
    return result
