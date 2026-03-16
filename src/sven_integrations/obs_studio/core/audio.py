"""OBS audio source management — dataclass model and project-level operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ..project import ObsSetup

_VALID_AUDIO_TYPES = frozenset({"input", "output"})
_VALID_MONITOR_TYPES = frozenset({"none", "monitor_only", "monitor_and_output"})


@dataclass
class AudioSource:
    """Represents a dedicated audio source in an OBS configuration."""

    source_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Audio Source"
    audio_type: str = "input"        # "input" | "output"
    device: str | None = None
    volume: float = 1.0              # 0.0 – 3.0 (mul)
    muted: bool = False
    monitor_type: str = "none"       # "none" | "monitor_only" | "monitor_and_output"
    balance: float = 0.0             # -1.0 (left) – 1.0 (right)
    sync_offset_ms: int = 0

    def __post_init__(self) -> None:
        if self.audio_type not in _VALID_AUDIO_TYPES:
            raise ValueError(
                f"audio_type must be one of {sorted(_VALID_AUDIO_TYPES)}, got {self.audio_type!r}"
            )
        if self.monitor_type not in _VALID_MONITOR_TYPES:
            raise ValueError(
                f"monitor_type must be one of {sorted(_VALID_MONITOR_TYPES)}, "
                f"got {self.monitor_type!r}"
            )
        if not 0.0 <= self.volume <= 3.0:
            raise ValueError(f"volume must be in [0, 3], got {self.volume}")
        if not -1.0 <= self.balance <= 1.0:
            raise ValueError(f"balance must be in [-1, 1], got {self.balance}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "audio_type": self.audio_type,
            "device": self.device,
            "volume": self.volume,
            "muted": self.muted,
            "monitor_type": self.monitor_type,
            "balance": self.balance,
            "sync_offset_ms": self.sync_offset_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AudioSource":
        return cls(
            source_id=str(d.get("source_id", str(uuid.uuid4()))),
            name=str(d.get("name", "Audio Source")),
            audio_type=str(d.get("audio_type", "input")),
            device=d.get("device"),
            volume=float(d.get("volume", 1.0)),
            muted=bool(d.get("muted", False)),
            monitor_type=str(d.get("monitor_type", "none")),
            balance=float(d.get("balance", 0.0)),
            sync_offset_ms=int(d.get("sync_offset_ms", 0)),
        )


# ---------------------------------------------------------------------------
# Project-level helpers


def _get_sources(project: ObsSetup) -> list[dict[str, Any]]:
    return project.data.setdefault("audio_sources", [])  # type: ignore[attr-defined]


def add_audio_source(
    project: ObsSetup,
    name: str,
    audio_type: str = "input",
    device: str | None = None,
    volume: float = 1.0,
    muted: bool = False,
    monitor_type: str = "none",
) -> dict[str, Any]:
    """Create and register a new audio source on the project."""
    source = AudioSource(
        name=name,
        audio_type=audio_type,
        device=device,
        volume=volume,
        muted=muted,
        monitor_type=monitor_type,
    )
    sources = _get_sources(project)
    sources.append(source.to_dict())
    return source.to_dict()


def _at_index(project: ObsSetup, index: int) -> dict[str, Any]:
    sources = _get_sources(project)
    if index < 0 or index >= len(sources):
        raise IndexError(f"Audio source index {index} out of range (have {len(sources)})")
    return sources[index]


def remove_audio_source(project: ObsSetup, index: int) -> dict[str, Any]:
    """Remove the audio source at *index* and return its data."""
    sources = _get_sources(project)
    if index < 0 or index >= len(sources):
        raise IndexError(f"Audio source index {index} out of range")
    return sources.pop(index)


def set_volume(project: ObsSetup, index: int, volume: float) -> dict[str, Any]:
    """Set the multiplier volume (0–3) of the source at *index*."""
    if not 0.0 <= volume <= 3.0:
        raise ValueError(f"volume must be in [0, 3], got {volume}")
    src = _at_index(project, index)
    src["volume"] = volume
    return src


def mute_source(project: ObsSetup, index: int) -> dict[str, Any]:
    """Mute the audio source at *index*."""
    src = _at_index(project, index)
    src["muted"] = True
    return src


def unmute_source(project: ObsSetup, index: int) -> dict[str, Any]:
    """Unmute the audio source at *index*."""
    src = _at_index(project, index)
    src["muted"] = False
    return src


def set_monitor(project: ObsSetup, index: int, monitor_type: str) -> dict[str, Any]:
    """Change the monitor mode for the audio source at *index*."""
    if monitor_type not in _VALID_MONITOR_TYPES:
        raise ValueError(
            f"monitor_type must be one of {sorted(_VALID_MONITOR_TYPES)}, got {monitor_type!r}"
        )
    src = _at_index(project, index)
    src["monitor_type"] = monitor_type
    return src


def set_balance(project: ObsSetup, index: int, balance: float) -> dict[str, Any]:
    """Set the stereo balance (-1 left … 1 right) for the audio source at *index*."""
    if not -1.0 <= balance <= 1.0:
        raise ValueError(f"balance must be in [-1, 1], got {balance}")
    src = _at_index(project, index)
    src["balance"] = balance
    return src


def set_sync_offset(project: ObsSetup, index: int, offset_ms: int) -> dict[str, Any]:
    """Set the sync offset in milliseconds for the audio source at *index*."""
    src = _at_index(project, index)
    src["sync_offset_ms"] = int(offset_ms)
    return src


def list_audio(project: ObsSetup) -> dict[str, Any]:
    """Return all audio sources stored on the project."""
    sources = _get_sources(project)
    return {"count": len(sources), "audio_sources": list(sources)}


def build_audio_requests(project: ObsSetup) -> list[dict[str, Any]]:
    """Build a list of obs-websocket request dicts to configure all audio sources."""
    requests: list[dict[str, Any]] = []
    for src in _get_sources(project):
        name = src.get("name", "")
        requests.append({
            "requestType": "SetInputVolume",
            "requestData": {"inputName": name, "inputVolumeMul": src.get("volume", 1.0)},
        })
        requests.append({
            "requestType": "SetInputMute",
            "requestData": {"inputName": name, "inputMuted": src.get("muted", False)},
        })
        requests.append({
            "requestType": "SetInputAudioMonitorType",
            "requestData": {"inputName": name, "monitorType": src.get("monitor_type", "none")},
        })
        requests.append({
            "requestType": "SetInputAudioBalance",
            "requestData": {"inputName": name, "inputAudioBalance": src.get("balance", 0.0)},
        })
        requests.append({
            "requestType": "SetInputAudioSyncOffset",
            "requestData": {
                "inputName": name,
                "inputAudioSyncOffset": src.get("sync_offset_ms", 0),
            },
        })
    return requests
