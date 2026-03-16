"""Label track management for Audacity projects — in-memory label editing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, asdict
from typing import Any

from ..project import AudioProject


@dataclass
class LabelMark:
    """A single label placed on the timeline.

    Point labels have *end_seconds* set to ``None``; region labels have both
    *start_seconds* and *end_seconds* set.
    """

    label_id: str
    start_seconds: float
    end_seconds: float | None
    text: str

    @property
    def is_region(self) -> bool:
        return self.end_seconds is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_id": self.label_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
            "type": "region" if self.is_region else "point",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LabelMark":
        return cls(
            label_id=data["label_id"],
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]) if data.get("end_seconds") is not None else None,
            text=data.get("text", ""),
        )


# ---------------------------------------------------------------------------
# Storage helpers

def _get_labels(project: AudioProject) -> list[dict[str, Any]]:
    """Return the mutable label list stored in ``project.data``."""
    return project.data.setdefault("labels", [])


# ---------------------------------------------------------------------------
# Public API

def add_label(
    project: AudioProject,
    start: float,
    end: float | None = None,
    text: str = "",
) -> dict[str, Any]:
    """Add a label at *start* seconds (optionally spanning to *end*).

    Labels are persisted inside ``project.data["labels"]`` as plain dicts
    so they survive JSON round-trips without a custom encoder.
    """
    label = LabelMark(
        label_id=str(uuid.uuid4()),
        start_seconds=start,
        end_seconds=end,
        text=text,
    )
    _get_labels(project).append(label.to_dict())
    return {
        "action": "add_label",
        "label": label.to_dict(),
    }


def remove_label(project: AudioProject, label_id: str) -> dict[str, Any]:
    """Remove the label with the given *label_id*.

    Raises ``KeyError`` if no matching label exists.
    """
    labels = _get_labels(project)
    for i, entry in enumerate(labels):
        if entry.get("label_id") == label_id:
            removed = labels.pop(i)
            return {
                "action": "remove_label",
                "removed": removed,
            }
    raise KeyError(f"No label with id {label_id!r}")


def list_labels(project: AudioProject) -> dict[str, Any]:
    """Return all labels sorted ascending by start time."""
    labels = sorted(
        _get_labels(project),
        key=lambda d: float(d.get("start_seconds", 0.0)),
    )
    for entry in labels:
        if "type" not in entry:
            entry["type"] = "region" if entry.get("end_seconds") is not None else "point"
    return {
        "action": "list_labels",
        "count": len(labels),
        "labels": labels,
    }


def build_label_track_commands(project: AudioProject) -> list[str]:
    """Build a sequence of mod-script-pipe commands to recreate all labels.

    The returned list can be sent to ``AudacityBackend.send_command`` in
    order to create one new label track and populate it with every stored
    label.
    """
    labels = sorted(
        _get_labels(project),
        key=lambda d: float(d.get("start_seconds", 0.0)),
    )
    if not labels:
        return []

    commands: list[str] = ["NewLabelTrack"]
    for entry in labels:
        start = float(entry.get("start_seconds", 0.0))
        end = entry.get("end_seconds")
        text = entry.get("text", "").replace('"', '\\"')

        if end is not None:
            commands.append(
                f'AddLabelPlaying: Start={start} End={float(end)} Text="{text}"'
            )
        else:
            commands.append(
                f'AddLabelPlaying: Start={start} End={start} Text="{text}"'
            )
    return commands
