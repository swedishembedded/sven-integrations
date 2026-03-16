"""Audacity project model — dataclass representation of an Audacity audio project."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AudioClip:
    """A single audio clip within a track."""

    clip_id: str
    start_seconds: float
    end_seconds: float
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioClip":
        return cls(
            clip_id=data["clip_id"],
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]),
            source_path=data["source_path"],
        )


@dataclass
class AudioTrack:
    """A single track inside an audio project."""

    track_id: str
    name: str
    kind: str  # mono | stereo | label | time
    muted: bool = False
    soloed: bool = False
    gain: float = 1.0
    pan: float = 0.0
    clips: list[AudioClip] = field(default_factory=list)

    _VALID_KINDS = frozenset({"mono", "stereo", "label", "time"})

    def __post_init__(self) -> None:
        if self.kind not in self._VALID_KINDS:
            raise ValueError(f"Track kind must be one of {self._VALID_KINDS}, got {self.kind!r}")
        if not (-1.0 <= self.pan <= 1.0):
            raise ValueError(f"Pan must be between -1.0 and 1.0, got {self.pan}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("_VALID_KINDS", None)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioTrack":
        clips = [AudioClip.from_dict(c) for c in data.get("clips", [])]
        return cls(
            track_id=data["track_id"],
            name=data["name"],
            kind=data["kind"],
            muted=bool(data.get("muted", False)),
            soloed=bool(data.get("soloed", False)),
            gain=float(data.get("gain", 1.0)),
            pan=float(data.get("pan", 0.0)),
            clips=clips,
        )


@dataclass
class AudioProject:
    """Top-level model for an Audacity project."""

    name: str
    sample_rate: int = 44100
    channels: int = 2
    bit_depth: int = 16
    duration_seconds: float = 0.0
    tracks: list[AudioTrack] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def add_track(self, track: AudioTrack) -> None:
        self.tracks.append(track)

    def remove_track(self, track_id: str) -> AudioTrack:
        for i, t in enumerate(self.tracks):
            if t.track_id == track_id:
                return self.tracks.pop(i)
        raise KeyError(f"No track with id {track_id!r}")

    def find_track(self, name: str) -> AudioTrack | None:
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    def total_tracks(self) -> int:
        return len(self.tracks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "duration_seconds": self.duration_seconds,
            "tracks": [t.to_dict() for t in self.tracks],
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AudioProject":
        tracks = [AudioTrack.from_dict(t) for t in raw.get("tracks", [])]
        return cls(
            name=raw["name"],
            sample_rate=int(raw.get("sample_rate", 44100)),
            channels=int(raw.get("channels", 2)),
            bit_depth=int(raw.get("bit_depth", 16)),
            duration_seconds=float(raw.get("duration_seconds", 0.0)),
            tracks=tracks,
            data=raw.get("data", {}),
        )
