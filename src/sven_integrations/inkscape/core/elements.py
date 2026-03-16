"""SVG element manipulation helpers for the Inkscape harness.

Each function returns a result dict with an ``"actions"`` key containing a
``list[str]`` of Inkscape action strings, suitable for passing to
:meth:`~sven_integrations.inkscape.backend.InkscapeBackend.run_actions`.
"""

from __future__ import annotations

from typing import Any


def select_element(element_id: str) -> dict[str, Any]:
    """Select an element by its SVG id attribute."""
    actions = [f"select-by-id:{element_id}"]
    return {
        "action": "select_element",
        "element_id": element_id,
        "actions": actions,
    }


def move_element(element_id: str, dx: float, dy: float) -> dict[str, Any]:
    """Translate an element by *(dx, dy)* user units relative to its current position."""
    actions = [
        f"select-by-id:{element_id}",
        f"transform-translate:{dx},{dy}",
        "select-clear",
    ]
    return {
        "action": "move_element",
        "element_id": element_id,
        "dx": dx,
        "dy": dy,
        "actions": actions,
    }


def scale_element(element_id: str, sx: float, sy: float) -> dict[str, Any]:
    """Scale an element by factors *(sx, sy)* relative to its current size."""
    actions = [
        f"select-by-id:{element_id}",
        f"transform-scale:{sx},{sy}",
        "select-clear",
    ]
    return {
        "action": "scale_element",
        "element_id": element_id,
        "sx": sx,
        "sy": sy,
        "actions": actions,
    }


def rotate_element(
    element_id: str,
    angle: float,
    cx: float = 0.0,
    cy: float = 0.0,
) -> dict[str, Any]:
    """Rotate an element by *angle* degrees around point *(cx, cy)*.

    When *(cx, cy)* is ``(0, 0)`` Inkscape rotates around the object's
    own centre.
    """
    actions = [
        f"select-by-id:{element_id}",
        f"transform-rotate:{angle},{cx},{cy}",
        "select-clear",
    ]
    return {
        "action": "rotate_element",
        "element_id": element_id,
        "angle": angle,
        "cx": cx,
        "cy": cy,
        "actions": actions,
    }


def set_fill(element_id: str, color: str) -> dict[str, Any]:
    """Set the fill colour of an element.

    *color* may be any CSS colour value, e.g. ``"#ff0000"`` or ``"red"``.
    """
    actions = [
        f"select-by-id:{element_id}",
        f"object-set-attribute:fill,{color}",
        "select-clear",
    ]
    return {
        "action": "set_fill",
        "element_id": element_id,
        "color": color,
        "actions": actions,
    }


def set_stroke(element_id: str, color: str, width: float = 1.0) -> dict[str, Any]:
    """Set the stroke colour and width of an element."""
    actions = [
        f"select-by-id:{element_id}",
        f"object-set-attribute:stroke,{color}",
        f"object-set-attribute:stroke-width,{width}",
        "select-clear",
    ]
    return {
        "action": "set_stroke",
        "element_id": element_id,
        "color": color,
        "width": width,
        "actions": actions,
    }


def duplicate_element(element_id: str) -> dict[str, Any]:
    """Duplicate an element in place (Inkscape ``edit-duplicate`` action)."""
    actions = [
        f"select-by-id:{element_id}",
        "edit-duplicate",
        "select-clear",
    ]
    return {
        "action": "duplicate_element",
        "element_id": element_id,
        "actions": actions,
    }


def delete_element(element_id: str) -> dict[str, Any]:
    """Delete an element from the document."""
    actions = [
        f"select-by-id:{element_id}",
        "edit-delete",
    ]
    return {
        "action": "delete_element",
        "element_id": element_id,
        "actions": actions,
    }


def group_elements(ids: list[str], group_id: str) -> dict[str, Any]:
    """Group a list of elements under a new ``<g>`` element with *group_id*.

    Elements are selected by ID, then grouped using Inkscape's
    ``object-group`` action.  The new group's id is set via an attribute
    assignment.
    """
    if not ids:
        raise ValueError("ids must not be empty")
    select_actions = [f"select-by-id:{eid}" for eid in ids]
    actions = select_actions + [
        "object-group",
        f"object-set-attribute:id,{group_id}",
        "select-clear",
    ]
    return {
        "action": "group_elements",
        "ids": ids,
        "group_id": group_id,
        "actions": actions,
    }
