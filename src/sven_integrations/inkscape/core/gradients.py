"""Gradient definitions and application for the Inkscape harness.

Gradients are stored as dicts under ``project.data["gradients"]``.
The :class:`GradientStop` and :class:`GradientDef` dataclasses provide
typed access; the canonical store is always plain dicts so they survive
JSON serialisation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from ..project import InkscapeProject

# ---------------------------------------------------------------------------
# Dataclasses


@dataclass
class GradientStop:
    """A single colour stop in a gradient definition."""

    offset: float  # 0.0–1.0
    color: str
    opacity: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"offset": self.offset, "color": self.color, "opacity": self.opacity}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GradientStop":
        return cls(
            offset=float(data.get("offset", 0.0)),
            color=str(data.get("color", "black")),
            opacity=float(data.get("opacity", 1.0)),
        )


@dataclass
class GradientDef:
    """A complete gradient definition (linear or radial)."""

    gradient_id: str
    kind: Literal["linear", "radial"]
    name: str
    stops: list[GradientStop] = field(default_factory=list)

    # Linear gradient geometry (normalised 0–1 by default)
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 0.0

    # Radial gradient geometry
    cx: float = 0.5
    cy: float = 0.5
    r: float = 0.5
    fx: float = 0.5
    fy: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "gradient_id": self.gradient_id,
            "kind": self.kind,
            "name": self.name,
            "stops": [s.to_dict() for s in self.stops],
        }
        if self.kind == "linear":
            base.update({"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2})
        else:
            base.update({"cx": self.cx, "cy": self.cy, "r": self.r, "fx": self.fx, "fy": self.fy})
        return base

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GradientDef":
        stops = [GradientStop.from_dict(s) for s in data.get("stops", [])]
        kind: Literal["linear", "radial"] = (
            "radial" if data.get("kind") == "radial" else "linear"
        )
        return cls(
            gradient_id=str(data.get("gradient_id", "")),
            kind=kind,
            name=str(data.get("name", "")),
            stops=stops,
            x1=float(data.get("x1", 0.0)),
            y1=float(data.get("y1", 0.0)),
            x2=float(data.get("x2", 1.0)),
            y2=float(data.get("y2", 0.0)),
            cx=float(data.get("cx", 0.5)),
            cy=float(data.get("cy", 0.5)),
            r=float(data.get("r", 0.5)),
            fx=float(data.get("fx", 0.5)),
            fy=float(data.get("fy", 0.5)),
        )


# ---------------------------------------------------------------------------
# Internal helpers


def _gradients(project: InkscapeProject) -> list[dict[str, Any]]:
    return project.data.setdefault("gradients", [])


def _parse_stops(stops_raw: list[dict[str, Any]]) -> list[GradientStop]:
    """Normalise a list of raw stop dicts."""
    return [GradientStop.from_dict(s) for s in stops_raw]


def _check_index(gradients: list[dict[str, Any]], index: int) -> None:
    if not (0 <= index < len(gradients)):
        raise IndexError(f"Gradient index {index} out of range (0–{len(gradients) - 1})")


# ---------------------------------------------------------------------------
# Public gradient functions


def add_linear_gradient(
    project: InkscapeProject,
    stops: list[dict[str, Any]],
    x1: float = 0.0,
    y1: float = 0.0,
    x2: float = 1.0,
    y2: float = 0.0,
    name: str | None = None,
) -> dict[str, Any]:
    """Add a linear gradient to *project* and return its index.

    Parameters
    ----------
    stops:
        List of dicts with ``offset`` (0–1), ``color``, and optionally
        ``opacity`` keys.
    x1, y1, x2, y2:
        Gradient vector in normalised coordinates (0–1).
    name:
        Human-readable label stored alongside the gradient.
    """
    grad_id = str(uuid.uuid4())[:8]
    grad = GradientDef(
        gradient_id=grad_id,
        kind="linear",
        name=name or f"linear_{grad_id}",
        stops=_parse_stops(stops),
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
    )
    grads = _gradients(project)
    grads.append(grad.to_dict())
    index = len(grads) - 1

    return {
        "action": "add_linear_gradient",
        "index": index,
        "gradient_id": grad_id,
        "gradient": grad.to_dict(),
    }


def add_radial_gradient(
    project: InkscapeProject,
    stops: list[dict[str, Any]],
    cx: float = 0.5,
    cy: float = 0.5,
    r: float = 0.5,
    fx: float | None = None,
    fy: float | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Add a radial gradient to *project* and return its index.

    Parameters
    ----------
    stops:
        List of dicts with ``offset`` (0–1), ``color``, and optionally
        ``opacity`` keys.
    cx, cy:
        Centre of the gradient circle (normalised 0–1).
    r:
        Radius of the gradient circle (normalised 0–1).
    fx, fy:
        Focal point.  Defaults to ``(cx, cy)``.
    name:
        Human-readable label.
    """
    effective_fx = cx if fx is None else fx
    effective_fy = cy if fy is None else fy

    grad_id = str(uuid.uuid4())[:8]
    grad = GradientDef(
        gradient_id=grad_id,
        kind="radial",
        name=name or f"radial_{grad_id}",
        stops=_parse_stops(stops),
        cx=cx,
        cy=cy,
        r=r,
        fx=effective_fx,
        fy=effective_fy,
    )
    grads = _gradients(project)
    grads.append(grad.to_dict())
    index = len(grads) - 1

    return {
        "action": "add_radial_gradient",
        "index": index,
        "gradient_id": grad_id,
        "gradient": grad.to_dict(),
    }


def apply_gradient(
    project: InkscapeProject,
    gradient_index: int,
    element_id: str,
    target: str = "fill",
) -> dict[str, Any]:
    """Apply gradient *gradient_index* to an element's fill or stroke.

    Sets ``element.fill`` (or ``element.stroke``) to the gradient
    reference string ``url(#<gradient_id>)`` and updates the element's
    style string accordingly.
    """
    grads = _gradients(project)
    _check_index(grads, gradient_index)

    elem = project.find_by_id(element_id)
    if elem is None:
        raise KeyError(f"No element with id {element_id!r}")

    grad_dict = grads[gradient_index]
    grad_ref = f"url(#{grad_dict['gradient_id']})"

    if target == "fill":
        elem.fill = grad_ref
    elif target == "stroke":
        elem.stroke = grad_ref
    else:
        raise ValueError(f"target must be 'fill' or 'stroke', got {target!r}")

    # Update the style string
    from .styles import parse_style_string, render_style_string
    style = parse_style_string(elem.style)
    style[target] = grad_ref
    elem.style = render_style_string(style)

    return {
        "action": "apply_gradient",
        "element_id": element_id,
        "gradient_index": gradient_index,
        "gradient_id": grad_dict["gradient_id"],
        "target": target,
        "ref": grad_ref,
    }


def list_gradients(project: InkscapeProject) -> dict[str, Any]:
    """Return all gradients in *project* with their indices."""
    grads = _gradients(project)
    return {
        "gradient_count": len(grads),
        "gradients": [{"index": i, **g} for i, g in enumerate(grads)],
    }


def get_gradient(project: InkscapeProject, index: int) -> dict[str, Any]:
    """Return the gradient dict at *index* with its index included."""
    grads = _gradients(project)
    _check_index(grads, index)
    return {"index": index, **grads[index]}


def remove_gradient(project: InkscapeProject, index: int) -> dict[str, Any]:
    """Remove the gradient at *index* from *project*.

    Does *not* update element style strings that may reference this
    gradient — callers should handle that if needed.
    """
    grads = _gradients(project)
    _check_index(grads, index)
    removed = grads.pop(index)
    return {
        "action": "remove_gradient",
        "removed_index": index,
        "removed_gradient_id": removed.get("gradient_id", ""),
    }


def build_gradient_svg(gradient: dict[str, Any]) -> str:
    """Render a gradient dict as an SVG ``<linearGradient>`` or ``<radialGradient>`` XML string.

    The returned string is a self-contained ``<defs>`` block ready to be
    embedded in an SVG document.
    """
    grad = GradientDef.from_dict(gradient)

    stop_tags: list[str] = []
    for stop in grad.stops:
        pct = f"{stop.offset * 100:.4g}%"
        stop_tags.append(
            f'  <stop offset="{pct}" style="stop-color:{stop.color};stop-opacity:{stop.opacity}"/>'
        )
    stops_xml = "\n".join(stop_tags)

    if grad.kind == "linear":
        attrs = (
            f'id="{grad.gradient_id}" '
            f'x1="{grad.x1}" y1="{grad.y1}" '
            f'x2="{grad.x2}" y2="{grad.y2}" '
            f'gradientUnits="objectBoundingBox"'
        )
        inner = f"<linearGradient {attrs}>\n{stops_xml}\n</linearGradient>"
    else:
        attrs = (
            f'id="{grad.gradient_id}" '
            f'cx="{grad.cx}" cy="{grad.cy}" r="{grad.r}" '
            f'fx="{grad.fx}" fy="{grad.fy}" '
            f'gradientUnits="objectBoundingBox"'
        )
        inner = f"<radialGradient {attrs}>\n{stops_xml}\n</radialGradient>"

    return f"<defs>\n{inner}\n</defs>"
