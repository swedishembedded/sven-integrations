"""Blender scene-level management helpers.

Each function returns a result dict that includes a ``"statements"`` key —
a ``list[str]`` of Python statements suitable for passing to
:meth:`~sven_integrations.blender.backend.BlenderBackend.build_python_expr`.
"""

from __future__ import annotations

from typing import Any

_BPY_SCENE = "bpy.context.scene"


def _preamble() -> list[str]:
    return ["import bpy"]


def set_frame_range(start: int, end: int) -> dict[str, Any]:
    """Set the animation frame range for the active scene."""
    stmts = _preamble() + [
        f"{_BPY_SCENE}.frame_start = {start}",
        f"{_BPY_SCENE}.frame_end = {end}",
    ]
    return {
        "action": "set_frame_range",
        "frame_start": start,
        "frame_end": end,
        "statements": stmts,
    }


def set_fps(fps: int) -> dict[str, Any]:
    """Set the frames-per-second of the active scene."""
    stmts = _preamble() + [
        f"{_BPY_SCENE}.render.fps = {fps}",
    ]
    return {
        "action": "set_fps",
        "fps": fps,
        "statements": stmts,
    }


def get_scene_info() -> dict[str, Any]:
    """Build statements that print scene info as JSON to stdout."""
    stmts = _preamble() + [
        "import json",
        "sc = bpy.context.scene",
        "info = {"
        '"name": sc.name, "frame_start": sc.frame_start, '
        '"frame_end": sc.frame_end, "fps": sc.render.fps, '
        '"object_count": len(sc.objects)'
        "}",
        "print(json.dumps(info))",
    ]
    return {
        "action": "get_scene_info",
        "statements": stmts,
    }


def set_active_camera(name: str) -> dict[str, Any]:
    """Set the scene camera to the object named *name*."""
    safe = name.replace('"', '\\"')
    stmts = _preamble() + [
        f'cam_obj = bpy.data.objects.get("{safe}")',
        "if cam_obj is None: raise ValueError(f'Camera object not found: {name!r}')",
        "bpy.context.scene.camera = cam_obj",
    ]
    return {
        "action": "set_active_camera",
        "name": name,
        "statements": stmts,
    }


def set_world_color(r: float, g: float, b: float) -> dict[str, Any]:
    """Set the world background colour to an RGB value (each component 0–1)."""
    stmts = _preamble() + [
        "world = bpy.context.scene.world",
        "if world is None:",
        "    world = bpy.data.worlds.new('World')",
        "    bpy.context.scene.world = world",
        "world.use_nodes = False",
        f"world.color = ({r}, {g}, {b})",
    ]
    return {
        "action": "set_world_color",
        "r": r,
        "g": g,
        "b": b,
        "statements": stmts,
    }


def list_objects() -> dict[str, Any]:
    """Build statements that print all scene objects as JSON."""
    stmts = _preamble() + [
        "import json",
        "objs = [{"
        '"name": o.name, "type": o.type, '
        '"location": list(o.location), '
        '"visible": not o.hide_viewport'
        "} for o in bpy.context.scene.objects]",
        "print(json.dumps(objs))",
    ]
    return {
        "action": "list_objects",
        "statements": stmts,
    }
