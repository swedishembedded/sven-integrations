"""Zoom recording management."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..backend import ZoomApiBackend, ZoomApiError

_DEFAULT_BACKEND = ZoomApiBackend()


def _api() -> ZoomApiBackend:
    return _DEFAULT_BACKEND


# ---------------------------------------------------------------------------
# Recording management


def list_recordings(
    token: str,
    user_id: str,
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:
    """Return all cloud recordings for *user_id* within [from_date, to_date].

    Dates are in ISO-8601 format (``YYYY-MM-DD``).
    """
    path = f"/users/{user_id}/recordings?from={from_date}&to={to_date}&page_size=300"
    result = _api().request("GET", path, None, token)
    return result.get("meetings", [])


def get_recording_info(token: str, meeting_id: str) -> dict[str, Any]:
    """Return recording details for a given meeting."""
    return _api().request("GET", f"/meetings/{meeting_id}/recordings", None, token)


def delete_recording(token: str, meeting_id: str, recording_id: str) -> None:
    """Delete a specific recording file."""
    _api().request(
        "DELETE",
        f"/meetings/{meeting_id}/recordings/{recording_id}",
        None,
        token,
    )


def download_recording(
    token: str,
    download_url: str,
    output_path: str,
) -> Path:
    """Download a recording file to *output_path*.

    The Zoom download URL typically requires a JWT / OAuth bearer token
    appended as ``?access_token=…`` or as an Authorization header.

    Returns the resolved Path of the downloaded file.
    """
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Zoom requires the access_token as a query param for direct file downloads
    sep = "&" if "?" in download_url else "?"
    url_with_token = f"{download_url}{sep}access_token={token}"

    req = urllib.request.Request(url_with_token)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise ZoomApiError(exc.code, f"Download failed: {exc.reason}") from exc
    return dest


def get_transcript(token: str, meeting_id: str) -> str | None:
    """Return the VTT transcript text for *meeting_id*, or None if unavailable."""
    try:
        data = get_recording_info(token, meeting_id)
    except ZoomApiError:
        return None

    for rec in data.get("recording_files", []):
        if rec.get("file_type", "").upper() == "TRANSCRIPT":
            vtt_url = rec.get("download_url", "")
            if not vtt_url:
                continue
            try:
                sep = "&" if "?" in vtt_url else "?"
                url_with_token = f"{vtt_url}{sep}access_token={token}"
                req = urllib.request.Request(url_with_token)
                req.add_header("Authorization", f"Bearer {token}")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, urllib.error.HTTPError):
                continue

    return None
