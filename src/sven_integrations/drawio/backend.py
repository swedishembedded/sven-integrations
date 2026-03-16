"""Draw.io CLI backend wrapper."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .drawio_xml import parse_diagram


class DrawioError(RuntimeError):
    """Raised when a draw.io CLI operation fails."""


SUPPORTED_FORMATS = {"png", "pdf", "svg", "jpg", "xml"}


class DrawioBackend:
    """Wraps the `drawio` desktop CLI for export and conversion operations."""

    def __init__(self, drawio_bin: str = "drawio") -> None:
        self._bin = drawio_bin

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = [self._bin, *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DrawioError(
                f"draw.io binary not found at {self._bin!r}. "
                "Install draw.io desktop and ensure it is on PATH."
            ) from exc
        if check and result.returncode != 0:
            raise DrawioError(
                f"draw.io exited {result.returncode}: {result.stderr.strip()}"
            )
        return result

    # ------------------------------------------------------------------
    # Public methods

    def export_diagram(
        self,
        input_path: str | Path,
        output_path: str | Path,
        fmt: str = "png",
        page_index: int = 0,
    ) -> Path:
        """Export a .drawio file to an image/document format.

        Uses ``drawio --export`` with the given format and page index.
        Returns the resolved output path.
        """
        fmt = fmt.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise DrawioError(
                f"Unsupported format {fmt!r}. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )
        out = Path(output_path)
        args = [
            "--export",
            "--format", fmt,
            "--output", str(out),
            "--page-index", str(page_index),
            str(input_path),
        ]
        self._run(args)
        if not out.exists():
            raise DrawioError(f"draw.io did not produce output file at {out}")
        return out

    def convert_xml(
        self,
        xml_str: str,
        output_path: str | Path,
        fmt: str = "png",
    ) -> Path:
        """Write XML to a temp file and export it to *output_path*."""
        with tempfile.NamedTemporaryFile(suffix=".drawio", mode="w", delete=False) as tmp:
            tmp.write(xml_str)
            tmp_path = Path(tmp.name)
        try:
            return self.export_diagram(tmp_path, output_path, fmt=fmt)
        finally:
            tmp_path.unlink(missing_ok=True)

    def validate_xml(self, xml_str: str) -> bool:
        """Return True if *xml_str* is parseable as drawio XML."""
        try:
            doc = parse_diagram(xml_str)
            return len(doc.pages) >= 0
        except (ValueError, Exception):
            return False

    def get_diagram_info(self, path: str | Path) -> dict[str, Any]:
        """Return metadata about a .drawio file (pages, cell counts)."""
        content = Path(path).read_text(encoding="utf-8")
        try:
            doc = parse_diagram(content)
        except ValueError as exc:
            raise DrawioError(f"Cannot parse {path}: {exc}") from exc
        return {
            "file": str(path),
            "pages": [
                {
                    "name": page.name,
                    "page_id": page.page_id,
                    "cell_count": len(page.cells),
                }
                for page in doc.pages
            ],
            "total_pages": len(doc.pages),
            "total_cells": sum(len(p.cells) for p in doc.pages),
        }
