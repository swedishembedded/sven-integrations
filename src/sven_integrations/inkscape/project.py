"""Inkscape SVG project model.

Represents an Inkscape document as a flat list of tracked SVG elements plus
the document canvas properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SvgElement:
    """Describes a single element within an Inkscape SVG document."""

    element_id: str
    tag: str = "g"
    label: str = ""
    stroke: str = "none"
    fill: str = "#000000"
    transform: str = ""
    style: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "tag": self.tag,
            "label": self.label,
            "stroke": self.stroke,
            "fill": self.fill,
            "transform": self.transform,
            "style": self.style,
            "attrs": dict(self.attrs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SvgElement":
        return cls(
            element_id=str(data["element_id"]),
            tag=str(data.get("tag", "g")),
            label=str(data.get("label", "")),
            stroke=str(data.get("stroke", "none")),
            fill=str(data.get("fill", "#000000")),
            transform=str(data.get("transform", "")),
            style=str(data.get("style", "")),
            attrs=dict(data.get("attrs", {})),
        )


@dataclass
class InkscapeProject:
    """Tracks the state of an open Inkscape SVG document."""

    svg_path: str | None = None
    width_mm: float = 210.0
    height_mm: float = 297.0
    viewbox: tuple[float, float, float, float] = (0.0, 0.0, 210.0, 297.0)
    elements: list[SvgElement] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Element helpers

    def add_element(self, element: SvgElement) -> None:
        """Add *element* to the tracked element list."""
        self.elements.append(element)

    def remove_element(self, element_id: str) -> bool:
        """Remove the element with *element_id*.  Returns True if found."""
        before = len(self.elements)
        self.elements = [e for e in self.elements if e.element_id != element_id]
        return len(self.elements) < before

    def find_by_id(self, element_id: str) -> SvgElement | None:
        """Return the first element matching *element_id*, or *None*."""
        for elem in self.elements:
            if elem.element_id == element_id:
                return elem
        return None

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "svg_path": self.svg_path,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "viewbox": list(self.viewbox),
            "elements": [e.to_dict() for e in self.elements],
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InkscapeProject":
        vb_raw = data.get("viewbox", [0, 0, 210, 297])
        vb: tuple[float, float, float, float] = (
            float(vb_raw[0]),
            float(vb_raw[1]),
            float(vb_raw[2]),
            float(vb_raw[3]),
        )
        return cls(
            svg_path=data.get("svg_path"),
            width_mm=float(data.get("width_mm", 210.0)),
            height_mm=float(data.get("height_mm", 297.0)),
            viewbox=vb,
            elements=[SvgElement.from_dict(e) for e in data.get("elements", [])],
            data=dict(data.get("data", {})),
        )
