"""Media probing utilities for Audacity projects — pure stdlib, no ffprobe."""

from __future__ import annotations

import math
import os
import wave
from dataclasses import dataclass
from typing import Any

from ..project import AudioProject


@dataclass
class MediaInfo:
    """Technical metadata for an audio file."""

    path: str
    format_name: str
    sample_rate: int | None
    channels: int | None
    duration_seconds: float | None
    bit_depth: int | None
    bitrate_kbps: float | None
    file_size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "format_name": self.format_name,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "duration_seconds": self.duration_seconds,
            "bit_depth": self.bit_depth,
            "bitrate_kbps": self.bitrate_kbps,
            "file_size_bytes": self.file_size_bytes,
        }


# ---------------------------------------------------------------------------
# Format helpers

_FORMAT_MAP: dict[str, str] = {
    ".wav": "wav",
    ".wave": "wav",
    ".mp3": "mp3",
    ".flac": "flac",
    ".ogg": "ogg",
    ".opus": "opus",
    ".aiff": "aiff",
    ".aif": "aiff",
    ".m4a": "m4a",
    ".aac": "aac",
}


def _probe_wav(path: str, file_size: int) -> MediaInfo:
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        n_frames = wf.getnframes()
    duration = n_frames / frame_rate if frame_rate > 0 else 0.0
    bit_depth = sample_width * 8
    bitrate = (frame_rate * n_channels * bit_depth) / 1000.0 if frame_rate > 0 else None
    return MediaInfo(
        path=path,
        format_name="wav",
        sample_rate=frame_rate,
        channels=n_channels,
        duration_seconds=duration,
        bit_depth=bit_depth,
        bitrate_kbps=bitrate,
        file_size_bytes=file_size,
    )


# ---------------------------------------------------------------------------
# Public API

def probe_media(path: str) -> MediaInfo:
    """Analyze an audio file and return a :class:`MediaInfo` instance.

    WAV files are parsed with the stdlib ``wave`` module.  All other formats
    receive ``None`` for fields that require a proper audio decoder.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Media file not found: {path!r}")

    file_size = os.path.getsize(path)
    ext = os.path.splitext(path)[1].lower()
    fmt = _FORMAT_MAP.get(ext, ext.lstrip(".") or "unknown")

    if ext in (".wav", ".wave"):
        try:
            return _probe_wav(path, file_size)
        except wave.Error as exc:
            raise ValueError(f"Cannot parse WAV file {path!r}: {exc}") from exc

    return MediaInfo(
        path=path,
        format_name=fmt,
        sample_rate=None,
        channels=None,
        duration_seconds=None,
        bit_depth=None,
        bitrate_kbps=None,
        file_size_bytes=file_size,
    )


def check_project_media(project: AudioProject) -> dict[str, Any]:
    """Verify that all clip source files referenced by the project exist on disk.

    Returns a dict with keys:
    - ``ok``: ``True`` only when every referenced file is present
    - ``missing``: list of paths that could not be found
    - ``found``: list of paths that exist
    """
    seen: set[str] = set()
    for track in project.tracks:
        for clip in track.clips:
            src = getattr(clip, "source_path", None)
            if src:
                seen.add(src)

    missing: list[str] = []
    found: list[str] = []
    for path in sorted(seen):
        if os.path.exists(path):
            found.append(path)
        else:
            missing.append(path)

    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "found": found,
    }


def format_duration(seconds: float) -> str:
    """Format *seconds* as ``HH:MM:SS.mmm``."""
    if not math.isfinite(seconds) or seconds < 0:
        return "00:00:00.000"
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    secs = total_s % 60
    total_m = total_s // 60
    mins = total_m % 60
    hours = total_m // 60
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"


def format_file_size(nbytes: int) -> str:
    """Return a human-readable representation of *nbytes*."""
    if nbytes < 1024:
        return f"{nbytes} B"
    for unit in ("KB", "MB", "GB", "TB"):
        nbytes_f = nbytes / 1024.0
        if nbytes_f < 1024.0 or unit == "TB":
            return f"{nbytes_f:.1f} {unit}"
        nbytes = int(nbytes_f)  # keep integer for next iteration
    return f"{nbytes} B"  # unreachable, satisfies type checker


def estimate_project_duration(project: AudioProject) -> float:
    """Return the maximum clip end time across all tracks (in seconds)."""
    max_end = 0.0
    for track in project.tracks:
        for clip in track.clips:
            end = getattr(clip, "end_seconds", None)
            if end is not None and end > max_end:
                max_end = end
    return max_end
