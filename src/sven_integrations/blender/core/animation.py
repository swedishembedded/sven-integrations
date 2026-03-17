"""Blender animation keyframe management.

Functions to add, remove, list, and apply keyframes on scene objects.
All keyframe state is stored in ``project.data["keyframes"]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..project import BlenderProject

# ---------------------------------------------------------------------------
# Internal data model


@dataclass
class KeyframeEntry:
    """A single keyframe stored in the project harness."""

    object_index: int
    frame: int
    prop: str
    value: Any
    interpolation: str = "BEZIER"

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_index": self.object_index,
            "frame": self.frame,
            "prop": self.prop,
            "value": self.value,
            "interpolation": self.interpolation,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "KeyframeEntry":
        return cls(
            object_index=int(d["object_index"]),
            frame=int(d["frame"]),
            prop=str(d["prop"]),
            value=d["value"],
            interpolation=str(d.get("interpolation", "BEZIER")),
        )


# ---------------------------------------------------------------------------
# Private helpers


def _keyframes(project: BlenderProject) -> list[dict[str, Any]]:
    return project.data.setdefault("keyframes", [])


def _matches(kf: dict[str, Any], object_index: int, frame: int, prop: str | None) -> bool:
    if kf["object_index"] != object_index or kf["frame"] != frame:
        return False
    return prop is None or kf["prop"] == prop


# ---------------------------------------------------------------------------
# Public API


def add_keyframe(
    project: BlenderProject,
    object_index: int,
    frame: int,
    prop: str,
    value: Any,
    interpolation: str = "BEZIER",
) -> dict[str, Any]:
    """Add or update a keyframe on an object property.

    If a keyframe already exists for the same *object_index*, *frame*, and
    *prop*, its value and interpolation are updated in place.  Otherwise a
    new entry is appended.

    Returns the result dict with ``"action": "add_keyframe"`` plus all
    keyframe fields.
    """
    keyframes = _keyframes(project)
    for kf in keyframes:
        if kf["object_index"] == object_index and kf["frame"] == frame and kf["prop"] == prop:
            kf["value"] = value
            kf["interpolation"] = interpolation
            return {
                "action": "add_keyframe",
                "updated": True,
                **KeyframeEntry.from_dict(kf).to_dict(),
            }
    entry = KeyframeEntry(
        object_index=object_index,
        frame=frame,
        prop=prop,
        value=value,
        interpolation=interpolation,
    )
    keyframes.append(entry.to_dict())
    return {"action": "add_keyframe", "updated": False, **entry.to_dict()}


def remove_keyframe(
    project: BlenderProject,
    object_index: int,
    frame: int,
    prop: str | None = None,
) -> dict[str, Any]:
    """Remove keyframe(s) from *object_index* at *frame*.

    When *prop* is provided, only the keyframe for that property is removed.
    When *prop* is ``None``, all keyframes for the object at that frame are
    removed.
    """
    keyframes = _keyframes(project)
    before = len(keyframes)
    project.data["keyframes"] = [
        kf for kf in keyframes if not _matches(kf, object_index, frame, prop)
    ]
    return {
        "action": "remove_keyframe",
        "object_index": object_index,
        "frame": frame,
        "prop": prop,
        "removed_count": before - len(project.data["keyframes"]),
    }


def list_keyframes(
    project: BlenderProject,
    object_index: int,
    prop: str | None = None,
) -> dict[str, Any]:
    """List keyframes for *object_index*, optionally filtered by *prop*."""
    keyframes = _keyframes(project)
    results = [
        kf for kf in keyframes
        if kf["object_index"] == object_index and (prop is None or kf["prop"] == prop)
    ]
    return {
        "action": "list_keyframes",
        "object_index": object_index,
        "prop": prop,
        "keyframes": results,
    }


def set_current_frame(project: BlenderProject, frame: int) -> dict[str, Any]:
    """Store the current frame marker in the project."""
    project.data["current_frame"] = frame
    return {"action": "set_current_frame", "frame": frame}


def build_animation_script(project: BlenderProject) -> list[str]:
    """Return Blender Python statements that apply all stored keyframes."""
    keyframes = _keyframes(project)
    if not keyframes:
        return []

    stmts: list[str] = ["import bpy"]
    for kf in keyframes:
        obj_idx = kf["object_index"]
        frame = kf["frame"]
        prop = kf["prop"]
        value = kf["value"]
        interp = kf["interpolation"]
        stmts += [
            f"_anim_obj = list(bpy.context.scene.objects)[{obj_idx}]",
            f"bpy.context.scene.frame_set({frame})",
            f"_anim_obj.{prop} = {value!r}",
            f"_anim_obj.keyframe_insert(data_path={prop!r}, frame={frame})",
            "_anim_action = _anim_obj.animation_data.action if _anim_obj.animation_data else None",
            "if _anim_action:",
            "    for _fc in _anim_action.fcurves:",
            f"        if _fc.data_path == {prop!r}:",
            "            for _kp in _fc.keyframe_points:",
            f"                if abs(_kp.co[0] - {frame}) < 0.5:",
            f"                    _kp.interpolation = {interp!r}",
        ]
    return stmts
