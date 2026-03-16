"""AnyGen session management."""

from __future__ import annotations

from ..shared import BaseSession


class AnygenSession(BaseSession):
    """Persistent session for the AnyGen harness.

    ``self.data["project"]`` holds the serialised AnygenProject.
    ``self.data["auth"]`` holds provider API keys as ``{provider: key}``.
    """

    harness: str = "anygen"

    def get_api_key(self, provider: str) -> str | None:
        auth: dict[str, str] = self.data.get("auth", {})
        return auth.get(provider)

    def set_api_key(self, provider: str, key: str) -> None:
        if "auth" not in self.data:
            self.data["auth"] = {}
        self.data["auth"][provider] = key

    def clear_keys(self) -> None:
        self.data["auth"] = {}
