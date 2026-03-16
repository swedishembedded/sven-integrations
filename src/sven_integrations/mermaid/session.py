"""Mermaid session management."""

from __future__ import annotations

from ..shared import BaseSession


class MermaidSession(BaseSession):
    """Persistent session for the Mermaid harness."""

    harness: str = "mermaid"
