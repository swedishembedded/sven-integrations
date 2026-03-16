"""Blender render configuration helpers.

Functions return result dicts with a ``"statements"`` key for use with
:meth:`~sven_integrations.blender.backend.BlenderBackend.build_python_expr`.
"""

from __future__ import annotations

from typing import Any

_VALID_ENGINES = frozenset({"CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"})
_ENGINE_ALIASES = {
    "EEVEE": "BLENDER_EEVEE",
    "WORKBENCH": "BLENDER_WORKBENCH",
    "CYCLES": "CYCLES",
    "BLENDER_EEVEE": "BLENDER_EEVEE",
    "BLENDER_WORKBENCH": "BLENDER_WORKBENCH",
}
_VALID_FORMATS = frozenset({"PNG", "JPEG", "OPEN_EXR", "FFMPEG"})
_FORMAT_ALIASES = {
    "EXR": "OPEN_EXR",
    "MP4": "FFMPEG",
    "JPG": "JPEG",
    "JPEG": "JPEG",
    "PNG": "PNG",
    "OPEN_EXR": "OPEN_EXR",
    "FFMPEG": "FFMPEG",
}


def _preamble() -> list[str]:
    return ["import bpy"]


def set_render_engine(engine: str) -> dict[str, Any]:
    """Set the render engine.

    Accepts ``CYCLES``, ``EEVEE`` (mapped to ``BLENDER_EEVEE``), or
    ``WORKBENCH`` (mapped to ``BLENDER_WORKBENCH``).
    """
    key = _ENGINE_ALIASES.get(engine.upper())
    if key is None:
        raise ValueError(
            f"Unknown engine {engine!r}. "
            f"Choose from: CYCLES, EEVEE, WORKBENCH"
        )
    stmts = _preamble() + [
        f"bpy.context.scene.render.engine = '{key}'",
    ]
    return {
        "action": "set_render_engine",
        "engine": key,
        "statements": stmts,
    }


def set_output_resolution(
    width: int,
    height: int,
    percentage: int = 100,
) -> dict[str, Any]:
    """Set the output resolution and resolution percentage."""
    stmts = _preamble() + [
        f"bpy.context.scene.render.resolution_x = {width}",
        f"bpy.context.scene.render.resolution_y = {height}",
        f"bpy.context.scene.render.resolution_percentage = {percentage}",
    ]
    return {
        "action": "set_output_resolution",
        "width": width,
        "height": height,
        "percentage": percentage,
        "statements": stmts,
    }


def set_output_format(fmt: str) -> dict[str, Any]:
    """Set the output image/video format.

    Accepts ``PNG``, ``JPEG`` / ``JPG``, ``EXR``, ``MP4`` / ``FFMPEG``.
    """
    key = _FORMAT_ALIASES.get(fmt.upper())
    if key is None:
        raise ValueError(
            f"Unknown format {fmt!r}. Choose from: PNG, JPEG, EXR, MP4"
        )
    stmts = _preamble() + [
        f"bpy.context.scene.render.image_settings.file_format = '{key}'",
    ]
    return {
        "action": "set_output_format",
        "format": key,
        "statements": stmts,
    }


def set_samples(count: int) -> dict[str, Any]:
    """Set the number of render samples.

    Works for both Cycles (``cycles.samples``) and EEVEE
    (``eevee.taa_render_samples``).
    """
    stmts = _preamble() + [
        f"bpy.context.scene.cycles.samples = {count}",
        f"if hasattr(bpy.context.scene, 'eevee'): bpy.context.scene.eevee.taa_render_samples = {count}",
    ]
    return {
        "action": "set_samples",
        "count": count,
        "statements": stmts,
    }


def set_output_path(path: str) -> dict[str, Any]:
    """Set the render output file path."""
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    stmts = _preamble() + [
        f'bpy.context.scene.render.filepath = "{escaped}"',
    ]
    return {
        "action": "set_output_path",
        "path": path,
        "statements": stmts,
    }


def enable_denoising(enabled: bool) -> dict[str, Any]:
    """Enable or disable Cycles denoising."""
    flag = "True" if enabled else "False"
    stmts = _preamble() + [
        f"bpy.context.scene.cycles.use_denoising = {flag}",
    ]
    return {
        "action": "enable_denoising",
        "enabled": enabled,
        "statements": stmts,
    }
