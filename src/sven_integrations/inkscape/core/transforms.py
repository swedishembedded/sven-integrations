"""SVG transform helpers for the Inkscape harness.

Transforms are stored as SVG transform strings on ``element.transform``.
All operations parse the existing string, append or overwrite an entry,
and write the result back.
"""

from __future__ import annotations

import re
from typing import Any

from ..project import InkscapeProject

# ---------------------------------------------------------------------------
# Internal: parse / serialise SVG transform strings

_TRANSFORM_RE = re.compile(
    r"(?P<func>[a-zA-Z]+)\s*\((?P<args>[^)]*)\)"
)


def parse_transform_string(transform_str: str) -> list[dict[str, Any]]:
    """Parse an SVG transform attribute into a list of operation dicts.

    Each dict has keys ``"func"`` (str) and ``"args"`` (list[float]).

    Examples
    --------
    >>> parse_transform_string("translate(10,20) rotate(45)")
    [{'func': 'translate', 'args': [10.0, 20.0]}, {'func': 'rotate', 'args': [45.0]}]
    """
    ops: list[dict[str, Any]] = []
    for match in _TRANSFORM_RE.finditer(transform_str):
        func = match.group("func")
        raw_args = match.group("args").strip()
        if raw_args:
            # Values may be space- or comma-separated (or both)
            args = [float(v) for v in re.split(r"[\s,]+", raw_args) if v]
        else:
            args = []
        ops.append({"func": func, "args": args})
    return ops


def serialize_transform(operations: list[dict[str, Any]]) -> str:
    """Serialise a list of ``{func, args}`` dicts back to an SVG string.

    Examples
    --------
    >>> serialize_transform([{'func': 'translate', 'args': [5.0, 10.0]}])
    'translate(5.0,10.0)'
    """
    parts: list[str] = []
    for op in operations:
        func = op["func"]
        args = op.get("args", [])
        if args:
            args_str = ",".join(str(a) for a in args)
            parts.append(f"{func}({args_str})")
        else:
            parts.append(f"{func}()")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers


def _require_element(project: InkscapeProject, element_id: str):  # type: ignore[return]
    elem = project.find_by_id(element_id)
    if elem is None:
        raise KeyError(f"No element with id {element_id!r} found in project")
    return elem


def _append_op(
    project: InkscapeProject,
    element_id: str,
    func: str,
    args: list[float],
) -> dict[str, Any]:
    """Append a transform operation to an element's transform string."""
    elem = _require_element(project, element_id)
    ops = parse_transform_string(elem.transform)
    ops.append({"func": func, "args": args})
    elem.transform = serialize_transform(ops)
    return {
        "action": "append_transform",
        "element_id": element_id,
        "func": func,
        "args": args,
        "transform": elem.transform,
    }


# ---------------------------------------------------------------------------
# Public transform operations


def translate(
    project: InkscapeProject,
    element_id: str,
    tx: float,
    ty: float,
) -> dict[str, Any]:
    """Append a ``translate(tx, ty)`` to the element's transform."""
    result = _append_op(project, element_id, "translate", [tx, ty])
    result["action"] = "translate"
    return result


def rotate(
    project: InkscapeProject,
    element_id: str,
    angle: float,
    cx: float = 0.0,
    cy: float = 0.0,
) -> dict[str, Any]:
    """Append a ``rotate(angle[, cx, cy])`` to the element's transform.

    When *(cx, cy)* is ``(0, 0)`` only the angle is included in the
    transform string (SVG semantics: rotation around the origin).
    """
    if cx == 0.0 and cy == 0.0:
        args: list[float] = [angle]
    else:
        args = [angle, cx, cy]
    result = _append_op(project, element_id, "rotate", args)
    result["action"] = "rotate"
    return result


def scale(
    project: InkscapeProject,
    element_id: str,
    sx: float,
    sy: float | None = None,
) -> dict[str, Any]:
    """Append a ``scale(sx[, sy])`` to the element's transform.

    When *sy* is ``None`` it defaults to *sx* (uniform scaling).
    """
    effective_sy = sx if sy is None else sy
    if sx == effective_sy:
        args: list[float] = [sx]
    else:
        args = [sx, effective_sy]
    result = _append_op(project, element_id, "scale", args)
    result["action"] = "scale"
    result["sy"] = effective_sy
    return result


def skew_x(
    project: InkscapeProject,
    element_id: str,
    angle: float,
) -> dict[str, Any]:
    """Append a ``skewX(angle)`` shear to the element's transform."""
    result = _append_op(project, element_id, "skewX", [angle])
    result["action"] = "skew_x"
    return result


def skew_y(
    project: InkscapeProject,
    element_id: str,
    angle: float,
) -> dict[str, Any]:
    """Append a ``skewY(angle)`` shear to the element's transform."""
    result = _append_op(project, element_id, "skewY", [angle])
    result["action"] = "skew_y"
    return result


def set_transform(
    project: InkscapeProject,
    element_id: str,
    transform: str,
) -> dict[str, Any]:
    """Overwrite the element's transform with the given SVG string."""
    elem = _require_element(project, element_id)
    elem.transform = transform
    return {
        "action": "set_transform",
        "element_id": element_id,
        "transform": transform,
    }


def get_transform(
    project: InkscapeProject,
    element_id: str,
) -> dict[str, Any]:
    """Return the element's current transform as raw string and parsed list."""
    elem = _require_element(project, element_id)
    return {
        "element_id": element_id,
        "raw_string": elem.transform,
        "operations": parse_transform_string(elem.transform),
    }


def clear_transform(
    project: InkscapeProject,
    element_id: str,
) -> dict[str, Any]:
    """Remove all transforms from an element."""
    elem = _require_element(project, element_id)
    previous = elem.transform
    elem.transform = ""
    return {
        "action": "clear_transform",
        "element_id": element_id,
        "previous": previous,
    }
