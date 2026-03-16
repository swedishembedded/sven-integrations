"""Canvas geometry operations for the GIMP harness.

Functions here produce result dicts with a ``"script"`` key containing the
Script-Fu expression that performs the operation on the active image.
"""

from __future__ import annotations

from typing import Any, Literal


def crop(x: int, y: int, w: int, h: int) -> dict[str, Any]:
    """Crop the active image to a *w* × *h* rectangle starting at *(x, y)*."""
    script = f"(gimp-image-crop (car (gimp-image-list)) {w} {h} {x} {y})"
    return {
        "action": "crop",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "script": script,
    }


def resize_canvas(
    w: int,
    h: int,
    offset_x: int = 0,
    offset_y: int = 0,
) -> dict[str, Any]:
    """Resize the canvas without scaling pixel content.

    *offset_x* / *offset_y* shift existing content within the new canvas.
    """
    script = (
        f"(gimp-image-resize (car (gimp-image-list)) "
        f"{w} {h} {offset_x} {offset_y})"
    )
    return {
        "action": "resize_canvas",
        "width": w,
        "height": h,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "script": script,
    }


def scale_image(
    w: int,
    h: int,
    interpolation: str = "INTERPOLATION-LINEAR",
) -> dict[str, Any]:
    """Scale the image to *w* × *h* using the specified interpolation method."""
    script = (
        f"(gimp-image-scale-full (car (gimp-image-list)) "
        f"{w} {h} {interpolation})"
    )
    return {
        "action": "scale_image",
        "width": w,
        "height": h,
        "interpolation": interpolation,
        "script": script,
    }


def rotate(angle_deg: float, auto_crop: bool = False) -> dict[str, Any]:
    """Rotate the active drawable by *angle_deg* degrees.

    When *auto_crop* is True the canvas is trimmed to the rotated content.
    """
    angle_rad = angle_deg * 3.141592653589793 / 180.0
    auto = "TRUE" if auto_crop else "FALSE"
    script = (
        f"(let* ((image (car (gimp-image-list))) "
        f"(drawable (car (gimp-image-get-active-drawable image)))) "
        f"(gimp-item-transform-rotate-default drawable {angle_rad} {auto} 0 0))"
    )
    return {
        "action": "rotate",
        "angle_deg": angle_deg,
        "auto_crop": auto_crop,
        "script": script,
    }


def flip(direction: Literal["h", "v"]) -> dict[str, Any]:
    """Flip the image horizontally (``"h"``) or vertically (``"v"``)."""
    if direction not in ("h", "v"):
        raise ValueError(f"direction must be 'h' or 'v', got {direction!r}")
    orientation = (
        "ORIENTATION-HORIZONTAL" if direction == "h" else "ORIENTATION-VERTICAL"
    )
    script = f"(gimp-image-flip (car (gimp-image-list)) {orientation})"
    return {
        "action": "flip",
        "direction": direction,
        "script": script,
    }


def set_resolution(dpi: float) -> dict[str, Any]:
    """Set both the horizontal and vertical resolution of the image."""
    script = (
        f"(gimp-image-set-resolution (car (gimp-image-list)) {dpi} {dpi})"
    )
    return {
        "action": "set_resolution",
        "dpi": dpi,
        "script": script,
    }


def flatten_to_background() -> dict[str, Any]:
    """Flatten all layers into a single background layer."""
    script = "(gimp-image-flatten (car (gimp-image-list)))"
    return {
        "action": "flatten_to_background",
        "script": script,
    }
