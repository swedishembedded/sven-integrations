"""Kdenlive timeline guide (chapter marker) management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..project import KdenliveProject

_VALID_GUIDE_TYPES = frozenset({"chapter", "section", "comment"})


@dataclass
class TimelineGuide:
    """A named marker placed on the Kdenlive timeline."""

    guide_id: int
    position_seconds: float
    label: str = ""
    guide_type: str = "chapter"   # chapter | section | comment
    comment: str = ""

    def __post_init__(self) -> None:
        if self.guide_type not in _VALID_GUIDE_TYPES:
            raise ValueError(
                f"guide_type must be one of {sorted(_VALID_GUIDE_TYPES)}, "
                f"got {self.guide_type!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "guide_id": self.guide_id,
            "position_seconds": self.position_seconds,
            "label": self.label,
            "guide_type": self.guide_type,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TimelineGuide":
        return cls(
            guide_id=int(d["guide_id"]),
            position_seconds=float(d["position_seconds"]),
            label=str(d.get("label", "")),
            guide_type=str(d.get("guide_type", "chapter")),
            comment=str(d.get("comment", "")),
        )


# ---------------------------------------------------------------------------
# Project-level helpers


def _ensure_guides(project: KdenliveProject) -> list[dict[str, Any]]:
    """Return the project's guide list, bootstrapping from data if needed."""
    data: dict[str, Any] = getattr(project, "data", {})
    if not hasattr(project, "_guides"):
        project._guides: list[dict[str, Any]] = list(data.get("guides", []))  # type: ignore[attr-defined]
    return project._guides  # type: ignore[attr-defined]


def _sync_guides(project: KdenliveProject, guides: list[dict[str, Any]]) -> None:
    if not hasattr(project, "data"):
        project.data = {}  # type: ignore[attr-defined]
    project.data["guides"] = guides  # type: ignore[attr-defined]


def _next_guide_id(guides: list[dict[str, Any]]) -> int:
    if not guides:
        return 1
    return max(g["guide_id"] for g in guides) + 1


def add_guide(
    project: KdenliveProject,
    position_seconds: float,
    label: str = "",
    guide_type: str = "chapter",
    comment: str = "",
) -> dict[str, Any]:
    """Add a timeline guide at *position_seconds* and return its dict."""
    guides = _ensure_guides(project)
    guide = TimelineGuide(
        guide_id=_next_guide_id(guides),
        position_seconds=position_seconds,
        label=label,
        guide_type=guide_type,
        comment=comment,
    )
    entry = guide.to_dict()
    guides.append(entry)
    _sync_guides(project, guides)
    return entry


def remove_guide(project: KdenliveProject, guide_id: int) -> dict[str, Any]:
    """Remove the guide with *guide_id* and return its data."""
    guides = _ensure_guides(project)
    for i, g in enumerate(guides):
        if g["guide_id"] == guide_id:
            removed = guides.pop(i)
            _sync_guides(project, guides)
            return removed
    raise KeyError(f"Guide {guide_id} not found")


def list_guides(project: KdenliveProject) -> dict[str, Any]:
    """Return all guides sorted by timeline position."""
    guides = _ensure_guides(project)
    sorted_guides = sorted(guides, key=lambda g: g["position_seconds"])
    return {"count": len(sorted_guides), "guides": sorted_guides}


def build_guide_xml(guide: dict[str, Any]) -> str:
    """Build an MLT XML comment/chapter marker string for *guide*."""
    guide_type = guide.get("guide_type", "chapter")
    position = guide.get("position_seconds", 0.0)
    label = guide.get("label", "")
    comment = guide.get("comment", "")

    # Convert seconds to MLT timecode HH:MM:SS.mmm
    hours = int(position // 3600)
    minutes = int((position % 3600) // 60)
    seconds = position % 60
    timecode = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    type_attr = {
        "chapter": "0",
        "section": "1",
        "comment": "2",
    }.get(guide_type, "0")

    parts = [
        f'<guide id="{guide.get("guide_id", 0)}"',
        f' position="{timecode}"',
        f' type="{type_attr}"',
        f' comment="{label}"',
    ]
    if comment:
        parts.append(f' description="{comment}"')
    parts.append(" />")
    return "".join(parts)
