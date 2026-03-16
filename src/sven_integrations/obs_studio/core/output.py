"""OBS output configuration — streaming, recording, and encoding presets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..project import ObsSetup

_VALID_FORMATS = frozenset({"mkv", "mp4", "flv", "mov"})
_VALID_QUALITIES = frozenset({"high", "medium", "low", "lossless"})


@dataclass
class StreamingConfig:
    """Holds Zoom/RTMP streaming destination details."""

    service: str = "custom"
    server_url: str = ""
    stream_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "server_url": self.server_url,
            "stream_key": self.stream_key,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StreamingConfig":
        return cls(
            service=str(d.get("service", "custom")),
            server_url=str(d.get("server_url", "")),
            stream_key=str(d.get("stream_key", "")),
        )


@dataclass
class RecordingConfig:
    """Local recording destination and format settings."""

    output_path: str = ""
    output_format: str = "mkv"    # mkv | mp4 | flv | mov
    quality: str = "high"         # high | medium | low | lossless

    def __post_init__(self) -> None:
        if self.output_format not in _VALID_FORMATS:
            raise ValueError(
                f"output_format must be one of {sorted(_VALID_FORMATS)}, "
                f"got {self.output_format!r}"
            )
        if self.quality not in _VALID_QUALITIES:
            raise ValueError(
                f"quality must be one of {sorted(_VALID_QUALITIES)}, got {self.quality!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "output_format": self.output_format,
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RecordingConfig":
        return cls(
            output_path=str(d.get("output_path", "")),
            output_format=str(d.get("output_format", "mkv")),
            quality=str(d.get("quality", "high")),
        )


@dataclass
class OutputSettings:
    """Video/audio encoding parameters for a stream or recording."""

    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_bitrate_kbps: int = 6000
    audio_bitrate_kbps: int = 160
    encoder: str = "x264"
    preset: str = "veryfast"

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "video_bitrate_kbps": self.video_bitrate_kbps,
            "audio_bitrate_kbps": self.audio_bitrate_kbps,
            "encoder": self.encoder,
            "preset": self.preset,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutputSettings":
        return cls(
            width=int(d.get("width", 1920)),
            height=int(d.get("height", 1080)),
            fps=int(d.get("fps", 30)),
            video_bitrate_kbps=int(d.get("video_bitrate_kbps", 6000)),
            audio_bitrate_kbps=int(d.get("audio_bitrate_kbps", 160)),
            encoder=str(d.get("encoder", "x264")),
            preset=str(d.get("preset", "veryfast")),
        )


# ---------------------------------------------------------------------------
# Built-in presets

ENCODING_PRESETS: dict[str, OutputSettings] = {
    "streaming_720p": OutputSettings(
        width=1280, height=720, fps=30,
        video_bitrate_kbps=3000, audio_bitrate_kbps=128,
        encoder="x264", preset="veryfast",
    ),
    "streaming_1080p": OutputSettings(
        width=1920, height=1080, fps=60,
        video_bitrate_kbps=6000, audio_bitrate_kbps=160,
        encoder="x264", preset="veryfast",
    ),
    "recording_1080p_high": OutputSettings(
        width=1920, height=1080, fps=60,
        video_bitrate_kbps=40000, audio_bitrate_kbps=320,
        encoder="x264", preset="medium",
    ),
    "recording_4k": OutputSettings(
        width=3840, height=2160, fps=30,
        video_bitrate_kbps=80000, audio_bitrate_kbps=320,
        encoder="x264", preset="slow",
    ),
    "social_media": OutputSettings(
        width=1080, height=1080, fps=30,
        video_bitrate_kbps=4000, audio_bitrate_kbps=192,
        encoder="x264", preset="fast",
    ),
    "low_bandwidth": OutputSettings(
        width=854, height=480, fps=30,
        video_bitrate_kbps=1500, audio_bitrate_kbps=96,
        encoder="x264", preset="ultrafast",
    ),
}


# ---------------------------------------------------------------------------
# Project-level helpers


def _output_section(project: ObsSetup) -> dict[str, Any]:
    return project.data.setdefault("output", {})  # type: ignore[attr-defined]


def set_streaming(
    project: ObsSetup,
    service: str,
    server: str,
    key: str,
) -> dict[str, Any]:
    """Store streaming configuration on the project."""
    cfg = StreamingConfig(service=service, server_url=server, stream_key=key)
    _output_section(project)["streaming"] = cfg.to_dict()
    return cfg.to_dict()


def set_recording(
    project: ObsSetup,
    path: str,
    fmt: str = "mkv",
    quality: str = "high",
) -> dict[str, Any]:
    """Store recording configuration on the project."""
    cfg = RecordingConfig(output_path=path, output_format=fmt, quality=quality)
    _output_section(project)["recording"] = cfg.to_dict()
    return cfg.to_dict()


def set_output_settings(
    project: ObsSetup,
    width: int,
    height: int,
    fps: int,
    video_bitrate: int,
    audio_bitrate: int,
    encoder: str,
    preset: str,
) -> dict[str, Any]:
    """Store encoder output settings on the project."""
    settings = OutputSettings(
        width=width,
        height=height,
        fps=fps,
        video_bitrate_kbps=video_bitrate,
        audio_bitrate_kbps=audio_bitrate,
        encoder=encoder,
        preset=preset,
    )
    _output_section(project)["settings"] = settings.to_dict()
    return settings.to_dict()


def get_output_info(project: ObsSetup) -> dict[str, Any]:
    """Return the full output configuration stored on the project."""
    return dict(_output_section(project))


def list_presets() -> list[dict[str, Any]]:
    """Return all built-in encoding presets."""
    return [
        {"name": name, **settings.to_dict()}
        for name, settings in ENCODING_PRESETS.items()
    ]
