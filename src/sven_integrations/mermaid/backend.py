"""Mermaid rendering backend: mmdc CLI or mermaid.ink REST API."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Literal


class MermaidError(RuntimeError):
    """Raised when a Mermaid rendering operation fails."""


RendererName = Literal["mmdc", "api"]

MERMAID_INK_BASE = "https://mermaid.ink"


class MermaidBackend:
    """Wraps mmdc CLI and the mermaid.ink REST API for rendering diagrams."""

    def __init__(self, mmdc_bin: str = "mmdc") -> None:
        self._mmdc = mmdc_bin

    def is_mmdc_available(self) -> bool:
        """Return True if the mmdc binary can be found on PATH."""
        return shutil.which(self._mmdc) is not None

    def choose_renderer(self) -> RendererName:
        """Return the preferred renderer name based on availability."""
        return "mmdc" if self.is_mmdc_available() else "api"

    def render_with_mmdc(
        self,
        diagram_src: str,
        output_path: str | Path,
        fmt: str = "png",
        theme: str = "default",
        bg_color: str = "white",
    ) -> Path:
        """Render diagram source using the mmdc CLI.

        Writes *diagram_src* to a temp file, runs mmdc, and returns the
        resolved output path.
        """
        if not self.is_mmdc_available():
            raise MermaidError(
                f"mmdc not found at {self._mmdc!r}. "
                "Install @mermaid-js/mermaid-cli: npm install -g @mermaid-js/mermaid-cli"
            )
        out = Path(output_path)
        with tempfile.NamedTemporaryFile(
            suffix=".mmd", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(diagram_src)
            tmp_path = Path(tmp.name)
        try:
            cmd = [
                self._mmdc,
                "--input", str(tmp_path),
                "--output", str(out),
                "--theme", theme,
                "--backgroundColor", bg_color,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise MermaidError(
                    f"mmdc exited {result.returncode}: {result.stderr.strip()}"
                )
        finally:
            tmp_path.unlink(missing_ok=True)
        if not out.exists():
            raise MermaidError(f"mmdc did not produce output at {out}")
        return out

    def render_with_api(
        self,
        diagram_src: str,
        fmt: str = "png",
        theme: str = "default",
    ) -> bytes:
        """Render via the mermaid.ink public REST API.

        Returns the raw image/document bytes.
        """
        encoded = base64.urlsafe_b64encode(diagram_src.encode("utf-8")).decode("ascii")
        endpoint_map = {
            "png": f"{MERMAID_INK_BASE}/img/{encoded}?theme={theme}",
            "svg": f"{MERMAID_INK_BASE}/svg/{encoded}?theme={theme}",
            "pdf": f"{MERMAID_INK_BASE}/pdf/{encoded}?theme={theme}",
        }
        url = endpoint_map.get(fmt.lower())
        if url is None:
            raise MermaidError(f"Unsupported API format {fmt!r}. Use png, svg, or pdf.")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sven-integrations/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raise MermaidError(f"mermaid.ink API error {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise MermaidError(f"mermaid.ink request failed: {exc.reason}") from exc
