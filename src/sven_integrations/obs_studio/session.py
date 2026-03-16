"""OBS Studio session — persistent state for the obs_studio harness."""

from __future__ import annotations

from typing import Any

from ..shared import BaseSession
from .project import ObsSetup


class ObsSession(BaseSession):
    """Named persistent session for an OBS Studio workspace.

    ``data`` stores the serialised ``ObsSetup`` under the ``"setup"`` key,
    plus connection parameters under ``"connection"``.
    """

    harness: str = "obs_studio"

    def get_setup(self) -> ObsSetup | None:
        raw = self.data.get("setup")
        if raw is None:
            return None
        return ObsSetup.from_dict(raw)

    def set_setup(self, setup: ObsSetup) -> None:
        self.data["setup"] = setup.to_dict()

    def has_setup(self) -> bool:
        return "setup" in self.data

    def set_connection(self, host: str, port: int, password: str) -> None:
        self.data["connection"] = {"host": host, "port": port, "password": password}

    def get_connection(self) -> dict[str, Any]:
        return self.data.get("connection", {"host": "localhost", "port": 4455, "password": ""})

    def status(self) -> dict[str, Any]:
        setup = self.get_setup()
        conn = self.get_connection()
        return {
            "session": self.name,
            "harness": self.harness,
            "has_setup": setup is not None,
            "profile": setup.profile_name if setup else None,
            "scene_count": len(setup.scenes) if setup else 0,
            "websocket_host": conn.get("host"),
            "websocket_port": conn.get("port"),
        }
