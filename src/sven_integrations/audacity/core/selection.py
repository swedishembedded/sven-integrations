"""Selection operations sent via Audacity's mod-script-pipe."""

from __future__ import annotations

from ..backend import AudacityBackend


def select_all(backend: AudacityBackend) -> str:
    """Select all audio across all tracks."""
    return backend.send_command("SelectAll")


def select_none(backend: AudacityBackend) -> str:
    """Clear the current selection."""
    return backend.send_command("SelectNone")


def select_time(backend: AudacityBackend, start_s: float, end_s: float) -> str:
    """Select a time range from *start_s* to *end_s* seconds."""
    if end_s <= start_s:
        raise ValueError(f"end_s ({end_s}) must be greater than start_s ({start_s})")
    return backend.send_command(
        f"SelectTime: Start={start_s} End={end_s} RelativeTo=ProjectStart"
    )


def select_tracks(
    backend: AudacityBackend, first_idx: int, last_idx: int
) -> str:
    """Select tracks from index *first_idx* through *last_idx* (inclusive)."""
    count = last_idx - first_idx + 1
    return backend.send_command(
        f"SelectTracks: Track={first_idx} TrackCount={count} Mode=Set"
    )


def select_region(
    backend: AudacityBackend,
    start_s: float,
    end_s: float,
    first_track: int,
    last_track: int,
) -> str:
    """Select a rectangular region of time and tracks."""
    select_time(backend, start_s, end_s)
    return select_tracks(backend, first_track, last_track)


def trim_to_selection(backend: AudacityBackend) -> str:
    """Trim all audio outside the current selection."""
    return backend.send_command("Trim")


def split_at_selection(backend: AudacityBackend) -> str:
    """Split clips at the selection boundaries."""
    return backend.send_command("SplitCut")


def zoom_to_selection(backend: AudacityBackend) -> str:
    """Zoom the view to fit the current selection."""
    return backend.send_command("ZoomSel")
