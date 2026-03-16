"""GIMP image project model.

Tracks the state of a GIMP image: dimensions, colour mode, resolution,
layer stack, and a log of operations performed in the current session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LayerInfo:
    """Describes a single layer within a GIMP image."""

    id: int
    name: str
    opacity: float = 1.0
    visible: bool = True
    blend_mode: str = "normal"
    group: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "opacity": self.opacity,
            "visible": self.visible,
            "blend_mode": self.blend_mode,
            "group": self.group,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayerInfo":
        return cls(
            id=int(data["id"]),
            name=str(data["name"]),
            opacity=float(data.get("opacity", 1.0)),
            visible=bool(data.get("visible", True)),
            blend_mode=str(data.get("blend_mode", "normal")),
            group=bool(data.get("group", False)),
        )


@dataclass
class GimpProject:
    """Complete description of an open GIMP image.

    Mirrors the subset of GIMP state that the CLI harness cares about.
    The layer list is ordered from top to bottom, matching GIMP's layer
    dialogue.
    """

    width: int
    height: int
    color_mode: str = "RGB"
    dpi: float = 72.0
    layers: list[LayerInfo] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    active_layer_index: int = 0

    # ------------------------------------------------------------------
    # Layer helpers

    @property
    def active_layer(self) -> LayerInfo | None:
        """Return the currently active layer, or *None* if the stack is empty."""
        if not self.layers:
            return None
        idx = self.active_layer_index
        if 0 <= idx < len(self.layers):
            return self.layers[idx]
        return None

    def add_layer(self, layer: LayerInfo) -> None:
        """Append *layer* to the top of the stack."""
        self.layers.append(layer)

    def remove_layer(self, layer_id: int) -> bool:
        """Remove the layer with *layer_id*.  Returns True if found."""
        before = len(self.layers)
        self.layers = [lyr for lyr in self.layers if lyr.id != layer_id]
        removed = len(self.layers) < before
        if removed:
            self.active_layer_index = min(
                self.active_layer_index, max(0, len(self.layers) - 1)
            )
        return removed

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "color_mode": self.color_mode,
            "dpi": self.dpi,
            "layers": [lyr.to_dict() for lyr in self.layers],
            "history": list(self.history),
            "active_layer_index": self.active_layer_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GimpProject":
        return cls(
            width=int(data["width"]),
            height=int(data["height"]),
            color_mode=str(data.get("color_mode", "RGB")),
            dpi=float(data.get("dpi", 72.0)),
            layers=[LayerInfo.from_dict(lyr) for lyr in data.get("layers", [])],
            history=list(data.get("history", [])),
            active_layer_index=int(data.get("active_layer_index", 0)),
        )
