"""Shotcut session — persists active project path and metadata."""

from __future__ import annotations

from ..shared import BaseSession


class ShotcutSession(BaseSession):
    """Session for the Shotcut harness.

    ``self.data`` keys
    ------------------
    mlt_path : str | None
        Path to the currently open .mlt file.
    profile : str
        Active render/export preset name.
    """

    harness: str = "shotcut"

    @property
    def mlt_path(self) -> str | None:
        return self.data.get("mlt_path")

    @mlt_path.setter
    def mlt_path(self, value: str | None) -> None:
        self.data["mlt_path"] = value

    @property
    def profile(self) -> str:
        return self.data.get("profile", "")

    @profile.setter
    def profile(self, value: str) -> None:
        self.data["profile"] = value
