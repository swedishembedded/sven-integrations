"""Shotcut compositing — blend modes, opacity, and PIP positioning via MLT filters."""

from __future__ import annotations

from typing import Any

from ..project import ShotcutProject

# Cairo/MLT blend modes with their string identifiers
BLEND_MODES: dict[str, str] = {
    "normal": "normal",
    "over": "over",
    "atop": "atop",
    "xor": "xor",
    "plus": "plus",
    "saturate": "saturate",
    "multiply": "multiply",
    "screen": "screen",
    "overlay": "overlay",
    "darken": "darken",
    "lighten": "lighten",
    "color_dodge": "color dodge",
    "color_burn": "color burn",
    "hard_light": "hard light",
    "soft_light": "soft light",
    "difference": "difference",
    "exclusion": "exclusion",
}


# ---------------------------------------------------------------------------
# Helpers


def _track_at(project: ShotcutProject, track_index: int) -> dict[str, Any]:
    """Return the track dict at *track_index* or raise IndexError."""
    if track_index < 0 or track_index >= len(project.tracks):
        raise IndexError(
            f"Track index {track_index} out of range (have {len(project.tracks)})"
        )
    track = project.tracks[track_index]
    # Ensure the track has a metadata dict
    if not hasattr(track, "meta"):
        track.meta = {}  # type: ignore[attr-defined]
    return track.meta  # type: ignore[attr-defined]


def _clip_at(project: ShotcutProject, track_index: int, clip_index: int) -> Any:
    """Return the clip at *clip_index* within the track at *track_index*."""
    if track_index < 0 or track_index >= len(project.tracks):
        raise IndexError(f"Track index {track_index} out of range")
    track = project.tracks[track_index]
    if clip_index < 0 or clip_index >= len(track.clips):
        raise IndexError(f"Clip index {clip_index} out of range")
    return track.clips[clip_index]


# ---------------------------------------------------------------------------
# Public API


def set_track_blend_mode(
    project: ShotcutProject,
    track_index: int,
    blend_mode: str,
) -> dict[str, Any]:
    """Set the Cairo blend mode for the track at *track_index*."""
    if blend_mode not in BLEND_MODES:
        raise ValueError(
            f"blend_mode must be one of {sorted(BLEND_MODES)}, got {blend_mode!r}"
        )
    meta = _track_at(project, track_index)
    meta["blend_mode"] = blend_mode
    meta["mlt_blend_mode"] = BLEND_MODES[blend_mode]
    return {"track_index": track_index, "blend_mode": blend_mode}


def get_track_blend_mode(project: ShotcutProject, track_index: int) -> dict[str, Any]:
    """Return the currently stored blend mode for the track at *track_index*."""
    meta = _track_at(project, track_index)
    mode = meta.get("blend_mode", "normal")
    return {"track_index": track_index, "blend_mode": mode}


def set_track_opacity(
    project: ShotcutProject,
    track_index: int,
    opacity: float,
) -> dict[str, Any]:
    """Set the opacity (0.0–1.0) for the track at *track_index*.

    Stores a brightness filter entry in the track meta that represents
    the opacity level in the MLT filter chain.
    """
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"opacity must be in [0, 1], got {opacity}")
    meta = _track_at(project, track_index)
    meta["opacity"] = opacity
    meta["opacity_filter"] = {
        "mlt_service": "brightness",
        "alpha": opacity,
    }
    return {"track_index": track_index, "opacity": opacity}


def pip_position(
    project: ShotcutProject,
    track_index: int,
    clip_index: int,
    x: float,
    y: float,
    width: float,
    height: float,
    opacity: float = 1.0,
) -> dict[str, Any]:
    """Set a picture-in-picture affine transform filter on the specified clip.

    Coordinates are normalised (0.0–1.0 relative to canvas dimensions).
    """
    if not 0.0 <= opacity <= 1.0:
        raise ValueError(f"opacity must be in [0, 1], got {opacity}")

    clip = _clip_at(project, track_index, clip_index)

    # Store the PIP filter specification on the clip object
    pip_filter = {
        "mlt_service": "affine",
        "transition.geometry": f"{x:.4f} {y:.4f} {width:.4f} {height:.4f} {opacity:.4f}",
        "transition.distort": 0,
        "transition.background": "colour:0x00000000",
    }
    if not hasattr(clip, "pip_filter"):
        clip.pip_filter = {}  # type: ignore[attr-defined]
    clip.pip_filter = pip_filter  # type: ignore[attr-defined]

    return {
        "track_index": track_index,
        "clip_index": clip_index,
        "clip_id": clip.clip_id,
        "pip": {"x": x, "y": y, "width": width, "height": height, "opacity": opacity},
    }


def list_blend_modes() -> list[dict[str, Any]]:
    """Return all supported Cairo blend modes with their MLT names."""
    return [
        {"name": name, "mlt_name": mlt_name}
        for name, mlt_name in BLEND_MODES.items()
    ]
