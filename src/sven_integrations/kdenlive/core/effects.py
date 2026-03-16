"""Kdenlive effect management — clip-level effects and transitions."""

from __future__ import annotations

import uuid
from typing import Any

from ..project import KdenliveProject

# ---------------------------------------------------------------------------
# Internal helpers

def _find_clip_data(project: KdenliveProject, clip_id: str) -> dict[str, Any] | None:
    """Return a mutable reference to the clip's effect store (a list)."""
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_id == clip_id:
                return clip  # type: ignore[return-value]
    return None


# Each clip stores effects in a separate dict keyed by clip_id in
# project.data["effects"].  This avoids adding fields to the core dataclass.

def _effects_store(project: KdenliveProject) -> dict[str, list[dict[str, Any]]]:
    if not hasattr(project, "_effects"):
        project._effects: dict[str, list[dict[str, Any]]] = {}  # type: ignore[attr-defined]
    return project._effects  # type: ignore[attr-defined]


def _transitions_store(project: KdenliveProject) -> list[dict[str, Any]]:
    if not hasattr(project, "_transitions"):
        project._transitions: list[dict[str, Any]] = []  # type: ignore[attr-defined]
    return project._transitions  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Public effects API


def add_effect(
    project: KdenliveProject,
    clip_id: str,
    effect_name: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Attach an effect to *clip_id*.

    Returns the new effect descriptor (including its generated effect_id).
    """
    store = _effects_store(project)
    effect = {
        "effect_id": f"eff_{uuid.uuid4().hex[:8]}",
        "name": effect_name,
        "params": dict(params),
    }
    store.setdefault(clip_id, []).append(effect)
    return effect


def remove_effect(project: KdenliveProject, clip_id: str, effect_id: str) -> bool:
    """Remove an effect from a clip.  Returns True if found and removed."""
    store = _effects_store(project)
    effects = store.get(clip_id, [])
    for i, eff in enumerate(effects):
        if eff["effect_id"] == effect_id:
            del effects[i]
            return True
    return False


def list_effects(project: KdenliveProject, clip_id: str) -> list[dict[str, Any]]:
    """Return all effects attached to *clip_id*."""
    return list(_effects_store(project).get(clip_id, []))


def set_effect_param(
    project: KdenliveProject,
    clip_id: str,
    effect_id: str,
    param: str,
    value: Any,
) -> bool:
    """Update a single parameter on an existing effect."""
    store = _effects_store(project)
    for eff in store.get(clip_id, []):
        if eff["effect_id"] == effect_id:
            eff["params"][param] = value
            return True
    return False


def add_transition(
    project: KdenliveProject,
    from_clip: str,
    to_clip: str,
    transition_type: str,
    duration_frames: int,
) -> dict[str, Any]:
    """Create a transition between two clips.

    Returns the transition descriptor.
    """
    transition = {
        "transition_id": f"trans_{uuid.uuid4().hex[:8]}",
        "from_clip": from_clip,
        "to_clip": to_clip,
        "type": transition_type,
        "duration_frames": duration_frames,
    }
    _transitions_store(project).append(transition)
    return transition


def add_title_clip(
    project: KdenliveProject,
    text: str,
    duration_frames: int,
    font: str = "Sans",
    color: str = "#ffffff",
    bg_color: str = "#000000",
) -> str:
    """Add a title (text) clip to the project bin.

    Returns a new clip_id that can later be placed on a track.
    """
    clip_id = f"title_{uuid.uuid4().hex[:8]}"
    store = _effects_store(project)
    store[clip_id] = [
        {
            "effect_id": f"eff_{uuid.uuid4().hex[:8]}",
            "name": "title",
            "params": {
                "text": text,
                "duration_frames": duration_frames,
                "font": font,
                "color": color,
                "bg_color": bg_color,
            },
        }
    ]
    return clip_id
