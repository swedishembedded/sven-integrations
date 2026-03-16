"""Zoom REST API v2 backend — stdlib urllib only, rate-limit aware."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_BASE_URL = "https://api.zoom.us/v2"


class ZoomApiError(RuntimeError):
    """Raised when the Zoom API returns an error response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Zoom API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class ZoomApiBackend:
    """Thin wrapper around the Zoom REST API v2.

    All network calls use stdlib ``urllib`` so there are no extra
    runtime dependencies.
    """

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Core request helper

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        token: str,
        *,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Make an authenticated JSON request to the Zoom API.

        Handles 429 / Retry-After automatically (up to *max_retries* times).
        """
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        data: bytes | None = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        for attempt in range(max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    if not raw:
                        return {}
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < max_retries:
                    retry_after = float(exc.headers.get("Retry-After", "1"))
                    time.sleep(retry_after)
                    continue
                try:
                    detail = json.loads(exc.read()).get("message", str(exc))
                except Exception:
                    detail = str(exc)
                raise ZoomApiError(exc.code, detail) from exc
            except urllib.error.URLError as exc:
                raise ZoomApiError(0, f"Network error: {exc.reason}") from exc

        raise ZoomApiError(429, "Rate limit exceeded after retries")

    # ------------------------------------------------------------------
    # User info

    def get_user_info(self, token: str, user_id: str = "me") -> dict[str, Any]:
        """Return profile information for *user_id* (default: the token owner)."""
        return self.request("GET", f"/users/{user_id}", None, token)
