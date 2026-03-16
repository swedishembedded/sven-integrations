"""Shotcut project model — dataclass-based MLT project representation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MltClip:
    """A single clip (entry) on an MLT playlist."""

    clip_id: str
    resource: str       # file path or colour string
    in_point: int       # frames
    out_point: int      # frames
    position: int       # frames (offset within the playlist / tractor)
    filters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "resource": self.resource,
            "in_point": self.in_point,
            "out_point": self.out_point,
            "position": self.position,
            "filters": list(self.filters),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MltClip":
        return cls(
            clip_id=str(d["clip_id"]),
            resource=str(d["resource"]),
            in_point=int(d["in_point"]),
            out_point=int(d["out_point"]),
            position=int(d["position"]),
            filters=list(d.get("filters", [])),
        )


@dataclass
class MltTrack:
    """A track (playlist) in the MLT tractor."""

    track_id: str
    name: str
    hide: int = 0      # 0=visible, 1=video hidden, 2=audio hidden
    clips: list[MltClip] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "hide": self.hide,
            "clips": [c.to_dict() for c in self.clips],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MltTrack":
        return cls(
            track_id=str(d["track_id"]),
            name=str(d["name"]),
            hide=int(d.get("hide", 0)),
            clips=[MltClip.from_dict(c) for c in d.get("clips", [])],
        )


@dataclass
class ShotcutProject:
    """In-memory representation of a Shotcut / MLT project."""

    mlt_path: str | None = None
    profile_name: str = "atsc_1080p_25"
    width: int = 1920
    height: int = 1080
    fps: float = 25.0
    tracks: list[MltTrack] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Track operations

    def add_track(self, track: MltTrack) -> None:
        self.tracks.append(track)

    def remove_track(self, track_id: str) -> bool:
        for i, t in enumerate(self.tracks):
            if t.track_id == track_id:
                del self.tracks[i]
                return True
        return False

    # ------------------------------------------------------------------
    # Clip operations

    def add_clip_to_track(self, track_id: str, clip: MltClip) -> bool:
        for t in self.tracks:
            if t.track_id == track_id:
                t.clips.append(clip)
                return True
        return False

    def find_clip(self, clip_id: str) -> MltClip | None:
        for t in self.tracks:
            for c in t.clips:
                if c.clip_id == clip_id:
                    return c
        return None

    # ------------------------------------------------------------------
    # Properties

    @property
    def timeline_duration_frames(self) -> int:
        """Total duration in frames (end of last clip across all tracks)."""
        end = 0
        for track in self.tracks:
            for clip in track.clips:
                clip_end = clip.position + (clip.out_point - clip.in_point)
                if clip_end > end:
                    end = clip_end
        return end

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "mlt_path": self.mlt_path,
            "profile_name": self.profile_name,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ShotcutProject":
        proj = cls(
            mlt_path=d.get("mlt_path"),
            profile_name=str(d.get("profile_name", "atsc_1080p_25")),
            width=int(d.get("width", 1920)),
            height=int(d.get("height", 1080)),
            fps=float(d.get("fps", 25.0)),
        )
        proj.tracks = [MltTrack.from_dict(t) for t in d.get("tracks", [])]
        return proj


def new_track_id() -> str:
    return f"track_{uuid.uuid4().hex[:8]}"


def new_clip_id() -> str:
    return f"clip_{uuid.uuid4().hex[:8]}"
