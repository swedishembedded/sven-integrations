"""Draw.io session management."""

from __future__ import annotations

from ..shared import BaseSession


class DrawioSession(BaseSession):
    """Persistent session for the draw.io harness."""

    harness: str = "drawio"
