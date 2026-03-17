"""Path boolean operations and shape-to-path conversion for the Inkscape harness.

Boolean operations (union, intersection, difference, exclusion) are
recorded as metadata on a new synthetic ``path`` element; the source
elements are removed.  Actual geometric computation would require
Inkscape's backend; this module manages the element registry and
provides the action vocabulary.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..project import InkscapeProject, SvgElement

# ---------------------------------------------------------------------------
# Available path boolean operations

_PATH_OPERATIONS: list[dict[str, Any]] = [
    {
        "name": "union",
        "inkscape_action": "path-union",
        "description": "Combine two paths into one (logical OR of filled areas)",
    },
    {
        "name": "intersection",
        "inkscape_action": "path-intersection",
        "description": "Keep only the overlapping region (logical AND)",
    },
    {
        "name": "difference",
        "inkscape_action": "path-difference",
        "description": "Subtract the second path from the first (A minus B)",
    },
    {
        "name": "exclusion",
        "inkscape_action": "path-exclusion",
        "description": "Non-overlapping areas only (logical XOR)",
    },
]


def list_path_operations() -> list[dict[str, Any]]:
    """Return the available boolean path operations with their Inkscape action names."""
    return list(_PATH_OPERATIONS)


# ---------------------------------------------------------------------------
# Internal helpers


def _require_element(project: InkscapeProject, element_id: str) -> SvgElement:
    elem = project.find_by_id(element_id)
    if elem is None:
        raise KeyError(f"No element with id {element_id!r} in project")
    return elem


def _record_boolean_op(
    project: InkscapeProject,
    op_name: str,
    id_a: str,
    id_b: str,
    result_name: str | None,
) -> dict[str, Any]:
    """Record a boolean path operation as a new element, removing sources."""
    elem_a = _require_element(project, id_a)
    _require_element(project, id_b)  # validate id_b exists

    result_id = str(uuid.uuid4())[:8]
    result_elem = SvgElement(
        element_id=result_id,
        tag="path",
        label=result_name or f"{op_name}_{id_a}_{id_b}",
        fill=elem_a.fill,
        stroke=elem_a.stroke,
        style=elem_a.style,
        attrs={
            "path_op": op_name,
            "source_a": id_a,
            "source_b": id_b,
            "d": "",  # placeholder; actual path computed by Inkscape
        },
    )

    project.remove_element(id_a)
    project.remove_element(id_b)
    project.add_element(result_elem)

    return {
        "action": f"path_{op_name}",
        "result_id": result_id,
        "source_a": id_a,
        "source_b": id_b,
        "inkscape_action": f"path-{op_name}",
    }


# ---------------------------------------------------------------------------
# Public path boolean operations


def path_union(
    project: InkscapeProject,
    id_a: str,
    id_b: str,
    result_name: str | None = None,
) -> dict[str, Any]:
    """Record a path union of *id_a* and *id_b*."""
    return _record_boolean_op(project, "union", id_a, id_b, result_name)


def path_intersection(
    project: InkscapeProject,
    id_a: str,
    id_b: str,
    result_name: str | None = None,
) -> dict[str, Any]:
    """Record a path intersection of *id_a* and *id_b*."""
    return _record_boolean_op(project, "intersection", id_a, id_b, result_name)


def path_difference(
    project: InkscapeProject,
    id_a: str,
    id_b: str,
    result_name: str | None = None,
) -> dict[str, Any]:
    """Record a path difference (A minus B)."""
    return _record_boolean_op(project, "difference", id_a, id_b, result_name)


def path_exclusion(
    project: InkscapeProject,
    id_a: str,
    id_b: str,
    result_name: str | None = None,
) -> dict[str, Any]:
    """Record a path exclusion (XOR) of *id_a* and *id_b*."""
    return _record_boolean_op(project, "exclusion", id_a, id_b, result_name)


# ---------------------------------------------------------------------------
# Shape-to-path conversion


def shape_to_path_data(element: SvgElement) -> str:
    """Convert a simple shape element to an SVG path ``d`` string.

    Supports ``rect``, ``circle``, ``ellipse``, and ``line``.
    For ``path`` and ``polygon`` elements the existing data is returned.
    Raises :exc:`ValueError` for unsupported tags.
    """
    tag = element.tag
    a = element.attrs

    if tag == "path":
        return str(a.get("d", ""))

    if tag == "polygon":
        pts_str = str(a.get("points", ""))
        if not pts_str:
            return ""
        # Convert "x1,y1 x2,y2 ..." into M x1,y1 L x2,y2 ... Z
        pairs = pts_str.strip().split()
        if not pairs:
            return ""
        first, rest = pairs[0], pairs[1:]
        d_parts = [f"M{first}"]
        d_parts.extend(f"L{p}" for p in rest)
        d_parts.append("Z")
        return " ".join(d_parts)

    if tag == "rect":
        x = float(a.get("x", 0))
        y = float(a.get("y", 0))
        w = float(a.get("width", 0))
        h = float(a.get("height", 0))
        rx = float(a.get("rx", 0))
        ry = float(a.get("ry", rx))
        if rx == 0 and ry == 0:
            return (
                f"M{x},{y} L{x + w},{y} L{x + w},{y + h} L{x},{y + h} Z"
            )
        # Rounded rectangle approximation using arc commands
        rx = min(rx, w / 2)
        ry = min(ry, h / 2)
        return (
            f"M{x + rx},{y} "
            f"L{x + w - rx},{y} "
            f"A{rx},{ry} 0 0 1 {x + w},{y + ry} "
            f"L{x + w},{y + h - ry} "
            f"A{rx},{ry} 0 0 1 {x + w - rx},{y + h} "
            f"L{x + rx},{y + h} "
            f"A{rx},{ry} 0 0 1 {x},{y + h - ry} "
            f"L{x},{y + ry} "
            f"A{rx},{ry} 0 0 1 {x + rx},{y} Z"
        )

    if tag == "circle":
        cx = float(a.get("cx", 0))
        cy = float(a.get("cy", 0))
        r = float(a.get("r", 0))
        # Approximate circle with four cubic Bézier arcs (k ≈ 0.5523)
        k = 0.5522847498
        kr = k * r
        return (
            f"M{cx},{cy - r} "
            f"C{cx + kr},{cy - r} {cx + r},{cy - kr} {cx + r},{cy} "
            f"C{cx + r},{cy + kr} {cx + kr},{cy + r} {cx},{cy + r} "
            f"C{cx - kr},{cy + r} {cx - r},{cy + kr} {cx - r},{cy} "
            f"C{cx - r},{cy - kr} {cx - kr},{cy - r} {cx},{cy - r} Z"
        )

    if tag == "ellipse":
        cx = float(a.get("cx", 0))
        cy = float(a.get("cy", 0))
        rx = float(a.get("rx", 0))
        ry = float(a.get("ry", 0))
        k = 0.5522847498
        krx = k * rx
        kry = k * ry
        return (
            f"M{cx},{cy - ry} "
            f"C{cx + krx},{cy - ry} {cx + rx},{cy - kry} {cx + rx},{cy} "
            f"C{cx + rx},{cy + kry} {cx + krx},{cy + ry} {cx},{cy + ry} "
            f"C{cx - krx},{cy + ry} {cx - rx},{cy + kry} {cx - rx},{cy} "
            f"C{cx - rx},{cy - kry} {cx - krx},{cy - ry} {cx},{cy - ry} Z"
        )

    if tag == "line":
        x1 = float(a.get("x1", 0))
        y1 = float(a.get("y1", 0))
        x2 = float(a.get("x2", 0))
        y2 = float(a.get("y2", 0))
        return f"M{x1},{y1} L{x2},{y2}"

    raise ValueError(f"Unsupported shape tag for path conversion: {tag!r}")


def convert_to_path(project: InkscapeProject, element_id: str) -> dict[str, Any]:
    """Convert a shape element to a ``path`` element in-place.

    Computes the SVG path data via :func:`shape_to_path_data`, updates the
    element's ``tag`` to ``"path"``, and stores the ``d`` attribute.
    """
    elem = _require_element(project, element_id)
    previous_tag = elem.tag

    if previous_tag == "path":
        return {
            "action": "convert_to_path",
            "element_id": element_id,
            "previous_tag": "path",
            "note": "already a path",
        }

    d = shape_to_path_data(elem)
    elem.tag = "path"
    elem.attrs = {"d": d}

    return {
        "action": "convert_to_path",
        "element_id": element_id,
        "previous_tag": previous_tag,
        "d": d,
    }
