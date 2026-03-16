"""Shotcut media probing — ffprobe integration and project media checks."""

from __future__ import annotations

import os
import subprocess
import json
from dataclasses import dataclass
from typing import Any

from ..project import ShotcutProject


@dataclass
class MediaProbeResult:
    """Metadata extracted from a media file."""

    path: str
    format_name: str = ""
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None
    bitrate_kbps: float | None = None
    file_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "format_name": self.format_name,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "bitrate_kbps": self.bitrate_kbps,
            "file_size_bytes": self.file_size_bytes,
        }


def probe_media(path: str) -> MediaProbeResult:
    """Probe a media file using ffprobe (falls back to file-stats if unavailable).

    Uses subprocess + ffprobe's JSON output. On failure, returns a result
    populated only with file-level information.
    """
    result = MediaProbeResult(path=path)

    try:
        result.file_size_bytes = os.path.getsize(path)
    except OSError:
        pass

    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return result

        data = json.loads(proc.stdout)
        fmt = data.get("format", {})
        result.format_name = fmt.get("format_name", "")
        if fmt.get("duration"):
            result.duration_seconds = float(fmt["duration"])
        if fmt.get("bit_rate"):
            result.bitrate_kbps = float(fmt["bit_rate"]) / 1000.0

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type", "")
            if codec_type == "video" and result.video_codec is None:
                result.video_codec = stream.get("codec_name")
                result.width = stream.get("width")
                result.height = stream.get("height")
                r_frame_rate = stream.get("r_frame_rate", "")
                if r_frame_rate and "/" in r_frame_rate:
                    num, den = r_frame_rate.split("/")
                    try:
                        result.fps = float(num) / float(den)
                    except (ValueError, ZeroDivisionError):
                        pass
            elif codec_type == "audio" and result.audio_codec is None:
                result.audio_codec = stream.get("codec_name")
                result.audio_sample_rate = stream.get("sample_rate")
                if result.audio_sample_rate is not None:
                    result.audio_sample_rate = int(result.audio_sample_rate)
                result.audio_channels = stream.get("channels")

    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        # ffprobe not available or file unreadable — return partial result
        pass

    return result


def list_media(project: ShotcutProject) -> dict[str, Any]:
    """List all unique resource paths referenced across the project."""
    seen: set[str] = set()
    resources: list[str] = []
    for track in project.tracks:
        for clip in track.clips:
            res = clip.resource
            if res and res not in seen:
                seen.add(res)
                resources.append(res)
    return {"count": len(resources), "resources": resources}


def check_media_files(project: ShotcutProject) -> dict[str, Any]:
    """Check which resource paths in the project actually exist on disk.

    Returns a dict with ``ok`` (bool), ``found`` (list), and ``missing`` (list).
    """
    info = list_media(project)
    found: list[str] = []
    missing: list[str] = []
    for res in info["resources"]:
        # Skip colour strings and other non-path resources
        if res.startswith("#") or res.startswith("colour:") or res.startswith("color:"):
            found.append(res)
            continue
        if os.path.exists(res):
            found.append(res)
        else:
            missing.append(res)
    return {
        "ok": len(missing) == 0,
        "found": found,
        "missing": missing,
    }


def generate_thumbnail(
    filepath: str,
    output_path: str,
    time_s: float = 1.0,
    width: int = 320,
    height: int = 180,
) -> dict[str, Any]:
    """Extract a video thumbnail using ffmpeg.

    Falls back to an error dict if ffmpeg is unavailable.
    """
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss", str(time_s),
                "-i", filepath,
                "-vframes", "1",
                "-vf", f"scale={width}:{height}",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": proc.stderr.strip() or "ffmpeg returned non-zero exit code",
                "output_path": None,
            }
        return {"ok": True, "output_path": output_path}
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "ffmpeg not found; install ffmpeg to generate thumbnails",
            "output_path": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "ffmpeg timed out",
            "output_path": None,
        }
