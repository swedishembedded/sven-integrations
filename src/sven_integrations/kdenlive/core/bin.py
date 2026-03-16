"""Kdenlive project bin (media library) management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..project import KdenliveProject

_VALID_CLIP_TYPES = frozenset({"video", "audio", "image", "color", "title"})


def _next_clip_id(clips: list[dict[str, Any]]) -> str:
    """Generate the next sequential bin clip ID like C001, C002, …"""
    return f"C{len(clips) + 1:03d}"


@dataclass
class BinClip:
    """Represents a media item in the Kdenlive project bin."""

    clip_id: str
    name: str
    source_path: str
    duration_seconds: float | None = None
    clip_type: str = "video"     # video | audio | image | color | title
    imported_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.clip_type not in _VALID_CLIP_TYPES:
            raise ValueError(
                f"clip_type must be one of {sorted(_VALID_CLIP_TYPES)}, "
                f"got {self.clip_type!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "name": self.name,
            "source_path": self.source_path,
            "duration_seconds": self.duration_seconds,
            "clip_type": self.clip_type,
            "imported_at": self.imported_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BinClip":
        return cls(
            clip_id=str(d["clip_id"]),
            name=str(d["name"]),
            source_path=str(d["source_path"]),
            duration_seconds=float(d["duration_seconds"]) if d.get("duration_seconds") is not None else None,
            clip_type=str(d.get("clip_type", "video")),
            imported_at=float(d.get("imported_at", time.time())),
        )


# ---------------------------------------------------------------------------
# Project-level helpers


def _get_clips(project: KdenliveProject) -> list[dict[str, Any]]:
    if not hasattr(project, "_bin_clips"):
        project._bin_clips: list[dict[str, Any]] = []  # type: ignore[attr-defined]
    # Mirror in to_dict compat: use a side-channel attribute
    # (KdenliveProject stores extra data via _bin_clips)
    return project._bin_clips  # type: ignore[attr-defined]


def _ensure_bin(project: KdenliveProject) -> list[dict[str, Any]]:
    """Return the bin clips list, bootstrapping from project.data if present."""
    data: dict[str, Any] = getattr(project, "data", None) or {}
    if not hasattr(project, "_bin_clips"):
        project._bin_clips = list(data.get("bin_clips", []))  # type: ignore[attr-defined]
    return project._bin_clips  # type: ignore[attr-defined]


def import_clip(
    project: KdenliveProject,
    source_path: str,
    name: str | None = None,
    duration: float | None = None,
    clip_type: str = "video",
) -> dict[str, Any]:
    """Add a media file to the project bin and return its clip dict."""
    clips = _ensure_bin(project)
    clip_id = _next_clip_id(clips)
    effective_name = name or source_path.rsplit("/", 1)[-1]
    clip = BinClip(
        clip_id=clip_id,
        name=effective_name,
        source_path=source_path,
        duration_seconds=duration,
        clip_type=clip_type,
    )
    entry = clip.to_dict()
    clips.append(entry)
    # Sync to project.data so serialisation round-trips work
    _sync_to_project_data(project, clips)
    return entry


def remove_clip(project: KdenliveProject, clip_id: str) -> dict[str, Any]:
    """Remove a clip by its ID and return its data."""
    clips = _ensure_bin(project)
    for i, c in enumerate(clips):
        if c["clip_id"] == clip_id:
            removed = clips.pop(i)
            _sync_to_project_data(project, clips)
            return removed
    raise KeyError(f"Clip {clip_id!r} not found in bin")


def list_clips(project: KdenliveProject) -> dict[str, Any]:
    """Return all clips in the project bin."""
    clips = _ensure_bin(project)
    return {"count": len(clips), "clips": list(clips)}


def get_clip(project: KdenliveProject, clip_id: str) -> dict[str, Any]:
    """Return a single clip by ID."""
    clips = _ensure_bin(project)
    for c in clips:
        if c["clip_id"] == clip_id:
            return dict(c)
    raise KeyError(f"Clip {clip_id!r} not found in bin")


def build_mlt_producer(clip: dict[str, Any]) -> dict[str, Any]:
    """Build MLT XML producer element attributes from a clip dict."""
    attrs: dict[str, Any] = {
        "id": clip["clip_id"],
        "resource": clip["source_path"],
        "in": "0",
        "out": "-1",
    }
    if clip.get("duration_seconds") is not None:
        fps = 25  # default assumption; real projects would use project fps
        out_frame = int(clip["duration_seconds"] * fps) - 1
        attrs["out"] = str(max(0, out_frame))

    type_map = {
        "color": "color",
        "image": "pixbuf",
        "audio": "avformat",
        "video": "avformat",
        "title": "kdenlivetitle",
    }
    clip_type = clip.get("clip_type", "video")
    attrs["mlt_service"] = type_map.get(clip_type, "avformat")
    attrs["kdenlive:clip_type"] = clip_type
    attrs["kdenlive:clipname"] = clip.get("name", "")
    return attrs


def _sync_to_project_data(
    project: KdenliveProject,
    clips: list[dict[str, Any]],
) -> None:
    """Write the bin_clips list back to project.data for serialisation."""
    if not hasattr(project, "data"):
        project.data = {}  # type: ignore[attr-defined]
    project.data["bin_clips"] = clips  # type: ignore[attr-defined]
