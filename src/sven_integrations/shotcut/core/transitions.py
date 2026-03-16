"""Shotcut transition management — registry, project-level CRUD, and MLT XML generation."""

from __future__ import annotations

from typing import Any

from ..project import ShotcutProject

# ---------------------------------------------------------------------------
# Transition registry

TRANSITION_REGISTRY: dict[str, dict[str, Any]] = {
    "dissolve": {
        "service": "luma",
        "description": "Simple cross-dissolve between two tracks",
        "category": "dissolve",
        "default_params": {"softness": 0.0, "reverse": 0},
    },
    "luma": {
        "service": "luma",
        "description": "Luma wipe using a custom grayscale map",
        "category": "wipe",
        "default_params": {"resource": "", "softness": 0.0},
    },
    "wipe_left": {
        "service": "luma",
        "description": "Horizontal wipe from right to left",
        "category": "wipe",
        "default_params": {"resource": "%luma01.pgm", "softness": 0.0},
    },
    "wipe_right": {
        "service": "luma",
        "description": "Horizontal wipe from left to right",
        "category": "wipe",
        "default_params": {"resource": "%luma01.pgm", "softness": 0.0, "reverse": 1},
    },
    "wipe_up": {
        "service": "luma",
        "description": "Vertical wipe from bottom to top",
        "category": "wipe",
        "default_params": {"resource": "%luma02.pgm", "softness": 0.0},
    },
    "wipe_down": {
        "service": "luma",
        "description": "Vertical wipe from top to bottom",
        "category": "wipe",
        "default_params": {"resource": "%luma02.pgm", "softness": 0.0, "reverse": 1},
    },
    "clock": {
        "service": "luma",
        "description": "Clock-style radial sweep transition",
        "category": "wipe",
        "default_params": {"resource": "%luma13.pgm", "softness": 0.0},
    },
    "iris": {
        "service": "luma",
        "description": "Iris/circle reveal transition",
        "category": "wipe",
        "default_params": {"resource": "%luma05.pgm", "softness": 0.1},
    },
    "barn_door": {
        "service": "luma",
        "description": "Barn door split-open effect",
        "category": "wipe",
        "default_params": {"resource": "%luma08.pgm", "softness": 0.0},
    },
}


# ---------------------------------------------------------------------------
# Project-level helpers


def _ensure_user_transitions(project: ShotcutProject) -> list[dict[str, Any]]:
    """Return the user-defined transition list for the project."""
    if not hasattr(project, "_user_transitions"):
        project._user_transitions: list[dict[str, Any]] = []  # type: ignore[attr-defined]
    return project._user_transitions  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# CRUD operations


def add_transition(
    project: ShotcutProject,
    transition_name: str,
    track_a: int,
    track_b: int,
    in_frame: int,
    out_frame: int,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a transition between *track_a* and *track_b* at the given frame range."""
    spec = TRANSITION_REGISTRY.get(transition_name)
    if spec is None:
        raise ValueError(
            f"Unknown transition {transition_name!r}. "
            f"Available: {sorted(TRANSITION_REGISTRY)}"
        )
    if in_frame >= out_frame:
        raise ValueError(
            f"in_frame ({in_frame}) must be less than out_frame ({out_frame})"
        )
    merged = {**spec["default_params"], **(params or {})}
    user_transitions = _ensure_user_transitions(project)
    entry: dict[str, Any] = {
        "index": len(user_transitions),
        "name": transition_name,
        "track_a": track_a,
        "track_b": track_b,
        "in_frame": in_frame,
        "out_frame": out_frame,
        "params": merged,
    }
    user_transitions.append(entry)
    return entry


def remove_transition(project: ShotcutProject, transition_index: int) -> dict[str, Any]:
    """Remove the transition at *transition_index* and return its data."""
    transitions = _ensure_user_transitions(project)
    if transition_index < 0 or transition_index >= len(transitions):
        raise IndexError(
            f"Transition index {transition_index} out of range (have {len(transitions)})"
        )
    return transitions.pop(transition_index)


def set_transition_param(
    project: ShotcutProject,
    transition_index: int,
    param: str,
    value: Any,
) -> dict[str, Any]:
    """Update a single parameter on the transition at *transition_index*."""
    transitions = _ensure_user_transitions(project)
    if transition_index < 0 or transition_index >= len(transitions):
        raise IndexError(f"Transition index {transition_index} out of range")
    transitions[transition_index]["params"][param] = value
    return transitions[transition_index]


def list_transitions(project: ShotcutProject) -> dict[str, Any]:
    """Return all user-defined transitions on the project."""
    transitions = _ensure_user_transitions(project)
    return {"count": len(transitions), "transitions": list(transitions)}


def list_available_transitions(category: str | None = None) -> list[dict[str, Any]]:
    """Return all registered transitions, optionally filtered by *category*."""
    result = []
    for name, spec in TRANSITION_REGISTRY.items():
        if category is not None and spec.get("category") != category:
            continue
        result.append({
            "name": name,
            "service": spec["service"],
            "description": spec["description"],
            "category": spec["category"],
            "default_params": dict(spec["default_params"]),
        })
    return result


def build_transition_element(transition: dict[str, Any]) -> str:
    """Generate an MLT XML ``<transition>`` element string."""
    name = transition.get("name", "")
    spec = TRANSITION_REGISTRY.get(name, {})
    service = spec.get("service", "luma")

    in_f = transition.get("in_frame", 0)
    out_f = transition.get("out_frame", 0)
    track_a = transition.get("track_a", 0)
    track_b = transition.get("track_b", 1)

    lines = [
        f'<transition in="{in_f}" out="{out_f}">',
        f'  <property name="mlt_service">{service}</property>',
        f'  <property name="a_track">{track_a}</property>',
        f'  <property name="b_track">{track_b}</property>',
    ]
    for key, val in transition.get("params", {}).items():
        lines.append(f'  <property name="{key}">{val}</property>')
    lines.append("</transition>")
    return "\n".join(lines)
