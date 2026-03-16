"""GIMP subprocess bridge.

Executes Script-Fu expressions against GIMP running in headless batch mode.
GIMP is invoked as::

    gimp --no-interface --batch <script> --batch "(gimp-quit 0)"

All Script-Fu is built by the caller; this module is only responsible for
process management and error detection.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class GimpError(RuntimeError):
    """Raised when the GIMP process exits with a non-zero return code."""


class GimpBackend:
    """Thin wrapper around GIMP's ``--batch`` / Script-Fu interface.

    Parameters
    ----------
    executable:
        Path (or name on ``$PATH``) of the GIMP binary.
    timeout:
        Maximum seconds to wait for a GIMP process before raising
        :class:`subprocess.TimeoutExpired`.
    """

    def __init__(
        self,
        executable: str = "gimp",
        timeout: float = 120.0,
    ) -> None:
        self.executable = executable
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Core execution

    def run_script(self, script: str) -> str:
        """Execute a single Script-Fu expression and return combined stdout.

        The expression is wrapped with the standard ``(gimp-quit 0)`` epilogue
        so GIMP exits cleanly after evaluation.

        Raises
        ------
        GimpError
            If GIMP exits with a non-zero code.
        """
        cmd: list[str] = [
            self.executable,
            "--no-interface",
            "--batch",
            script,
            "--batch",
            "(gimp-quit 0)",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise GimpError(
                f"GIMP exited {result.returncode}: {detail}"
            )
        return result.stdout

    # ------------------------------------------------------------------
    # Higher-level operations

    def open_file(self, path: str) -> str:
        """Load an image file and return the Script-Fu output."""
        escaped = path.replace('"', '\\"')
        fname = Path(path).name.replace('"', '\\"')
        script = (
            f'(car (gimp-file-load RUN-NONINTERACTIVE "{escaped}" "{fname}"))'
        )
        return self.run_script(script)

    def export_file(self, path: str, fmt: str) -> str:
        """Export the topmost image to *path* in *fmt* format."""
        escaped = path.replace('"', '\\"')
        fname = Path(path).name.replace('"', '\\"')
        fmt_proc = fmt.lower().replace("jpg", "jpeg")
        script = (
            f'(let* ((image (car (gimp-image-list))) '
            f'(drawable (car (gimp-image-get-active-drawable image)))) '
            f'(file-{fmt_proc}-save RUN-NONINTERACTIVE image drawable '
            f'"{escaped}" "{fname}"))'
        )
        return self.run_script(script)

    def get_image_info(self) -> dict[str, Any]:
        """Query basic properties of the most-recently-loaded image."""
        script = (
            "(let* ((image (car (gimp-image-list)))) "
            "(list (car (gimp-image-width image)) "
            "(car (gimp-image-height image)) "
            "(car (gimp-image-get-resolution image))))"
        )
        raw = self.run_script(script)
        return {"raw_output": raw.strip()}
