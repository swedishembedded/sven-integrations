"""ComfyUI session management."""

from __future__ import annotations

import uuid

from ..shared import BaseSession


class ComfySession(BaseSession):
    """Persistent session for the ComfyUI harness.

    ``self.data["project"]`` holds the serialised ComfyProject.
    ``self.data["client_id"]`` holds a stable UUID4 for WebSocket identification.
    """

    harness: str = "comfyui"

    def ensure_client_id(self) -> str:
        """Return existing client_id or generate and persist a new one."""
        if "client_id" not in self.data:
            self.data["client_id"] = str(uuid.uuid4())
        return self.data["client_id"]
