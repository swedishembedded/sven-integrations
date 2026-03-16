"""Persistent session for the Inkscape harness.

Wraps :class:`~sven_integrations.shared.BaseSession` with typed access to
the :class:`~sven_integrations.inkscape.project.InkscapeProject` stored in
``self.data``.
"""

from __future__ import annotations

from typing import Any

from ..shared import BaseSession
from .project import InkscapeProject


class InkscapeSession(BaseSession):
    """Named workspace that persists an :class:`InkscapeProject` to disk."""

    harness: str = "inkscape"

    # ------------------------------------------------------------------
    # Project property

    @property
    def project(self) -> InkscapeProject | None:
        """Deserialise the project from the session data store."""
        raw: dict[str, Any] | None = self.data.get("project")
        if raw is None:
            return None
        return InkscapeProject.from_dict(raw)

    @project.setter
    def project(self, value: InkscapeProject | None) -> None:
        """Serialise *value* into the session data store."""
        if value is None:
            self.data.pop("project", None)
        else:
            self.data["project"] = value.to_dict()

    # ------------------------------------------------------------------
    # Lifecycle helpers

    def open_document(
        self,
        svg_path: str,
        width_mm: float = 210.0,
        height_mm: float = 297.0,
    ) -> InkscapeProject:
        """Record a document path and create a minimal project."""
        proj = InkscapeProject(
            svg_path=svg_path,
            width_mm=width_mm,
            height_mm=height_mm,
        )
        self.project = proj
        self.save()
        return proj

    def close(self) -> None:
        """Clear the current project and persist the cleared state."""
        self.project = None
        self.save()
