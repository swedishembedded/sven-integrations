"""Kdenlive project model — dataclass-based project/track/clip representation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimelineClip:
    """A single clip placed on a timeline track."""

    clip_id: str
    bin_id: str
    in_point: float   # seconds (source in-point)
    out_point: float  # seconds (source out-point)
    position: float   # seconds (timeline placement)
    speed: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "bin_id": self.bin_id,
            "in_point": self.in_point,
            "out_point": self.out_point,
            "position": self.position,
            "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TimelineClip":
        return cls(
            clip_id=str(d["clip_id"]),
            bin_id=str(d["bin_id"]),
            in_point=float(d["in_point"]),
            out_point=float(d["out_point"]),
            position=float(d["position"]),
            speed=float(d.get("speed", 1.0)),
        )


@dataclass
class TimelineTrack:
    """A track in the Kdenlive timeline."""

    track_id: str
    name: str
    kind: str          # "video" | "audio"
    muted: bool = False
    locked: bool = False
    clips: list[TimelineClip] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "kind": self.kind,
            "muted": self.muted,
            "locked": self.locked,
            "clips": [c.to_dict() for c in self.clips],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TimelineTrack":
        return cls(
            track_id=str(d["track_id"]),
            name=str(d["name"]),
            kind=str(d.get("kind", "video")),
            muted=bool(d.get("muted", False)),
            locked=bool(d.get("locked", False)),
            clips=[TimelineClip.from_dict(c) for c in d.get("clips", [])],
        )


@dataclass
class KdenliveProject:
    """In-memory representation of a Kdenlive project."""

    project_path: str | None = None
    profile_name: str = "hdv_1080_25p"
    fps_num: int = 25
    fps_den: int = 1
    width: int = 1920
    height: int = 1080
    tracks: list[TimelineTrack] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Track operations

    def add_track(self, track: TimelineTrack) -> None:
        self.tracks.append(track)

    def remove_track(self, track_id: str) -> bool:
        for i, t in enumerate(self.tracks):
            if t.track_id == track_id:
                del self.tracks[i]
                return True
        return False

    def find_track(self, name: str) -> TimelineTrack | None:
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    # ------------------------------------------------------------------
    # Clip operations

    def add_clip(self, track_id: str, clip: TimelineClip) -> bool:
        for t in self.tracks:
            if t.track_id == track_id:
                t.clips.append(clip)
                return True
        return False

    # ------------------------------------------------------------------
    # Properties

    @property
    def duration_seconds(self) -> float:
        """End time of the last clip across all tracks."""
        end = 0.0
        for track in self.tracks:
            for clip in track.clips:
                duration = (clip.out_point - clip.in_point) / max(clip.speed, 1e-9)
                clip_end = clip.position + duration
                if clip_end > end:
                    end = clip_end
        return end

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "profile_name": self.profile_name,
            "fps_num": self.fps_num,
            "fps_den": self.fps_den,
            "width": self.width,
            "height": self.height,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "KdenliveProject":
        proj = cls(
            project_path=d.get("project_path"),
            profile_name=str(d.get("profile_name", "hdv_1080_25p")),
            fps_num=int(d.get("fps_num", 25)),
            fps_den=int(d.get("fps_den", 1)),
            width=int(d.get("width", 1920)),
            height=int(d.get("height", 1080)),
        )
        proj.tracks = [TimelineTrack.from_dict(t) for t in d.get("tracks", [])]
        return proj


def new_track_id() -> str:
    return f"track_{uuid.uuid4().hex[:8]}"


def new_clip_id() -> str:
    return f"clip_{uuid.uuid4().hex[:8]}"
