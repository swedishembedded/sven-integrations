"""Shotcut export helpers — melt preset commands and codec discovery."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET

from ..backend import ShotcutError

# ---------------------------------------------------------------------------
# Built-in melt / Shotcut export presets

_BUILTIN_PRESETS: dict[str, dict[str, str]] = {
    "youtube": {
        "description": "YouTube (H.264 / AAC, MP4)",
        "vcodec": "libx264",
        "acodec": "aac",
        "extension": "mp4",
        "b": "8000k",
        "ar": "44100",
    },
    "vimeo": {
        "description": "Vimeo (H.264 / AAC, MP4)",
        "vcodec": "libx264",
        "acodec": "aac",
        "extension": "mp4",
        "b": "10000k",
        "ar": "44100",
    },
    "dnxhd": {
        "description": "Avid DNxHD (MOV)",
        "vcodec": "dnxhd",
        "acodec": "pcm_s16le",
        "extension": "mov",
        "b": "36M",
        "ar": "48000",
    },
    "prores": {
        "description": "Apple ProRes 422 (MOV)",
        "vcodec": "prores_ks",
        "acodec": "pcm_s16le",
        "extension": "mov",
        "b": "50M",
        "ar": "48000",
    },
    "gif": {
        "description": "Animated GIF",
        "vcodec": "gif",
        "acodec": "",
        "extension": "gif",
        "b": "0",
        "ar": "0",
    },
    "mp3": {
        "description": "MP3 audio only",
        "vcodec": "",
        "acodec": "libmp3lame",
        "extension": "mp3",
        "b": "0",
        "ar": "44100",
    },
}


def list_melt_presets() -> list[str]:
    """Return the names of all available export presets."""
    return sorted(_BUILTIN_PRESETS.keys())


def build_melt_command(
    mlt_path: str,
    output_path: str,
    preset: str,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
) -> list[str]:
    """Build the melt command list for rendering *mlt_path* to *output_path*.

    Parameters
    ----------
    mlt_path:
        Source MLT project file.
    output_path:
        Destination media file.
    preset:
        Name of the export preset (see ``list_melt_presets()``).
    width, height:
        Override the output resolution.
    fps:
        Override the output frame rate.
    """
    if preset not in _BUILTIN_PRESETS:
        raise ShotcutError(
            f"Unknown preset '{preset}'. Available: {', '.join(sorted(_BUILTIN_PRESETS))}"
        )

    melt = None
    for candidate in ("melt", "melt-7", "mlt-melt"):
        if shutil.which(candidate):
            melt = candidate
            break
    if melt is None:
        raise ShotcutError("melt binary not found")

    p = _BUILTIN_PRESETS[preset]

    consumer_parts = [f"avformat:{output_path}"]
    if p.get("vcodec"):
        consumer_parts.append(f"vcodec={p['vcodec']}")
    if p.get("acodec"):
        consumer_parts.append(f"acodec={p['acodec']}")
    if p.get("b") and p["b"] != "0":
        consumer_parts.append(f"b={p['b']}")
    if p.get("ar") and p["ar"] != "0":
        consumer_parts.append(f"ar={p['ar']}")
    if width and height:
        consumer_parts.append(f"s={width}x{height}")
    if fps:
        consumer_parts.append(f"r={fps}")

    cmd = [melt, mlt_path, "-consumer"] + consumer_parts
    return cmd


def estimate_duration(mlt_path: str) -> float:
    """Estimate the duration of an MLT project in seconds.

    Parses the XML and sums up track lengths.  Returns 0.0 if the file
    cannot be parsed or the duration cannot be determined.
    """
    try:
        tree = ET.parse(mlt_path)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError, OSError):
        return 0.0

    # Try to get fps from profile
    fps = 25.0
    profile_elem = root.find("profile")
    if profile_elem is not None:
        try:
            fn = int(profile_elem.get("frame_rate_num", 25))
            fd = int(profile_elem.get("frame_rate_den", 1))
            fps = fn / max(fd, 1)
        except (ValueError, TypeError):
            pass

    # Find the total frame count from playlists
    max_frames = 0
    for playlist_elem in root.findall("playlist"):
        total = 0
        for entry in playlist_elem.findall("entry"):
            try:
                in_f = int(entry.get("in", 0))
                out_f = int(entry.get("out", 0))
                total += out_f - in_f
            except (ValueError, TypeError):
                pass
        if total > max_frames:
            max_frames = total

    return max_frames / fps if fps > 0 else 0.0


def get_supported_codecs() -> dict[str, list[str]]:
    """Return a dict of codec category → list of codec names via ffmpeg -codecs.

    Falls back to a built-in list when ffmpeg is not installed.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        result = subprocess.run(
            [ffmpeg, "-codecs", "-hide_banner"],
            capture_output=True, text=True, timeout=10,
        )
        video: list[str] = []
        audio: list[str] = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            flags = parts[0]
            name = parts[1]
            if "E" not in flags:
                continue
            if "V" in flags:
                video.append(name)
            elif "A" in flags:
                audio.append(name)
        return {"video": sorted(video), "audio": sorted(audio)}

    return {
        "video": ["libx264", "libx265", "libvpx-vp9", "prores_ks", "dnxhd", "gif"],
        "audio": ["aac", "libmp3lame", "ac3", "pcm_s16le", "flac", "libvorbis"],
    }
