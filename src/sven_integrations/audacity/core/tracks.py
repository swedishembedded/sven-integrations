"""Track management commands sent via Audacity's mod-script-pipe."""

from __future__ import annotations

from ..backend import AudacityBackend


def new_mono_track(backend: AudacityBackend, name: str) -> str:
    """Create a new mono audio track named *name*."""
    reply = backend.send_command(f"NewMonoTrack")
    if name:
        backend.send_command(f"SetTrackStatus: Name={name!r}")
    return reply


def new_stereo_track(backend: AudacityBackend, name: str) -> str:
    """Create a new stereo audio track named *name*."""
    reply = backend.send_command("NewStereoTrack")
    if name:
        backend.send_command(f"SetTrackStatus: Name={name!r}")
    return reply


def new_label_track(backend: AudacityBackend, name: str) -> str:
    """Create a new label track named *name*."""
    reply = backend.send_command("NewLabelTrack")
    if name:
        backend.send_command(f"SetTrackStatus: Name={name!r}")
    return reply


def delete_track(backend: AudacityBackend, track_idx: int) -> str:
    """Delete the track at *track_idx* (0-based)."""
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command("RemoveTracks")


def move_track_up(backend: AudacityBackend, track_idx: int) -> str:
    """Move the track at *track_idx* one position upward in the stack."""
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command("TrackMoveUp")


def move_track_down(backend: AudacityBackend, track_idx: int) -> str:
    """Move the track at *track_idx* one position downward in the stack."""
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command("TrackMoveDown")


def mute_track(backend: AudacityBackend, track_idx: int) -> str:
    """Toggle mute on the track at *track_idx*."""
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command("MuteSelectedTracks")


def solo_track(backend: AudacityBackend, track_idx: int) -> str:
    """Toggle solo on the track at *track_idx*."""
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command("SoloSelectedTracks")


def set_gain(backend: AudacityBackend, track_idx: int, db_value: float) -> str:
    """Set the gain of the track at *track_idx* to *db_value* dB."""
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command(f"SetTrackAudio: Gain={db_value}")


def set_pan(backend: AudacityBackend, track_idx: int, pan_value: float) -> str:
    """Set the pan of the track at *track_idx*.

    *pan_value* must be in the range -1.0 (full left) to 1.0 (full right).
    """
    if not (-1.0 <= pan_value <= 1.0):
        raise ValueError(f"Pan value must be between -1.0 and 1.0, got {pan_value}")
    backend.send_command(f"SelectTracks: Track={track_idx} TrackCount=1 Mode=Set")
    return backend.send_command(f"SetTrackAudio: Pan={pan_value}")
