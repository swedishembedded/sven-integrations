"""Export helpers for Audacity via mod-script-pipe Export2 command."""

from __future__ import annotations

from ..backend import AudacityBackend

_FORMAT_IDS = {
    "wav": "WAV",
    "mp3": "MP3",
    "flac": "FLAC",
    "ogg": "OGG",
    "aiff": "AIFF",
}


def build_export_command(fmt: str, path: str, **kwargs: object) -> str:
    """Build an Audacity Export2 command string.

    Returns the raw command text without sending it.
    Extra keyword arguments are appended as ``Key=Value`` pairs.
    """
    fmt_upper = _FORMAT_IDS.get(fmt.lower(), fmt.upper())
    parts = [f"Export2: Filename={path!r} NumChannels=2 ExportFormat={fmt_upper}"]
    for key, val in kwargs.items():
        parts.append(f"{key}={val}")
    return " ".join(parts)


def export_wav(
    backend: AudacityBackend,
    path: str,
    bit_depth: int = 16,
) -> str:
    """Export the project as a WAV file.

    *bit_depth* must be 16, 24, or 32.
    """
    if bit_depth not in (16, 24, 32):
        raise ValueError(f"WAV bit depth must be 16, 24, or 32, got {bit_depth}")
    encoding = {16: "PCM_16_bit", 24: "PCM_24_bit", 32: "PCM_32_bit"}[bit_depth]
    cmd = build_export_command("wav", path, SubFormat=encoding)
    return backend.send_command(cmd)


def export_mp3(
    backend: AudacityBackend,
    path: str,
    quality: int = 2,
) -> str:
    """Export as MP3.

    *quality* can be a VBR quality level 0–9 (0=best) or an ABR bitrate kbps.
    Values 0–9 are treated as VBR; values ≥ 32 as CBR bitrate.
    """
    if quality < 0 or quality > 320:
        raise ValueError(f"MP3 quality must be 0-9 (VBR) or 32-320 (CBR kbps), got {quality}")
    if quality <= 9:
        cmd = build_export_command("mp3", path, VBRMode=quality)
    else:
        cmd = build_export_command("mp3", path, CBRBitrate=quality)
    return backend.send_command(cmd)


def export_flac(
    backend: AudacityBackend,
    path: str,
    compression: int = 5,
) -> str:
    """Export as FLAC with compression level 0 (fastest) to 8 (smallest)."""
    if not (0 <= compression <= 8):
        raise ValueError(f"FLAC compression must be 0-8, got {compression}")
    cmd = build_export_command("flac", path, Level=compression)
    return backend.send_command(cmd)


def export_ogg(
    backend: AudacityBackend,
    path: str,
    quality: float = 5.0,
) -> str:
    """Export as Ogg Vorbis with quality in the range -1 to 10."""
    if not (-1.0 <= quality <= 10.0):
        raise ValueError(f"OGG quality must be between -1 and 10, got {quality}")
    cmd = build_export_command("ogg", path, Quality=quality)
    return backend.send_command(cmd)


def export_aiff(backend: AudacityBackend, path: str) -> str:
    """Export as AIFF (standard 16-bit PCM)."""
    cmd = build_export_command("aiff", path)
    return backend.send_command(cmd)
