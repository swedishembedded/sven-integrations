"""Zoom meeting participant and registrant management via Zoom REST API v2."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

_BASE_URL = "https://api.zoom.us/v2"


# ---------------------------------------------------------------------------
# Dataclass


@dataclass
class RegistrantInfo:
    """Summary of a meeting registrant."""

    email: str
    first_name: str
    last_name: str
    status: str = "pending"   # pending | approved | denied

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RegistrantInfo":
        return cls(
            email=str(d.get("email", "")),
            first_name=str(d.get("first_name", "")),
            last_name=str(d.get("last_name", "")),
            status=str(d.get("status", "pending")),
        )


# ---------------------------------------------------------------------------
# Internal HTTP helpers


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _do_request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers=_auth_headers(token),
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            err_data = json.loads(body_bytes)
        except Exception:
            err_data = {"message": body_bytes.decode("utf-8", errors="replace")}
        raise RuntimeError(
            f"Zoom API {exc.code}: {err_data.get('message', str(exc))}"
        ) from exc


def _paginate(
    token: str,
    path: str,
    page_size: int,
    extra_params: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all pages from a paginated Zoom list endpoint."""
    items: list[dict[str, Any]] = []
    next_token: str | None = None
    params: dict[str, str] = {"page_size": str(page_size)}
    if extra_params:
        params.update(extra_params)

    while True:
        if next_token:
            params["next_page_token"] = next_token
        qs = urllib.parse.urlencode(params)
        url = f"{_BASE_URL}{path}?{qs}"
        data = _do_request("GET", url, token)
        # Different endpoints use different list keys
        for key in ("registrants", "participants", "meetings"):
            if key in data:
                items.extend(data[key])
                break
        next_token = data.get("next_page_token") or ""
        if not next_token:
            break

    return items


# ---------------------------------------------------------------------------
# Public API


def add_registrant(
    token: str,
    meeting_id: str,
    email: str,
    first_name: str,
    last_name: str,
) -> dict[str, Any]:
    """Register a single attendee for *meeting_id*.

    Returns the Zoom API response (includes registrant_id and join_url).
    """
    url = f"{_BASE_URL}/meetings/{meeting_id}/registrants"
    return _do_request(
        "POST",
        url,
        token,
        body={"email": email, "first_name": first_name, "last_name": last_name},
    )


def add_batch_registrants(
    token: str,
    meeting_id: str,
    registrants: list[dict[str, Any]],
) -> dict[str, Any]:
    """Register multiple attendees in a single API call.

    Each entry in *registrants* must contain ``email``, ``first_name``, and
    ``last_name``.  Returns a list of ``{registrant_id, join_url}`` entries.
    """
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for reg in registrants:
        try:
            resp = add_registrant(
                token,
                meeting_id,
                email=str(reg.get("email", "")),
                first_name=str(reg.get("first_name", "")),
                last_name=str(reg.get("last_name", "")),
            )
            results.append(resp)
        except RuntimeError as exc:
            errors.append({"email": reg.get("email"), "error": str(exc)})
    return {"added": results, "errors": errors, "total": len(registrants)}


def list_registrants(
    token: str,
    meeting_id: str,
    status: str = "approved",
    page_size: int = 30,
) -> list[dict[str, Any]]:
    """Return all registrants for *meeting_id* with the given *status*."""
    path = f"/meetings/{meeting_id}/registrants"
    return _paginate(token, path, page_size, {"status": status})


def remove_registrant(
    token: str,
    meeting_id: str,
    registrant_id: str,
) -> dict[str, Any]:
    """Cancel/remove a registrant from a meeting."""
    url = f"{_BASE_URL}/meetings/{meeting_id}/registrants"
    body = {"registrants": [{"id": registrant_id}], "action": "cancel"}
    return _do_request("PUT", url, token, body=body)


def list_past_participants(
    token: str,
    meeting_uuid: str,
    page_size: int = 30,
) -> list[dict[str, Any]]:
    """Return participants who attended a past meeting identified by *meeting_uuid*."""
    # Zoom requires double URL-encoding for meeting UUIDs containing slashes
    encoded = urllib.parse.quote(urllib.parse.quote(meeting_uuid, safe=""), safe="")
    path = f"/past_meetings/{encoded}/participants"
    return _paginate(token, path, page_size)
