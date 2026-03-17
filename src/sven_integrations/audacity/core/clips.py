"""Clip management for Audacity projects — in-memory clip editing operations."""

from __future__ import annotations

import os
import uuid
import wave
from dataclasses import asdict, dataclass
from typing import Any

from ..project import AudioProject


@dataclass
class ClipInfo:
    """Rich representation of an audio clip placed on a track timeline."""

    clip_id: str
    name: str
    source_path: str
    start_seconds: float
    end_seconds: float
    trim_in: float = 0.0
    trim_out: float = 0.0
    volume: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClipInfo":
        return cls(
            clip_id=data["clip_id"],
            name=data["name"],
            source_path=data["source_path"],
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]),
            trim_in=float(data.get("trim_in", 0.0)),
            trim_out=float(data.get("trim_out", 0.0)),
            volume=float(data.get("volume", 1.0)),
        )


# ---------------------------------------------------------------------------
# Internal helpers

def _validate_track_index(project: AudioProject, track_index: int) -> None:
    if not (0 <= track_index < len(project.tracks)):
        raise IndexError(
            f"Track index {track_index} out of range (project has {len(project.tracks)} track(s))"
        )


def _validate_clip_index(project: AudioProject, track_index: int, clip_index: int) -> None:
    _validate_track_index(project, track_index)
    clips = project.tracks[track_index].clips
    if not (0 <= clip_index < len(clips)):
        raise IndexError(
            f"Clip index {clip_index} out of range (track has {len(clips)} clip(s))"
        )


# ---------------------------------------------------------------------------
# Public API

def add_clip(
    project: AudioProject,
    track_index: int,
    source_path: str,
    name: str | None = None,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    trim_in: float = 0.0,
    trim_out: float = 0.0,
    volume: float = 1.0,
) -> dict[str, Any]:
    """Append a new clip to the track at *track_index*.

    If *end_seconds* is omitted the clip duration is probed from the file
    using the stdlib ``wave`` module (WAV only); other formats receive a
    placeholder of ``start_seconds + 0.0``.
    """
    _validate_track_index(project, track_index)

    resolved_end = end_seconds
    if resolved_end is None:
        try:
            probe = probe_audio(source_path)
            resolved_end = start_seconds + probe["duration_seconds"]
        except Exception:
            resolved_end = start_seconds

    clip = ClipInfo(
        clip_id=str(uuid.uuid4()),
        name=name or os.path.basename(source_path),
        source_path=source_path,
        start_seconds=start_seconds,
        end_seconds=resolved_end,
        trim_in=trim_in,
        trim_out=trim_out,
        volume=volume,
    )
    project.tracks[track_index].clips.append(clip)  # type: ignore[arg-type]
    return {
        "action": "add_clip",
        "track_index": track_index,
        "clip": clip.to_dict(),
    }


def remove_clip(
    project: AudioProject,
    track_index: int,
    clip_index: int,
) -> dict[str, Any]:
    """Remove the clip at *clip_index* from track *track_index*."""
    _validate_clip_index(project, track_index, clip_index)
    removed = project.tracks[track_index].clips.pop(clip_index)
    removed_dict = removed.to_dict() if hasattr(removed, "to_dict") else vars(removed)
    return {
        "action": "remove_clip",
        "track_index": track_index,
        "clip_index": clip_index,
        "removed": removed_dict,
    }


def trim_clip(
    project: AudioProject,
    track_index: int,
    clip_index: int,
    trim_in: float,
    trim_out: float,
) -> dict[str, Any]:
    """Update the trim-in / trim-out offsets on an existing clip."""
    _validate_clip_index(project, track_index, clip_index)
    clip = project.tracks[track_index].clips[clip_index]
    if hasattr(clip, "trim_in"):
        clip.trim_in = trim_in  # type: ignore[assignment]
        clip.trim_out = trim_out  # type: ignore[assignment]
    return {
        "action": "trim_clip",
        "track_index": track_index,
        "clip_index": clip_index,
        "trim_in": trim_in,
        "trim_out": trim_out,
    }


def split_clip(
    project: AudioProject,
    track_index: int,
    clip_index: int,
    split_at_seconds: float,
) -> dict[str, Any]:
    """Split a clip into two halves at the given timeline position.

    The original clip's end is set to *split_at_seconds*; a second clip
    starting at *split_at_seconds* is inserted immediately after it on the
    same track.  Both clips share the same source file.
    """
    _validate_clip_index(project, track_index, clip_index)
    clip = project.tracks[track_index].clips[clip_index]

    start = getattr(clip, "start_seconds", 0.0)
    end = getattr(clip, "end_seconds", start)

    if not (start < split_at_seconds < end):
        raise ValueError(
            f"split_at_seconds={split_at_seconds} must be strictly between "
            f"clip start ({start}) and end ({end})"
        )

    source_path = getattr(clip, "source_path", "")
    name = getattr(clip, "name", os.path.basename(source_path))
    volume = getattr(clip, "volume", 1.0)
    trim_in = getattr(clip, "trim_in", 0.0)

    clip.end_seconds = split_at_seconds  # type: ignore[assignment]

    second_clip = ClipInfo(
        clip_id=str(uuid.uuid4()),
        name=f"{name} (split)",
        source_path=source_path,
        start_seconds=split_at_seconds,
        end_seconds=end,
        trim_in=trim_in + (split_at_seconds - start),
        trim_out=getattr(clip, "trim_out", 0.0),
        volume=volume,
    )
    project.tracks[track_index].clips.insert(clip_index + 1, second_clip)  # type: ignore[arg-type]

    return {
        "action": "split_clip",
        "track_index": track_index,
        "original_clip_index": clip_index,
        "split_at_seconds": split_at_seconds,
        "second_clip_index": clip_index + 1,
        "second_clip_id": second_clip.clip_id,
    }


def move_clip(
    project: AudioProject,
    track_index: int,
    clip_index: int,
    new_start_seconds: float,
) -> dict[str, Any]:
    """Slide a clip to a new start position, preserving its duration."""
    _validate_clip_index(project, track_index, clip_index)
    clip = project.tracks[track_index].clips[clip_index]

    old_start = getattr(clip, "start_seconds", 0.0)
    old_end = getattr(clip, "end_seconds", old_start)
    duration = old_end - old_start

    clip.start_seconds = new_start_seconds  # type: ignore[assignment]
    clip.end_seconds = new_start_seconds + duration  # type: ignore[assignment]

    return {
        "action": "move_clip",
        "track_index": track_index,
        "clip_index": clip_index,
        "old_start_seconds": old_start,
        "new_start_seconds": new_start_seconds,
        "end_seconds": new_start_seconds + duration,
    }


def list_clips(project: AudioProject, track_index: int) -> dict[str, Any]:
    """Return all clips on a track as a list of dicts."""
    _validate_track_index(project, track_index)
    track = project.tracks[track_index]
    clips_out: list[dict[str, Any]] = []
    for i, clip in enumerate(track.clips):
        if hasattr(clip, "to_dict"):
            d = clip.to_dict()
        else:
            d = {
                "clip_id": getattr(clip, "clip_id", ""),
                "source_path": getattr(clip, "source_path", ""),
                "start_seconds": getattr(clip, "start_seconds", 0.0),
                "end_seconds": getattr(clip, "end_seconds", 0.0),
            }
        d["index"] = i
        clips_out.append(d)
    return {
        "action": "list_clips",
        "track_index": track_index,
        "track_name": track.name,
        "count": len(clips_out),
        "clips": clips_out,
    }


def probe_audio(path: str) -> dict[str, Any]:
    """Probe an audio file and return its technical properties.

    Uses the stdlib ``wave`` module for WAV files.  For other formats
    (MP3, FLAC, etc.) falls back to basic file-system metadata only.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path!r}")

    file_size = os.path.getsize(path)
    ext = os.path.splitext(path)[1].lower()

    if ext == ".wav":
        try:
            with wave.open(path, "rb") as wf:
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                n_frames = wf.getnframes()
                duration = n_frames / frame_rate if frame_rate > 0 else 0.0
            return {
                "path": path,
                "format": "wav",
                "sample_rate": frame_rate,
                "channels": n_channels,
                "duration_seconds": duration,
                "bit_depth": sample_width * 8,
                "file_size_bytes": file_size,
            }
        except wave.Error as exc:
            raise ValueError(f"Could not read WAV file {path!r}: {exc}") from exc

    format_map = {".mp3": "mp3", ".flac": "flac", ".ogg": "ogg", ".aiff": "aiff", ".aif": "aiff"}
    fmt = format_map.get(ext, ext.lstrip(".") or "unknown")

    return {
        "path": path,
        "format": fmt,
        "sample_rate": None,
        "channels": None,
        "duration_seconds": None,
        "bit_depth": None,
        "file_size_bytes": file_size,
    }
