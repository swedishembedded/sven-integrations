"""Audacity session — persistent state for the audacity harness."""

from __future__ import annotations

from typing import Any

from ..shared import BaseSession
from .project import AudioProject


class AudacitySession(BaseSession):
    """Named persistent session for an Audacity workspace.

    ``data`` stores the serialised ``AudioProject`` under the ``"project"`` key.
    """

    harness: str = "audacity"

    def get_project(self) -> AudioProject | None:
        raw = self.data.get("project")
        if raw is None:
            return None
        return AudioProject.from_dict(raw)

    def set_project(self, project: AudioProject) -> None:
        self.data["project"] = project.to_dict()

    def has_project(self) -> bool:
        return "project" in self.data

    def status(self) -> dict[str, Any]:
        proj = self.get_project()
        return {
            "session": self.name,
            "harness": self.harness,
            "has_project": proj is not None,
            "project_name": proj.name if proj else None,
            "track_count": proj.total_tracks() if proj else 0,
        }
