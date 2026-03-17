"""Zoom meeting CRUD operations."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..backend import ZoomApiBackend
from ..project import ZoomMeetingConfig

_DEFAULT_BACKEND = ZoomApiBackend()


def _api() -> ZoomApiBackend:
    return _DEFAULT_BACKEND


# ---------------------------------------------------------------------------
# Meeting CRUD


def create_meeting(
    token: str,
    user_id: str,
    config: ZoomMeetingConfig,
) -> dict[str, Any]:
    """Create a new Zoom meeting for *user_id* using the given config.

    Returns the full meeting object returned by the API.
    """
    errors = config.validate()
    if errors:
        raise ValueError(f"Invalid config: {'; '.join(errors)}")

    body: dict[str, Any] = {
        "topic": config.topic,
        "type": config.meeting_type,
        "duration": config.duration_minutes,
        "timezone": config.timezone,
        "settings": {
            "waiting_room": config.waiting_room,
            "auto_recording": "cloud" if config.recording_enabled else "none",
        },
    }
    if config.passcode:
        body["password"] = config.passcode
    if config.start_time:
        body["start_time"] = config.start_time
    if config.agenda:
        body["agenda"] = config.agenda

    return _api().request("POST", f"/users/{user_id}/meetings", body, token)


def get_meeting(token: str, meeting_id: str) -> dict[str, Any]:
    """Return meeting details for *meeting_id*."""
    return _api().request("GET", f"/meetings/{meeting_id}", None, token)


def update_meeting(
    token: str,
    meeting_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Patch the meeting with *updates* (partial update)."""
    _api().request("PATCH", f"/meetings/{meeting_id}", updates, token)
    return {"meeting_id": meeting_id, "updated": True}


def delete_meeting(token: str, meeting_id: str) -> None:
    """Delete a meeting permanently."""
    _api().request("DELETE", f"/meetings/{meeting_id}", None, token)


def list_meetings(
    token: str,
    user_id: str,
    meeting_type: str = "scheduled",  # scheduled | live | past | pastOne
    page_size: int = 30,
) -> list[dict[str, Any]]:
    """Return a page of meetings for *user_id*.

    meeting_type: "scheduled" | "live" | "upcoming" | "all"
    Handles pagination automatically and returns all meetings up to
    ``page_size`` results.
    """
    path = f"/users/{user_id}/meetings?type={meeting_type}&page_size={min(page_size, 300)}"
    result = _api().request("GET", path, None, token)
    return result.get("meetings", [])


# ---------------------------------------------------------------------------
# URL helpers


def start_meeting_url(meeting_id: str, passcode: str | None = None) -> str:
    """Return the host start URL for *meeting_id*."""
    url = f"https://zoom.us/s/{meeting_id}"
    if passcode:
        url += f"?pwd={urllib.parse.quote(passcode)}"
    return url


def join_meeting_url(meeting_id: str, passcode: str | None = None) -> str:
    """Return the participant join URL for *meeting_id*."""
    url = f"https://zoom.us/j/{meeting_id}"
    if passcode:
        url += f"?pwd={urllib.parse.quote(passcode)}"
    return url
