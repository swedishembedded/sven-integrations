"""Shotcut backend — melt CLI wrapper and MLT validation."""

from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class ShotcutError(RuntimeError):
    """Raised when a Shotcut or melt operation fails."""


def _find_melt() -> str:
    for candidate in ("melt", "melt-7", "mlt-melt"):
        if shutil.which(candidate):
            return candidate
    raise ShotcutError("melt binary not found; install the MLT framework")


def _find_shotcut() -> str | None:
    for candidate in ("shotcut", "Shotcut"):
        if shutil.which(candidate):
            return candidate
    return None


class ShotcutBackend:
    """Thin wrapper around the Shotcut CLI and the melt command."""

    # ------------------------------------------------------------------
    # Rendering

    def render_mlt(
        self,
        mlt_path: str,
        output_path: str,
        profile: str = "atsc_1080p_25",
    ) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        """Render an MLT project file to *output_path* via melt.

        Returns the completed subprocess result.
        """
        if not Path(mlt_path).exists():
            raise ShotcutError(f"MLT file not found: {mlt_path}")

        melt = _find_melt()
        cmd = [
            melt,
            "-profile", profile,
            mlt_path,
            "-consumer", f"avformat:{output_path}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode != 0:
            raise ShotcutError(f"melt render failed (rc={result.returncode}): {result.stderr.strip()}")
        return result

    # ------------------------------------------------------------------
    # Validation

    def validate_mlt(self, mlt_path: str) -> bool:
        """Return True if *mlt_path* is well-formed MLT XML."""
        try:
            tree = ET.parse(mlt_path)
            root = tree.getroot()
            return root.tag == "mlt"
        except (ET.ParseError, FileNotFoundError, OSError):
            return False

    # ------------------------------------------------------------------
    # Preview frame

    def preview_frame(self, mlt_path: str, frame_num: int, output_png: str) -> None:
        """Extract a single frame from an MLT project as a PNG image."""
        if not Path(mlt_path).exists():
            raise ShotcutError(f"MLT file not found: {mlt_path}")

        melt = _find_melt()
        cmd = [
            melt,
            mlt_path,
            "-consumer", f"avformat:{output_png}",
            "-in", str(frame_num),
            "-out", str(frame_num),
            "vcodec=png",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise ShotcutError(f"Frame extraction failed: {result.stderr.strip()}")

    # ------------------------------------------------------------------
    # Media info

    def get_media_info(self, path: str) -> dict[str, Any]:
        """Return basic media metadata via melt -query or ffprobe fallback."""
        if not Path(path).exists():
            raise ShotcutError(f"Media file not found: {path}")

        # Try melt -query consumer first
        try:
            melt = _find_melt()
            result = subprocess.run(
                [melt, path, "-consumer", "null", "-frames", "0"],
                capture_output=True, text=True, timeout=30,
            )
            # Parse whatever we can from stderr / stdout
            info: dict[str, Any] = {"path": path, "source": "melt"}
            for line in (result.stdout + result.stderr).splitlines():
                if "width:" in line.lower():
                    try:
                        info["width"] = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "height:" in line.lower():
                    try:
                        info["height"] = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "fps:" in line.lower() or "frame_rate" in line.lower():
                    try:
                        info["fps"] = float(line.split(":")[-1].strip())
                    except ValueError:
                        pass
            return info
        except ShotcutError:
            pass

        # Fallback: use ffprobe if available
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            result = subprocess.run(
                [
                    ffprobe, "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams", path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    streams = data.get("streams", [])
                    info = {"path": path, "source": "ffprobe", "streams": []}
                    for s in streams:
                        info["streams"].append({  # type: ignore[union-attr]
                            "codec_type": s.get("codec_type"),
                            "codec_name": s.get("codec_name"),
                            "width": s.get("width"),
                            "height": s.get("height"),
                            "r_frame_rate": s.get("r_frame_rate"),
                        })
                    return info
                except (json.JSONDecodeError, KeyError):
                    pass

        return {"path": path, "source": "unknown", "error": "no probe tool available"}
