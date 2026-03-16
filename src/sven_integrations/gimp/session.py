"""Persistent session for the GIMP harness.

Wraps :class:`~sven_integrations.shared.BaseSession` with typed access to
the :class:`~sven_integrations.gimp.project.GimpProject` payload stored in
``self.data``.
"""

from __future__ import annotations

from typing import Any

from ..shared import BaseSession
from .project import GimpProject


class GimpSession(BaseSession):
    """Named workspace that persists a :class:`GimpProject` to disk."""

    harness: str = "gimp"

    # ------------------------------------------------------------------
    # Project property

    @property
    def project(self) -> GimpProject | None:
        """Deserialise the project from the session data store."""
        raw: dict[str, Any] | None = self.data.get("project")
        if raw is None:
            return None
        return GimpProject.from_dict(raw)

    @project.setter
    def project(self, value: GimpProject | None) -> None:
        """Serialise *value* into the session data store."""
        if value is None:
            self.data.pop("project", None)
        else:
            self.data["project"] = value.to_dict()

    # ------------------------------------------------------------------
    # Lifecycle helpers

    def new_project(
        self,
        width: int,
        height: int,
        color_mode: str = "RGB",
        dpi: float = 72.0,
    ) -> GimpProject:
        """Create a blank project and persist the session."""
        proj = GimpProject(
            width=width,
            height=height,
            color_mode=color_mode,
            dpi=dpi,
        )
        self.project = proj
        self.save()
        return proj

    def close(self) -> None:
        """Clear the current project and persist the cleared state."""
        self.project = None
        self.save()
