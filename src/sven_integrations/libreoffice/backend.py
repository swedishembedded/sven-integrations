"""LibreOffice headless backend — wraps the libreoffice CLI for file conversion."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class LibreOfficeError(RuntimeError):
    """Raised when a LibreOffice subprocess call fails."""


def _find_binary() -> str:
    """Return the path to the libreoffice (or soffice) binary."""
    for candidate in ("libreoffice", "soffice"):
        found = shutil.which(candidate)
        if found:
            return found
    raise LibreOfficeError(
        "LibreOffice binary not found. Install LibreOffice and ensure it is on PATH."
    )


class LibreOfficeBackend:
    """Controls LibreOffice via its ``--headless`` command-line interface.

    All operations spawn a short-lived subprocess.  Each instance can optionally
    cache the resolved binary path to avoid repeated PATH searches.
    """

    DEFAULT_TIMEOUT = 120

    def __init__(self, binary: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._binary = binary or _find_binary()
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API

    def convert(
        self,
        input_path: str,
        output_format: str,
        output_dir: str | None = None,
    ) -> Path:
        """Convert *input_path* to *output_format* using LibreOffice headless.

        Returns the path of the generated output file.
        """
        src = Path(input_path)
        if not src.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        dest_dir = Path(output_dir) if output_dir else src.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._binary,
            "--headless",
            "--convert-to", output_format,
            "--outdir", str(dest_dir),
            str(src),
        ]
        self._run(cmd)

        output_path = dest_dir / src.with_suffix(f".{output_format}").name
        if not output_path.exists():
            output_path = dest_dir / f"{src.stem}.{output_format}"
        return output_path

    def run_macro(self, macro_name: str, args: list[str]) -> str:
        """Execute a LibreOffice Basic macro by name.

        *macro_name* should follow the form ``Library.Module.MacroName``.
        Returns captured stdout.
        """
        arg_str = " ".join(args)
        cmd = [
            self._binary,
            "--headless",
            f"macro:///{macro_name}({arg_str})",
        ]
        return self._run(cmd)

    def open_and_export(
        self,
        template_path: str,
        data: dict[str, str],
        output_path: str,
        fmt: str,
    ) -> Path:
        """Open *template_path*, populate it with *data*, and export to *output_path*.

        This is a convenience wrapper that converts the template to the target
        format and then copies it to *output_path*.  Full data injection requires
        a macro or Python-UNO bridge; this backend handles the conversion step.
        """
        src = Path(template_path)
        out = Path(output_path)
        converted = self.convert(str(src), fmt, str(out.parent))
        if converted != out:
            converted.rename(out)
        return out

    # ------------------------------------------------------------------
    # Internals

    def _run(self, cmd: list[str]) -> str:
        """Run *cmd* and return combined stdout+stderr as a string."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise LibreOfficeError(
                f"LibreOffice timed out after {self._timeout}s: {' '.join(cmd)}"
            ) from exc
        except FileNotFoundError as exc:
            raise LibreOfficeError(f"Binary not found: {self._binary}") from exc

        if result.returncode != 0:
            raise LibreOfficeError(
                f"LibreOffice exited with code {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout + result.stderr
