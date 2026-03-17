"""Kdenlive backend — DBus bridge with XML fallback.

Tries to connect to a running Kdenlive instance over DBus.  When DBus is
unavailable (headless CI, remote machines) all operations fall back to
direct XML manipulation of ``.kdenlive`` project files.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class KdenliveError(RuntimeError):
    """Raised when a Kdenlive backend operation fails."""


class KdenliveBackend:
    """High-level wrapper around the Kdenlive DBus interface.

    Falls back to XML manipulation when DBus is not available.
    """

    _DBUS_SERVICE = "org.kde.kdenlive"
    _DBUS_PATH = "/kdenlive"
    _DBUS_IFACE = "org.kde.kdenlive"

    def __init__(self) -> None:
        self._dbus_available: bool = False
        self._iface: Any = None  # dbus.Interface when connected

    # ------------------------------------------------------------------
    # DBus connection

    def connect_dbus(self) -> bool:
        """Attempt to connect to a running Kdenlive over DBus.

        Returns True when a live connection is established.  Returns False
        (without raising) when DBus or Kdenlive is unavailable — the backend
        will fall back to XML-based operations for supported commands.
        """
        try:
            import dbus  # type: ignore[import]

            bus = dbus.SessionBus()
            obj = bus.get_object(self._DBUS_SERVICE, self._DBUS_PATH)
            self._iface = dbus.Interface(obj, self._DBUS_IFACE)
            self._dbus_available = True
            return True
        except ImportError:
            # python-dbus not installed — silently fall back to XML mode
            self._dbus_available = False
            return False
        except Exception as exc:
            # Kdenlive not running or DBus session unavailable
            import warnings
            warnings.warn(
                f"Kdenlive DBus connection failed ({exc}); "
                "falling back to XML-only mode. "
                "Start Kdenlive first for live editing features.",
                stacklevel=2,
            )
            self._dbus_available = False
            return False

    # ------------------------------------------------------------------
    # Generic action dispatch

    def run_action(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke a named action through DBus or raise KdenliveError."""
        if not self._dbus_available:
            raise KdenliveError(
                f"DBus not connected; cannot run action '{action_name}'. "
                "Use XML-based operations instead."
            )
        try:
            result = self._iface.runAction(action_name, str(params))  # type: ignore[union-attr]
            return {"action": action_name, "result": str(result)}
        except Exception as exc:
            raise KdenliveError(f"DBus action '{action_name}' failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Project operations

    def open_project(self, path: str) -> None:
        """Open a project file in a running Kdenlive or validate it offline."""
        p = Path(path)
        if not p.exists():
            raise KdenliveError(f"Project file not found: {path}")
        if not path.endswith(".kdenlive") and not path.endswith(".mlt"):
            raise KdenliveError(f"Unsupported project format: {path}")

        if self._dbus_available:
            self.run_action("open_project", {"path": path})
        else:
            # Validate that the file is well-formed XML
            try:
                ET.parse(path)
            except ET.ParseError as exc:
                raise KdenliveError(f"Malformed project file {path}: {exc}") from exc

    def save_project(self, path: str) -> None:
        """Save the currently open project to *path*."""
        if self._dbus_available:
            self.run_action("save_project", {"path": path})
        else:
            raise KdenliveError(
                "DBus not connected. Use KdenliveProject.to_dict() + XML writer to save."
            )

    def render_project(self, output_path: str, profile: str) -> str:
        """Trigger a render via DBus or via melt CLI.

        Returns the output path on success.
        """
        if self._dbus_available:
            self.run_action("render", {"output": output_path, "profile": profile})
            return output_path

        return self._render_via_melt(output_path, profile)

    def _render_via_melt(self, output_path: str, profile: str) -> str:
        melt_bin = self._find_melt()
        cmd = [melt_bin, "-profile", profile, "-consumer", f"avformat:{output_path}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode != 0:
                raise KdenliveError(f"melt render failed: {result.stderr.strip()}")
        except FileNotFoundError as exc:
            raise KdenliveError(
                "melt binary not found. Install the MLT framework: "
                "apt-get install melt  (Debian/Ubuntu) or  brew install mlt  (macOS)"
            ) from exc
        return output_path

    def get_project_info(self) -> dict[str, Any]:
        """Return metadata about the currently open project."""
        if self._dbus_available:
            return self.run_action("project_info", {})
        return {"dbus": False, "info": "Use KdenliveProject.to_dict() for offline info"}

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _find_melt() -> str:
        import shutil

        for candidate in ("melt", "melt-7", "mlt-melt"):
            if shutil.which(candidate):
                return candidate
        raise KdenliveError("melt binary not found; install the MLT framework")
