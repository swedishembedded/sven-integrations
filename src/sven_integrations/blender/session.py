"""Persistent session for the Blender harness.

Wraps :class:`~sven_integrations.shared.BaseSession` with typed access to
the :class:`~sven_integrations.blender.project.BlenderProject` stored in
``self.data``.
"""

from __future__ import annotations

from typing import Any

from ..shared import BaseSession
from .project import BlenderProject


class BlenderSession(BaseSession):
    """Named workspace that persists a :class:`BlenderProject` to disk."""

    harness: str = "blender"

    # ------------------------------------------------------------------
    # Project property

    @property
    def project(self) -> BlenderProject | None:
        """Deserialise the project from the session data store."""
        raw: dict[str, Any] | None = self.data.get("project")
        if raw is None:
            return None
        return BlenderProject.from_dict(raw)

    @project.setter
    def project(self, value: BlenderProject | None) -> None:
        """Serialise *value* into the session data store."""
        if value is None:
            self.data.pop("project", None)
        else:
            self.data["project"] = value.to_dict()

    # ------------------------------------------------------------------
    # Lifecycle helpers

    def new_scene(
        self,
        scene_name: str = "Scene",
        frame_start: int = 1,
        frame_end: int = 250,
        fps: int = 24,
    ) -> BlenderProject:
        """Create a fresh scene project and persist the session."""
        proj = BlenderProject(
            scene_name=scene_name,
            frame_start=frame_start,
            frame_end=frame_end,
            fps=fps,
        )
        self.project = proj
        self.save()
        return proj

    def set_blend_file(self, path: str) -> None:
        """Record the path to the .blend file and persist."""
        proj = self.project or BlenderProject()
        proj.blend_file = path
        self.project = proj
        self.save()

    def close(self) -> None:
        """Clear the current project and persist the cleared state."""
        self.project = None
        self.save()
