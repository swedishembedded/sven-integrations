"""Audacity IPC backend — communicates via mod-script-pipe named pipes."""

from __future__ import annotations

import os
import time


class AudacityConnectionError(RuntimeError):
    """Raised when the Audacity mod-script-pipe is unavailable."""


class AudacityBackend:
    """Bridge to a running Audacity instance via its mod-script-pipe interface.

    Audacity's mod-script-pipe plugin exposes two named pipes:
    - ``/tmp/audacity_script_pipe.to.<uid>``   — commands written here
    - ``/tmp/audacity_script_pipe.from.<uid>``  — responses read from here

    The response protocol ends each reply with ``"\\n\\n"`` (blank line).
    """

    _EOL = "\\n"
    _END_OF_REPLY = ""

    def __init__(self) -> None:
        self._uid = os.getuid()
        self._to_path = f"/tmp/audacity_script_pipe.to.{self._uid}"
        self._from_path = f"/tmp/audacity_script_pipe.from.{self._uid}"
        self._to_pipe: "IO[str] | None" = None
        self._from_pipe: "IO[str] | None" = None

    # ------------------------------------------------------------------
    # Connection lifecycle

    def connect(self) -> None:
        """Open both named pipes.  Raises AudacityConnectionError on failure."""
        if not os.path.exists(self._to_path):
            raise AudacityConnectionError(
                f"Audacity pipe not found: {self._to_path}\n"
                "Ensure Audacity is running with mod-script-pipe enabled."
            )
        if not os.path.exists(self._from_path):
            raise AudacityConnectionError(
                f"Audacity pipe not found: {self._from_path}"
            )
        self._to_pipe = open(self._to_path, "w")  # noqa: WPS515
        self._from_pipe = open(self._from_path, "r")  # noqa: WPS515

    def disconnect(self) -> None:
        """Close both pipes gracefully."""
        if self._to_pipe is not None:
            try:
                self._to_pipe.close()
            except OSError:
                pass
            self._to_pipe = None
        if self._from_pipe is not None:
            try:
                self._from_pipe.close()
            except OSError:
                pass
            self._from_pipe = None

    def is_connected(self) -> bool:
        return self._to_pipe is not None and self._from_pipe is not None

    # ------------------------------------------------------------------
    # Command dispatch

    def send_command(self, cmd: str) -> str:
        """Send *cmd* to Audacity and return the full reply as a string.

        Blocks until the blank-line sentinel is received.
        """
        if not self.is_connected():
            raise AudacityConnectionError("Not connected — call connect() first.")
        assert self._to_pipe is not None
        assert self._from_pipe is not None

        self._to_pipe.write(cmd + self._EOL)
        self._to_pipe.flush()

        lines: list[str] = []
        while True:
            line = self._from_pipe.readline()
            if line.rstrip("\r\n") == self._END_OF_REPLY and lines:
                break
            lines.append(line.rstrip("\r\n"))

        return "\n".join(lines)

    def ping(self) -> bool:
        """Return True when Audacity responds to a no-op GetInfo call."""
        try:
            reply = self.send_command("GetInfo: Type=Commands")
            return bool(reply)
        except (AudacityConnectionError, OSError):
            return False

    # ------------------------------------------------------------------
    # Context manager

    def __enter__(self) -> "AudacityBackend":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
