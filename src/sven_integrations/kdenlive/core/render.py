"""Kdenlive render management — profile selection and melt-based rendering."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Any


class RenderError(RuntimeError):
    """Raised when a render operation fails."""


# ---------------------------------------------------------------------------
# Render profiles

_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "youtube_1080p": {
        "description": "YouTube 1080p (H.264, AAC)",
        "extension": "mp4",
        "vcodec": "libx264",
        "acodec": "aac",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "bitrate_kbps": 8000,
    },
    "youtube_720p": {
        "description": "YouTube 720p (H.264, AAC)",
        "extension": "mp4",
        "vcodec": "libx264",
        "acodec": "aac",
        "width": 1280,
        "height": 720,
        "fps": 30,
        "bitrate_kbps": 4000,
    },
    "vimeo_1080p": {
        "description": "Vimeo 1080p (H.264, AAC)",
        "extension": "mp4",
        "vcodec": "libx264",
        "acodec": "aac",
        "width": 1920,
        "height": 1080,
        "fps": 25,
        "bitrate_kbps": 10000,
    },
    "dvd_pal": {
        "description": "DVD PAL (MPEG-2)",
        "extension": "mpg",
        "vcodec": "mpeg2video",
        "acodec": "ac3",
        "width": 720,
        "height": 576,
        "fps": 25,
        "bitrate_kbps": 6000,
    },
    "prores_422": {
        "description": "Apple ProRes 422",
        "extension": "mov",
        "vcodec": "prores_ks",
        "acodec": "pcm_s16le",
        "width": 1920,
        "height": 1080,
        "fps": 25,
        "bitrate_kbps": 50000,
    },
    "gif": {
        "description": "Animated GIF",
        "extension": "gif",
        "vcodec": "gif",
        "acodec": None,
        "width": 640,
        "height": 360,
        "fps": 15,
        "bitrate_kbps": 0,
    },
}

# Internal mutable state (per-process; fine for a CLI tool)
_active_profile: str = "youtube_1080p"
_render_range: tuple[float, float] | None = None
_render_progress: float = 0.0
_render_active: bool = False
_render_lock = threading.Lock()


def list_render_profiles() -> list[str]:
    """Return the names of all available render profiles."""
    return sorted(_BUILTIN_PROFILES.keys())


def set_render_profile(profile_name: str) -> None:
    """Select the active render profile."""
    global _active_profile
    if profile_name not in _BUILTIN_PROFILES:
        raise RenderError(
            f"Unknown profile '{profile_name}'. "
            f"Available: {', '.join(sorted(_BUILTIN_PROFILES))}"
        )
    _active_profile = profile_name


def set_render_range(start_s: float, end_s: float) -> None:
    """Set the timeline range to render (in seconds)."""
    global _render_range
    if start_s >= end_s:
        raise RenderError(f"start ({start_s}) must be less than end ({end_s})")
    _render_range = (start_s, end_s)


def render_to_file(
    output_path: str,
    profile: str | None = None,
    two_pass: bool = False,
    mlt_path: str | None = None,
) -> dict[str, Any]:
    """Render the project to *output_path*.

    Parameters
    ----------
    output_path:
        Destination file path.
    profile:
        Override the active profile; uses ``_active_profile`` if None.
    two_pass:
        Enable two-pass encoding (only meaningful for CBR video codecs).
    mlt_path:
        Path to an MLT project file; required when DBus is not available.
    """
    global _render_active, _render_progress

    chosen = profile or _active_profile
    if chosen not in _BUILTIN_PROFILES:
        raise RenderError(f"Unknown profile '{chosen}'")

    prof = _BUILTIN_PROFILES[chosen]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with _render_lock:
        if _render_active:
            raise RenderError("A render is already in progress")
        _render_active = True
        _render_progress = 0.0

    try:
        result = _run_melt(output_path, prof, mlt_path, two_pass)
    finally:
        with _render_lock:
            _render_active = False
            _render_progress = 1.0

    return {
        "output": str(output_path),
        "profile": chosen,
        "two_pass": two_pass,
        "returncode": result.returncode,
        "success": result.returncode == 0,
    }


def _run_melt(
    output_path: str,
    prof: dict[str, Any],
    mlt_path: str | None,
    two_pass: bool,
) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    import shutil

    melt_bin = None
    for candidate in ("melt", "melt-7", "mlt-melt"):
        if shutil.which(candidate):
            melt_bin = candidate
            break
    if melt_bin is None:
        raise RenderError("melt binary not found; install the MLT framework")

    consumer_args = [
        f"avformat:{output_path}",
        f"vcodec={prof['vcodec']}",
        f"s={prof['width']}x{prof['height']}",
        f"r={prof['fps']}",
    ]
    if prof.get("acodec"):
        consumer_args.append(f"acodec={prof['acodec']}")
    if prof.get("bitrate_kbps"):
        consumer_args.append(f"b={prof['bitrate_kbps']}k")
    if two_pass:
        consumer_args.append("two_pass=1")

    cmd = [melt_bin]
    if mlt_path:
        cmd.append(mlt_path)
    cmd += ["-consumer"] + consumer_args

    if _render_range is not None:
        start_f = int(_render_range[0] * prof["fps"])
        end_f = int(_render_range[1] * prof["fps"])
        cmd += ["-in", str(start_f), "-out", str(end_f)]

    return subprocess.run(cmd, capture_output=True, text=True, timeout=7200)


def get_render_progress() -> float:
    """Return current render progress as a float 0.0–1.0."""
    return _render_progress


def abort_render() -> None:
    """Signal the active render to stop (sets progress to 1.0)."""
    global _render_active, _render_progress
    with _render_lock:
        _render_active = False
        _render_progress = 1.0


def estimate_output_size(profile: str, duration_s: float) -> int:
    """Estimate the output file size in bytes for *profile* and *duration_s*."""
    if profile not in _BUILTIN_PROFILES:
        raise RenderError(f"Unknown profile '{profile}'")
    prof = _BUILTIN_PROFILES[profile]
    bitrate_bps = prof.get("bitrate_kbps", 0) * 1000
    if bitrate_bps <= 0:
        return 0
    return int(bitrate_bps / 8 * duration_s)
