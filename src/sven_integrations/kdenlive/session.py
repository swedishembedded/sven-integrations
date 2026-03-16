"""Kdenlive session — persists active project path and metadata."""

from __future__ import annotations

from ..shared import BaseSession


class KdenliveSession(BaseSession):
    """Session for the Kdenlive harness.

    ``self.data`` keys
    ------------------
    project_path : str | None
        Path to the currently open .kdenlive file.
    profile : str
        Active render profile name.
    """

    harness: str = "kdenlive"

    @property
    def project_path(self) -> str | None:
        return self.data.get("project_path")

    @project_path.setter
    def project_path(self, value: str | None) -> None:
        self.data["project_path"] = value

    @property
    def profile(self) -> str:
        return self.data.get("profile", "")

    @profile.setter
    def profile(self, value: str) -> None:
        self.data["profile"] = value
