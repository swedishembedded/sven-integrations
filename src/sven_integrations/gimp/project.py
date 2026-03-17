"""GIMP image project model.

Tracks the state of a GIMP image: dimensions, colour mode, resolution,
layer stack, and a log of operations performed in the current session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DrawOperation:
    """A single drawing operation stored on a layer."""

    op_type: str  # text, rect, ellipse, line
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"op_type": self.op_type, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DrawOperation":
        return cls(
            op_type=str(data["op_type"]),
            params=dict(data.get("params", {})),
        )


@dataclass
class FilterInfo:
    """A filter recorded on a layer, applied during render."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FilterInfo":
        return cls(
            name=str(data["name"]),
            params=dict(data.get("params", {})),
        )


@dataclass
class LayerInfo:
    """Describes a single layer within a GIMP image."""

    id: int
    name: str
    opacity: float = 1.0
    visible: bool = True
    blend_mode: str = "normal"
    group: bool = False
    source: str | None = None  # Path to image file for image layers
    offset_x: int = 0
    offset_y: int = 0
    width: int | None = None
    height: int | None = None
    fill_color: str | None = None  # Background fill: "white", "black", "transparent", or hex
    draw_ops: list[DrawOperation] = field(default_factory=list)
    filters: list[FilterInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "opacity": self.opacity,
            "visible": self.visible,
            "blend_mode": self.blend_mode,
            "group": self.group,
        }
        if self.source is not None:
            d["source"] = self.source
        if self.offset_x or self.offset_y:
            d["offset_x"] = self.offset_x
            d["offset_y"] = self.offset_y
        if self.width is not None:
            d["width"] = self.width
        if self.height is not None:
            d["height"] = self.height
        if self.fill_color is not None:
            d["fill_color"] = self.fill_color
        if self.draw_ops:
            d["draw_ops"] = [op.to_dict() for op in self.draw_ops]
        if self.filters:
            d["filters"] = [f.to_dict() for f in self.filters]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayerInfo":
        return cls(
            id=int(data["id"]),
            name=str(data["name"]),
            opacity=float(data.get("opacity", 1.0)),
            visible=bool(data.get("visible", True)),
            blend_mode=str(data.get("blend_mode", "normal")),
            group=bool(data.get("group", False)),
            source=data.get("source"),
            offset_x=int(data.get("offset_x", 0)),
            offset_y=int(data.get("offset_y", 0)),
            width=data.get("width"),
            height=data.get("height"),
            fill_color=data.get("fill_color"),
            draw_ops=[DrawOperation.from_dict(op) for op in data.get("draw_ops", [])],
            filters=[FilterInfo.from_dict(f) for f in data.get("filters", [])],
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
    name: str = "untitled"
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

    def _next_layer_id(self) -> int:
        """Return the next available layer ID."""
        existing = [lyr.id for lyr in self.layers]
        return max(existing, default=-1) + 1

    def add_layer_from_file(
        self,
        path: str,
        name: str | None = None,
        position: int | None = None,
        opacity: float = 1.0,
        blend_mode: str = "normal",
    ) -> LayerInfo:
        """Add a layer from an image file. Returns the new layer."""
        import os
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image file not found: {path}")
        layer_name = name or os.path.basename(path)
        layer = LayerInfo(
            id=self._next_layer_id(),
            name=layer_name,
            source=os.path.abspath(path),
            opacity=opacity,
            blend_mode=blend_mode,
        )
        if position is not None:
            pos = max(0, min(position, len(self.layers)))
            self.layers.insert(pos, layer)
        else:
            self.layers.insert(0, layer)
        return layer

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

    def remove_layer_at_index(self, index: int) -> LayerInfo | None:
        """Remove the layer at *index*. Returns the removed layer or None."""
        if index < 0 or index >= len(self.layers):
            return None
        removed = self.layers.pop(index)
        self.active_layer_index = min(
            self.active_layer_index, max(0, len(self.layers) - 1)
        )
        return removed

    def duplicate_layer_at(self, index: int) -> LayerInfo | None:
        """Duplicate the layer at *index*. Returns the new layer or None."""
        if index < 0 or index >= len(self.layers):
            return None
        orig = self.layers[index]
        dup = LayerInfo(
            id=self._next_layer_id(),
            name=f"{orig.name} copy",
            opacity=orig.opacity,
            visible=orig.visible,
            blend_mode=orig.blend_mode,
            source=orig.source,
            offset_x=orig.offset_x,
            offset_y=orig.offset_y,
            width=orig.width,
            height=orig.height,
            fill_color=orig.fill_color,
            draw_ops=list(orig.draw_ops),
            filters=list(orig.filters),
        )
        self.layers.insert(index, dup)
        return dup

    def move_layer(self, index: int, to_index: int) -> bool:
        """Move layer from *index* to *to_index*. Returns True if valid."""
        if index < 0 or index >= len(self.layers) or to_index < 0 or to_index >= len(self.layers):
            return False
        if index == to_index:
            return True
        layer = self.layers.pop(index)
        self.layers.insert(to_index, layer)
        return True

    def set_layer_property(self, index: int, prop: str, value: Any) -> bool:
        """Set a layer property. Returns True if valid."""
        if index < 0 or index >= len(self.layers):
            return False
        layer = self.layers[index]
        if prop == "name":
            layer.name = str(value)
        elif prop == "opacity":
            layer.opacity = float(value)
        elif prop == "visible":
            layer.visible = str(value).lower() in ("true", "1", "yes")
        elif prop == "mode":
            layer.blend_mode = str(value)
        elif prop == "offset_x":
            layer.offset_x = int(value)
        elif prop == "offset_y":
            layer.offset_y = int(value)
        elif prop == "fill_color":
            layer.fill_color = str(value)
        else:
            return False
        return True

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "width": self.width,
            "height": self.height,
            "color_mode": self.color_mode,
            "dpi": self.dpi,
            "name": self.name,
            "layers": [lyr.to_dict() for lyr in self.layers],
            "history": list(self.history),
            "active_layer_index": self.active_layer_index,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GimpProject":
        return cls(
            width=int(data["width"]),
            height=int(data["height"]),
            color_mode=str(data.get("color_mode", "RGB")),
            dpi=float(data.get("dpi", 72.0)),
            name=str(data.get("name", "untitled")),
            layers=[LayerInfo.from_dict(lyr) for lyr in data.get("layers", [])],
            history=list(data.get("history", [])),
            active_layer_index=int(data.get("active_layer_index", 0)),
        )
