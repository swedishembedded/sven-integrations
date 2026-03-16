"""Layer management for the Inkscape harness.

Layers are stored as a list of dicts under ``project.data["layers"]``.
The :class:`InkscapeLayer` dataclass mirrors that dict structure and is
used for type-annotated access, but the canonical store is always the
plain dict list so it survives JSON serialisation through
:class:`~sven_integrations.inkscape.project.InkscapeProject`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ..project import InkscapeProject


@dataclass
class InkscapeLayer:
    """In-memory representation of a single layer."""

    layer_id: str
    name: str
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    element_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "element_ids": list(self.element_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InkscapeLayer":
        return cls(
            layer_id=str(data["layer_id"]),
            name=str(data.get("name", "")),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
            opacity=float(data.get("opacity", 1.0)),
            element_ids=list(data.get("element_ids", [])),
        )


# ---------------------------------------------------------------------------
# Internal helpers


def _layers(project: InkscapeProject) -> list[dict[str, Any]]:
    """Return the mutable layer list from ``project.data``, creating it on demand."""
    return project.data.setdefault("layers", [])


def _check_index(layers: list[dict[str, Any]], index: int, label: str = "layer") -> None:
    if not (0 <= index < len(layers)):
        raise IndexError(f"{label} index {index} out of range (0–{len(layers) - 1})")


# ---------------------------------------------------------------------------
# Public layer operations


def add_layer(
    project: InkscapeProject,
    name: str,
    visible: bool = True,
    locked: bool = False,
    opacity: float = 1.0,
    position: int | None = None,
) -> dict[str, Any]:
    """Append (or insert at *position*) a new layer.

    The layer is stored as a dict in ``project.data["layers"]``.

    Returns
    -------
    dict with action, index, and the new layer dict.
    """
    layer = InkscapeLayer(
        layer_id=str(uuid.uuid4()),
        name=name,
        visible=visible,
        locked=locked,
        opacity=max(0.0, min(1.0, float(opacity))),
    )
    layer_dict = layer.to_dict()
    layers = _layers(project)

    if position is None or position >= len(layers):
        layers.append(layer_dict)
        index = len(layers) - 1
    else:
        insert_at = max(0, position)
        layers.insert(insert_at, layer_dict)
        index = insert_at

    return {
        "action": "add_layer",
        "index": index,
        "layer": layer_dict,
    }


def remove_layer(project: InkscapeProject, layer_index: int) -> dict[str, Any]:
    """Remove the layer at *layer_index*.

    Elements that belonged to the removed layer have their layer
    associations cleared (they remain in ``project.elements``).
    """
    layers = _layers(project)
    _check_index(layers, layer_index)
    removed = layers.pop(layer_index)

    # Unassign affected element IDs from any surviving layers
    orphaned_ids: list[str] = removed.get("element_ids", [])
    for orphan_id in orphaned_ids:
        for remaining in layers:
            eids: list[str] = remaining.setdefault("element_ids", [])
            if orphan_id in eids:
                eids.remove(orphan_id)

    return {
        "action": "remove_layer",
        "removed_index": layer_index,
        "removed_layer": removed,
        "orphaned_element_ids": orphaned_ids,
    }


def move_to_layer(
    project: InkscapeProject,
    element_id: str,
    layer_index: int,
) -> dict[str, Any]:
    """Assign an element to a specific layer by index.

    The element is removed from any other layer it currently belongs to.
    """
    layers = _layers(project)
    _check_index(layers, layer_index)

    # Verify the element exists
    if project.find_by_id(element_id) is None:
        raise KeyError(f"No element with id {element_id!r}")

    # Remove from all existing layers
    previous_layer: int | None = None
    for idx, layer in enumerate(layers):
        eids: list[str] = layer.setdefault("element_ids", [])
        if element_id in eids:
            eids.remove(element_id)
            previous_layer = idx

    # Add to target layer
    layers[layer_index].setdefault("element_ids", []).append(element_id)

    return {
        "action": "move_to_layer",
        "element_id": element_id,
        "layer_index": layer_index,
        "previous_layer": previous_layer,
    }


def set_layer_property(
    project: InkscapeProject,
    layer_index: int,
    prop: str,
    value: Any,
) -> dict[str, Any]:
    """Set a property on a layer dict (``visible``, ``locked``, ``opacity``, ``name``)."""
    allowed = {"visible", "locked", "opacity", "name"}
    if prop not in allowed:
        raise ValueError(f"Unknown layer property {prop!r}. Allowed: {sorted(allowed)}")

    layers = _layers(project)
    _check_index(layers, layer_index)

    if prop == "opacity":
        value = max(0.0, min(1.0, float(value)))
    elif prop in ("visible", "locked"):
        value = bool(value)
    else:
        value = str(value)

    layers[layer_index][prop] = value
    return {
        "action": "set_layer_property",
        "layer_index": layer_index,
        "prop": prop,
        "value": value,
    }


def list_layers(project: InkscapeProject) -> dict[str, Any]:
    """Return all layers with their indices."""
    layers = _layers(project)
    return {
        "layer_count": len(layers),
        "layers": [
            {"index": i, **layer}
            for i, layer in enumerate(layers)
        ],
    }


def reorder_layers(
    project: InkscapeProject,
    from_index: int,
    to_index: int,
) -> dict[str, Any]:
    """Move the layer at *from_index* to *to_index* by re-inserting it."""
    layers = _layers(project)
    _check_index(layers, from_index, "from_index")
    clipped_to = max(0, min(len(layers) - 1, to_index))

    layer = layers.pop(from_index)
    layers.insert(clipped_to, layer)

    return {
        "action": "reorder_layers",
        "from_index": from_index,
        "to_index": clipped_to,
        "layer_name": layer.get("name", ""),
    }


def get_layer(project: InkscapeProject, layer_index: int) -> dict[str, Any]:
    """Return the layer dict at *layer_index* with its index included."""
    layers = _layers(project)
    _check_index(layers, layer_index)
    return {"index": layer_index, **layers[layer_index]}
