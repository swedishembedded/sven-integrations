"""OBS scene transition management — dataclass model and project-level operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ..project import ObsSetup

TRANSITION_TYPES: list[str] = [
    "cut",
    "fade",
    "swipe",
    "slide",
    "stinger",
    "fade_to_color",
    "luma_wipe",
]

_OBS_TRANSITION_ID_MAP: dict[str, str] = {
    "cut": "cut_transition",
    "fade": "fade_transition",
    "swipe": "swipe_transition",
    "slide": "slide_transition",
    "stinger": "obs_stinger_transition",
    "fade_to_color": "fade_to_color_transition",
    "luma_wipe": "wipe_transition",
}


@dataclass
class SceneTransition:
    """Represents a scene transition entry."""

    transition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Transition"
    transition_type: str = "fade"
    duration_ms: int = 300
    active: bool = False

    def __post_init__(self) -> None:
        if self.transition_type not in TRANSITION_TYPES:
            raise ValueError(
                f"transition_type must be one of {TRANSITION_TYPES}, "
                f"got {self.transition_type!r}"
            )
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be >= 0, got {self.duration_ms}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "name": self.name,
            "transition_type": self.transition_type,
            "duration_ms": self.duration_ms,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SceneTransition":
        return cls(
            transition_id=str(d.get("transition_id", str(uuid.uuid4()))),
            name=str(d.get("name", "Transition")),
            transition_type=str(d.get("transition_type", "fade")),
            duration_ms=int(d.get("duration_ms", 300)),
            active=bool(d.get("active", False)),
        )


# ---------------------------------------------------------------------------
# Project-level helpers


def _get_transitions(project: ObsSetup) -> list[dict[str, Any]]:
    return project.data.setdefault("transitions", [])  # type: ignore[attr-defined]


def _at_index(project: ObsSetup, index: int) -> dict[str, Any]:
    tlist = _get_transitions(project)
    if index < 0 or index >= len(tlist):
        raise IndexError(f"Transition index {index} out of range (have {len(tlist)})")
    return tlist[index]


def add_transition(
    project: ObsSetup,
    transition_type: str,
    name: str | None = None,
    duration_ms: int = 300,
) -> dict[str, Any]:
    """Create a new transition and register it on the project."""
    tlist = _get_transitions(project)
    effective_name = name or f"{transition_type}_{len(tlist)}"
    trans = SceneTransition(
        name=effective_name,
        transition_type=transition_type,
        duration_ms=duration_ms,
        active=len(tlist) == 0,
    )
    tlist.append(trans.to_dict())
    return trans.to_dict()


def remove_transition(project: ObsSetup, index: int) -> dict[str, Any]:
    """Remove the transition at *index* and return its data."""
    tlist = _get_transitions(project)
    if index < 0 or index >= len(tlist):
        raise IndexError(f"Transition index {index} out of range")
    removed = tlist.pop(index)
    # If the removed transition was active, activate the first remaining one
    if removed.get("active") and tlist:
        tlist[0]["active"] = True
    return removed


def set_duration(project: ObsSetup, index: int, duration_ms: int) -> dict[str, Any]:
    """Update the duration of the transition at *index*."""
    if duration_ms < 0:
        raise ValueError(f"duration_ms must be >= 0, got {duration_ms}")
    trans = _at_index(project, index)
    trans["duration_ms"] = duration_ms
    return trans


def set_active_transition(project: ObsSetup, index: int) -> dict[str, Any]:
    """Mark the transition at *index* as the active one (clears all others)."""
    tlist = _get_transitions(project)
    if index < 0 or index >= len(tlist):
        raise IndexError(f"Transition index {index} out of range (have {len(tlist)})")
    for i, t in enumerate(tlist):
        t["active"] = i == index
    return tlist[index]


def list_transitions(project: ObsSetup) -> dict[str, Any]:
    """Return all transitions registered on the project."""
    tlist = _get_transitions(project)
    return {"count": len(tlist), "transitions": list(tlist)}


def build_transition_requests(project: ObsSetup) -> list[dict[str, Any]]:
    """Build obs-websocket request dicts to configure all project transitions."""
    requests: list[dict[str, Any]] = []
    for trans in _get_transitions(project):
        obs_id = _OBS_TRANSITION_ID_MAP.get(trans.get("transition_type", ""), "fade_transition")
        requests.append({
            "requestType": "CreateSceneTransition",
            "requestData": {
                "transitionName": trans.get("name", ""),
                "transitionKind": obs_id,
            },
        })
        if trans.get("active"):
            requests.append({
                "requestType": "SetCurrentSceneTransition",
                "requestData": {"transitionName": trans.get("name", "")},
            })
            requests.append({
                "requestType": "SetCurrentSceneTransitionDuration",
                "requestData": {"transitionDuration": trans.get("duration_ms", 300)},
            })
    return requests
