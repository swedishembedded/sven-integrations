"""Layer management for the GIMP harness.

Each function returns a result dict that contains the Script-Fu expression
under the ``"script"`` key so the caller can forward it to
:class:`~sven_integrations.gimp.backend.GimpBackend`.
"""

from __future__ import annotations

from typing import Any


def create_layer(
    name: str,
    width: int,
    height: int,
    mode: str = "LAYER-MODE-NORMAL-LEGACY",
) -> dict[str, Any]:
    """Build a Script-Fu command that creates a new RGBA layer.

    The layer is inserted at position 0 (top) of the active image.
    """
    safe_name = name.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")
    script = (
        f'(let* ((image (car (gimp-image-list))) '
        f'(layer (car (gimp-layer-new image {width} {height} RGBA-IMAGE '
        f'"{safe_name}" 100 {mode})))) '
        f'(gimp-image-insert-layer image layer 0 -1) layer)'
    )
    return {
        "action": "create_layer",
        "name": name,
        "width": width,
        "height": height,
        "mode": mode,
        "script": script,
    }


def duplicate_layer(layer_id: int) -> dict[str, Any]:
    """Duplicate an existing layer by its Script-Fu ID."""
    script = f"(car (gimp-layer-copy {layer_id} TRUE))"
    return {
        "action": "duplicate_layer",
        "layer_id": layer_id,
        "script": script,
    }


def flatten_image() -> dict[str, Any]:
    """Merge all layers into a single flat layer."""
    script = "(gimp-image-flatten (car (gimp-image-list)))"
    return {
        "action": "flatten_image",
        "script": script,
    }


def merge_visible() -> dict[str, Any]:
    """Merge all currently visible layers, clipping to the image boundary."""
    script = (
        "(gimp-image-merge-visible-layers "
        "(car (gimp-image-list)) CLIP-TO-IMAGE)"
    )
    return {
        "action": "merge_visible",
        "script": script,
    }


def set_layer_opacity(layer_id: int, opacity: float) -> dict[str, Any]:
    """Set the opacity of a layer.

    Parameters
    ----------
    opacity:
        Value in ``[0.0, 1.0]`` where 1.0 is fully opaque.
    """
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"opacity must be between 0.0 and 1.0, got {opacity!r}")
    gimp_opacity = opacity * 100.0
    script = f"(gimp-layer-set-opacity {layer_id} {gimp_opacity})"
    return {
        "action": "set_layer_opacity",
        "layer_id": layer_id,
        "opacity": opacity,
        "script": script,
    }


def move_layer(layer_id: int, x: int, y: int) -> dict[str, Any]:
    """Position a layer at pixel coordinates *(x, y)*."""
    script = f"(gimp-layer-set-offsets {layer_id} {x} {y})"
    return {
        "action": "move_layer",
        "layer_id": layer_id,
        "x": x,
        "y": y,
        "script": script,
    }


def resize_layer(layer_id: int, w: int, h: int) -> dict[str, Any]:
    """Resize a layer to *w* × *h* pixels, anchored at the current offset."""
    script = f"(gimp-layer-resize {layer_id} {w} {h} 0 0)"
    return {
        "action": "resize_layer",
        "layer_id": layer_id,
        "width": w,
        "height": h,
        "script": script,
    }
