"""SVG text element helpers for the Inkscape harness.

Functions return result dicts with an ``"actions"`` key containing
Inkscape action strings.
"""

from __future__ import annotations

from typing import Any


def add_text(
    x: float,
    y: float,
    content: str,
    font_family: str = "sans-serif",
    font_size: float = 12.0,
    color: str = "#000000",
) -> dict[str, Any]:
    """Create a new text element at *(x, y)*.

    Inkscape's ``text-put`` action inserts a text node; subsequent
    attribute actions set the visual properties.
    """
    safe_content = content.replace('"', "&quot;").replace("'", "&apos;")
    actions = [
        f"text-put:{x},{y},{safe_content}",
        f"object-set-attribute:font-family,{font_family}",
        f"object-set-attribute:font-size,{font_size}px",
        f"object-set-attribute:fill,{color}",
        "select-clear",
    ]
    return {
        "action": "add_text",
        "x": x,
        "y": y,
        "content": content,
        "font_family": font_family,
        "font_size": font_size,
        "color": color,
        "actions": actions,
    }


def edit_text(element_id: str, new_content: str) -> dict[str, Any]:
    """Replace the text content of an existing text element."""
    safe = new_content.replace('"', "&quot;").replace("'", "&apos;")
    actions = [
        f"select-by-id:{element_id}",
        f"text-set-text:{safe}",
        "select-clear",
    ]
    return {
        "action": "edit_text",
        "element_id": element_id,
        "new_content": new_content,
        "actions": actions,
    }


def set_font(
    element_id: str,
    family: str,
    size: float,
    weight: str = "normal",
) -> dict[str, Any]:
    """Set font family, size, and weight on an existing text element."""
    actions = [
        f"select-by-id:{element_id}",
        f"object-set-attribute:font-family,{family}",
        f"object-set-attribute:font-size,{size}px",
        f"object-set-attribute:font-weight,{weight}",
        "select-clear",
    ]
    return {
        "action": "set_font",
        "element_id": element_id,
        "family": family,
        "size": size,
        "weight": weight,
        "actions": actions,
    }


def flow_text_in_frame(frame_id: str, content: str) -> dict[str, Any]:
    """Flow *content* inside an existing frame element.

    This uses Inkscape's flowed-text feature.  *frame_id* must be the
    id of an existing ``<svg:rect>`` or similar bounding shape.
    """
    safe = content.replace('"', "&quot;")
    actions = [
        f"select-by-id:{frame_id}",
        f"text-flow-into-frame:{safe}",
        "select-clear",
    ]
    return {
        "action": "flow_text_in_frame",
        "frame_id": frame_id,
        "content": content,
        "actions": actions,
    }


def convert_text_to_path(element_id: str) -> dict[str, Any]:
    """Convert a text element to an outline path (Object → Object to Path)."""
    actions = [
        f"select-by-id:{element_id}",
        "object-to-path",
        "select-clear",
    ]
    return {
        "action": "convert_text_to_path",
        "element_id": element_id,
        "actions": actions,
    }
