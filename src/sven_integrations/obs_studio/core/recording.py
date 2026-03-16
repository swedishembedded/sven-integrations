"""Recording and streaming control via OBS WebSocket."""

from __future__ import annotations

from ..backend import ObsBackend


def start_recording(backend: ObsBackend) -> None:
    """Start recording."""
    backend.call("StartRecord")


def stop_recording(backend: ObsBackend) -> dict[str, object]:
    """Stop recording and return status info including the output file path."""
    return backend.call("StopRecord")


def toggle_recording(backend: ObsBackend) -> None:
    """Toggle recording on or off."""
    backend.call("ToggleRecord")


def start_streaming(backend: ObsBackend) -> None:
    """Start the stream output."""
    backend.call("StartStream")


def stop_streaming(backend: ObsBackend) -> dict[str, object]:
    """Stop the stream output and return status info."""
    return backend.call("StopStream")


def get_recording_status(backend: ObsBackend) -> dict[str, object]:
    """Return the current recording status."""
    return backend.call("GetRecordStatus")


def get_streaming_status(backend: ObsBackend) -> dict[str, object]:
    """Return the current streaming status."""
    return backend.call("GetStreamStatus")


def set_recording_path(backend: ObsBackend, path: str) -> None:
    """Set the directory where recordings are saved."""
    backend.call("SetRecordDirectory", {"recordDirectory": path})


def get_output_settings(backend: ObsBackend) -> dict[str, object]:
    """Return the current output (recording/streaming) configuration."""
    return backend.call("GetOutputList")
