"""Zoom session — persists OAuth tokens and meeting state."""

from __future__ import annotations

import time

from ..shared import BaseSession


class ZoomSession(BaseSession):
    """Session for the Zoom harness.

    ``self.data`` keys
    ------------------
    auth.oauth_token : str | None
        Current bearer token.
    auth.token_expiry : float | None
        Unix timestamp after which the token is considered expired.
    auth.refresh_token : str | None
        Token used to refresh the access token.
    """

    harness: str = "zoom"

    # ------------------------------------------------------------------
    # Token management

    @property
    def oauth_token(self) -> str | None:
        return self.data.get("auth", {}).get("oauth_token")

    @property
    def token_expiry(self) -> float | None:
        return self.data.get("auth", {}).get("token_expiry")

    def set_token(self, token: str, expires_in_seconds: float, refresh_token: str = "") -> None:
        """Store an OAuth access token and its expiry."""
        if "auth" not in self.data:
            self.data["auth"] = {}
        self.data["auth"]["oauth_token"] = token
        self.data["auth"]["token_expiry"] = time.time() + expires_in_seconds
        if refresh_token:
            self.data["auth"]["refresh_token"] = refresh_token
        self.save()

    def is_authenticated(self) -> bool:
        """Return True when a non-expired token is stored."""
        token = self.oauth_token
        expiry = self.token_expiry
        if not token:
            return False
        if expiry is not None and time.time() >= expiry:
            return False
        return True

    def clear_auth(self) -> None:
        """Remove all stored authentication data."""
        self.data.pop("auth", None)
        self.save()

    def get_refresh_token(self) -> str | None:
        return self.data.get("auth", {}).get("refresh_token")
