"""Kdenlive timeline transition management — MLT transition model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..project import KdenliveProject

# ---------------------------------------------------------------------------
# Transition registry

TRANSITION_TYPES: dict[str, dict[str, Any]] = {
    "dissolve": {
        "description": "Cross-fade dissolve between two tracks",
        "mlt_service": "luma",
        "default_params": {"softness": 0.0},
    },
    "wipe": {
        "description": "Directional wipe transition",
        "mlt_service": "luma",
        "default_params": {"resource": "%luma01.pgm", "softness": 0.0},
    },
    "slide": {
        "description": "Slide one track over another",
        "mlt_service": "slide",
        "default_params": {"direction": "left"},
    },
    "composite": {
        "description": "Composite two tracks with alpha blending",
        "mlt_service": "composite",
        "default_params": {"operator": "over", "halign": "centre", "valign": "centre"},
    },
    "affine": {
        "description": "Affine transformation composite (scale, rotate, translate)",
        "mlt_service": "affine",
        "default_params": {"background": "colour:0x00000000", "distort": 0},
    },
    "luma": {
        "description": "Luma wipe using a grayscale map image",
        "mlt_service": "luma",
        "default_params": {"resource": "", "softness": 0.0, "reverse": 0},
    },
}


@dataclass
class TimelineTransition:
    """A transition between two overlapping tracks on the Kdenlive timeline."""

    transition_id: int
    transition_type: str
    track_a: str
    track_b: str
    position_seconds: float
    duration_seconds: float = 1.0
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.transition_type not in TRANSITION_TYPES:
            raise ValueError(
                f"transition_type must be one of {sorted(TRANSITION_TYPES)}, "
                f"got {self.transition_type!r}"
            )
        if self.duration_seconds <= 0:
            raise ValueError(f"duration_seconds must be > 0, got {self.duration_seconds}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "transition_type": self.transition_type,
            "track_a": self.track_a,
            "track_b": self.track_b,
            "position_seconds": self.position_seconds,
            "duration_seconds": self.duration_seconds,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TimelineTransition":
        return cls(
            transition_id=int(d["transition_id"]),
            transition_type=str(d["transition_type"]),
            track_a=str(d["track_a"]),
            track_b=str(d["track_b"]),
            position_seconds=float(d["position_seconds"]),
            duration_seconds=float(d.get("duration_seconds", 1.0)),
            params=dict(d.get("params", {})),
        )


# ---------------------------------------------------------------------------
# Project-level helpers


def _ensure_transitions(project: KdenliveProject) -> list[dict[str, Any]]:
    data: dict[str, Any] = getattr(project, "data", {})
    if not hasattr(project, "_transitions"):
        project._transitions: list[dict[str, Any]] = list(data.get("transitions", []))  # type: ignore[attr-defined]
    return project._transitions  # type: ignore[attr-defined]


def _sync_transitions(project: KdenliveProject, transitions: list[dict[str, Any]]) -> None:
    if not hasattr(project, "data"):
        project.data = {}  # type: ignore[attr-defined]
    project.data["transitions"] = transitions  # type: ignore[attr-defined]


def _next_transition_id(transitions: list[dict[str, Any]]) -> int:
    if not transitions:
        return 1
    return max(t["transition_id"] for t in transitions) + 1


def add_transition(
    project: KdenliveProject,
    transition_type: str,
    track_a: str,
    track_b: str,
    position_seconds: float,
    duration_seconds: float = 1.0,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a transition between *track_a* and *track_b* at *position_seconds*."""
    transitions = _ensure_transitions(project)
    spec = TRANSITION_TYPES.get(transition_type)
    if spec is None:
        raise ValueError(
            f"Unknown transition type {transition_type!r}. "
            f"Available: {sorted(TRANSITION_TYPES)}"
        )
    merged_params = {**spec["default_params"], **(params or {})}
    trans = TimelineTransition(
        transition_id=_next_transition_id(transitions),
        transition_type=transition_type,
        track_a=track_a,
        track_b=track_b,
        position_seconds=position_seconds,
        duration_seconds=duration_seconds,
        params=merged_params,
    )
    entry = trans.to_dict()
    transitions.append(entry)
    _sync_transitions(project, transitions)
    return entry


def remove_transition(project: KdenliveProject, transition_id: int) -> dict[str, Any]:
    """Remove the transition with *transition_id* and return its data."""
    transitions = _ensure_transitions(project)
    for i, t in enumerate(transitions):
        if t["transition_id"] == transition_id:
            removed = transitions.pop(i)
            _sync_transitions(project, transitions)
            return removed
    raise KeyError(f"Transition {transition_id} not found")


def set_transition(
    project: KdenliveProject,
    transition_id: int,
    param_name: str,
    value: Any,
) -> dict[str, Any]:
    """Update a single parameter on the transition with *transition_id*."""
    transitions = _ensure_transitions(project)
    for t in transitions:
        if t["transition_id"] == transition_id:
            t["params"][param_name] = value
            _sync_transitions(project, transitions)
            return t
    raise KeyError(f"Transition {transition_id} not found")


def list_transitions(project: KdenliveProject) -> dict[str, Any]:
    """Return all transitions on the project."""
    transitions = _ensure_transitions(project)
    return {"count": len(transitions), "transitions": list(transitions)}


def build_transition_xml(t: dict[str, Any]) -> str:
    """Build an MLT XML ``<transition>`` element string from transition dict *t*."""
    spec = TRANSITION_TYPES.get(t.get("transition_type", ""), {})
    mlt_service = spec.get("mlt_service", "luma")
    fps = 25  # default assumption
    in_frame = int(t.get("position_seconds", 0) * fps)
    out_frame = int((t.get("position_seconds", 0) + t.get("duration_seconds", 1.0)) * fps) - 1

    lines = [
        f'<transition id="transition_{t.get("transition_id", 0)}"'
        f' in="{in_frame}" out="{out_frame}">',
        f'  <property name="mlt_service">{mlt_service}</property>',
        f'  <property name="a_track">{t.get("track_a", "0")}</property>',
        f'  <property name="b_track">{t.get("track_b", "1")}</property>',
    ]
    for key, val in t.get("params", {}).items():
        lines.append(f'  <property name="{key}">{val}</property>')
    lines.append("</transition>")
    return "\n".join(lines)
