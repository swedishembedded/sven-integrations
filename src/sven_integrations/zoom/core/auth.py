"""Zoom OAuth 2.0 helpers — stdlib urllib only."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..backend import ZoomApiError

_AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
_TOKEN_URL = "https://zoom.us/oauth/token"
_REVOKE_URL = "https://zoom.us/oauth/revoke"
_TOKEN_INFO_URL = "https://zoom.us/oauth/data/tokeninfo"


# ---------------------------------------------------------------------------
# URL building


def build_oauth_url(
    client_id: str,
    redirect_uri: str,
    state: str = "",
) -> str:
    """Return the Zoom OAuth 2.0 authorisation URL.

    The user must visit this URL in a browser to grant access.
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    if state:
        params["state"] = state
    return f"{_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------------
# Token exchange


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange an authorisation code for access + refresh tokens.

    Returns the full token response from Zoom.
    """
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode()
    return _post_token(body, client_id, client_secret)


def refresh_token(
    client_id: str,
    client_secret: str,
    refresh_token_val: str,
) -> dict[str, Any]:
    """Exchange a refresh token for a new access token."""
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_val,
        }
    ).encode()
    return _post_token(body, client_id, client_secret)


def _post_token(
    body: bytes,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        _TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("reason", str(exc))
        except Exception:
            detail = str(exc)
        raise ZoomApiError(exc.code, detail) from exc
    except urllib.error.URLError as exc:
        raise ZoomApiError(0, f"Network error: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Token revocation


def revoke_token(token: str) -> None:
    """Revoke an access token so it can no longer be used."""
    body = urllib.parse.urlencode({"token": token}).encode()
    req = urllib.request.Request(
        _REVOKE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as exc:
        raise ZoomApiError(exc.code, str(exc)) from exc


# ---------------------------------------------------------------------------
# Token introspection


def get_token_info(token: str) -> dict[str, Any]:
    """Return metadata about an access token (scopes, expiry, etc.)."""
    params = urllib.parse.urlencode({"access_token": token})
    req = urllib.request.Request(
        f"{_TOKEN_INFO_URL}?{params}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("message", str(exc))
        except Exception:
            detail = str(exc)
        raise ZoomApiError(exc.code, detail) from exc
