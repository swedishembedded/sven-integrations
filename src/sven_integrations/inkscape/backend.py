"""Inkscape subprocess bridge.

Drives Inkscape via its ``--actions`` CLI interface (Inkscape ≥ 1.0)::

    inkscape <svg_file> --actions="<action1>;action2;..."

Each action string follows Inkscape's action syntax.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class InkscapeError(RuntimeError):
    """Raised when the Inkscape process exits with a non-zero return code."""


class InkscapeBackend:
    """Thin wrapper around Inkscape's ``--actions`` interface.

    Parameters
    ----------
    executable:
        Path (or name on ``$PATH``) of the Inkscape binary.
    timeout:
        Maximum seconds to wait before raising
        :class:`subprocess.TimeoutExpired`.
    """

    def __init__(
        self,
        executable: str = "inkscape",
        timeout: float = 120.0,
    ) -> None:
        self.executable = executable
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Core execution

    def run_actions(self, svg_path: str, actions: list[str]) -> str:
        """Execute a sequence of Inkscape actions and return stdout.

        Parameters
        ----------
        svg_path:
            The SVG file to operate on.
        actions:
            List of action strings, e.g.
            ``["select-by-id:rect1", "transform-translate:10,20"]``.

        Raises
        ------
        InkscapeError
            If Inkscape exits with a non-zero code.
        """
        actions_str = ";".join(actions)
        cmd: list[str] = [
            self.executable,
            svg_path,
            f"--actions={actions_str}",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise InkscapeError(
                f"Inkscape exited {result.returncode}: {detail}"
            )
        return result.stdout

    # ------------------------------------------------------------------
    # Higher-level operations

    def open_document(self, path: str) -> str:
        """Open a document and return the file-open action output."""
        actions = [f"file-open:{path}", "query-all"]
        return self.run_actions(path, actions)

    def export_document(
        self,
        in_path: str,
        out_path: str,
        fmt: str,
    ) -> str:
        """Export *in_path* to *out_path* in *fmt* format.

        Supported formats: ``png``, ``pdf``, ``eps``, ``emf``, ``svg``.
        """
        actions = [
            f"file-open:{in_path}",
            f"export-type:{fmt.lower()}",
            f"export-filename:{out_path}",
            "export-do",
        ]
        return self.run_actions(in_path, actions)

    def get_document_info(self, path: str) -> dict[str, Any]:
        """Return basic metadata about an SVG document.

        Queries width, height, and the list of element IDs.
        """
        actions = [
            f"file-open:{path}",
            "query-all",
        ]
        raw = self.run_actions(path, actions)
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return {
            "path": path,
            "name": Path(path).name,
            "elements": lines,
        }
