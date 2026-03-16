"""Export helpers for the GIMP harness.

Each ``export_*`` function builds a result dict containing:

* ``"action"`` — identifier string
* ``"path"`` — destination file path
* ``"cmd"`` — the full subprocess argument list (``list[str]``) ready for
  ``subprocess.run``

:func:`build_export_cmd` is the canonical factory used by all helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_SUPPORTED_FORMATS: frozenset[str] = frozenset(
    {"png", "jpeg", "jpg", "tiff", "webp", "pdf"}
)


class ExportError(ValueError):
    """Raised for unsupported or misconfigured export requests."""


def _img_preamble() -> str:
    return (
        "(let* ((image (car (gimp-image-list))) "
        "(drawable (car (gimp-image-get-active-drawable image)))) "
    )


def export_png(
    path: str,
    interlace: int = 0,
    compression: int = 6,
) -> dict[str, Any]:
    """Export the active image as PNG.

    Parameters
    ----------
    interlace:
        ``0`` = non-interlaced, ``1`` = interlaced (Adam7).
    compression:
        zlib compression level ``0``–``9``.
    """
    return {
        "action": "export_png",
        "path": path,
        "interlace": interlace,
        "compression": compression,
        "cmd": build_export_cmd("png", path, interlace=interlace, compression=compression),
    }


def export_jpeg(path: str, quality: int = 90) -> dict[str, Any]:
    """Export the active image as JPEG.

    Parameters
    ----------
    quality:
        Encoding quality, ``0`` (lowest) – ``100`` (highest).
    """
    if not 0 <= quality <= 100:
        raise ExportError(f"JPEG quality must be 0–100, got {quality}")
    return {
        "action": "export_jpeg",
        "path": path,
        "quality": quality,
        "cmd": build_export_cmd("jpeg", path, quality=quality),
    }


def export_tiff(path: str, compression: str = "none") -> dict[str, Any]:
    """Export the active image as TIFF."""
    return {
        "action": "export_tiff",
        "path": path,
        "compression": compression,
        "cmd": build_export_cmd("tiff", path, compression=compression),
    }


def export_webp(path: str, quality: int = 85) -> dict[str, Any]:
    """Export the active image as WebP.

    Parameters
    ----------
    quality:
        Lossy quality ``0``–``100``.  Use ``100`` for lossless.
    """
    if not 0 <= quality <= 100:
        raise ExportError(f"WebP quality must be 0–100, got {quality}")
    return {
        "action": "export_webp",
        "path": path,
        "quality": quality,
        "cmd": build_export_cmd("webp", path, quality=quality),
    }


def export_pdf(path: str) -> dict[str, Any]:
    """Export the active image as a single-page PDF."""
    return {
        "action": "export_pdf",
        "path": path,
        "cmd": build_export_cmd("pdf", path),
    }


def build_export_cmd(fmt: str, path: str, **opts: Any) -> list[str]:
    """Build a GIMP batch subprocess command for exporting *path* as *fmt*.

    Returns a ``list[str]`` suitable for :func:`subprocess.run`.

    Raises
    ------
    ExportError
        If *fmt* is not in :data:`_SUPPORTED_FORMATS`.
    """
    fmt_key = fmt.lower().lstrip(".")
    if fmt_key not in _SUPPORTED_FORMATS:
        raise ExportError(
            f"Unsupported export format {fmt!r}. "
            f"Choose from: {', '.join(sorted(_SUPPORTED_FORMATS))}"
        )

    escaped_path = path.replace('"', '\\"')
    fname = Path(path).name.replace('"', '\\"')
    preamble = _img_preamble()

    if fmt_key == "png":
        interlace = int(opts.get("interlace", 0))
        compression = int(opts.get("compression", 6))
        script = (
            f"{preamble}"
            f'(file-png-save RUN-NONINTERACTIVE image drawable '
            f'"{escaped_path}" "{fname}" {interlace} {compression} 1 1 1 1 1))'
        )
    elif fmt_key in ("jpeg", "jpg"):
        quality = float(opts.get("quality", 90)) / 100.0
        script = (
            f"{preamble}"
            f'(file-jpeg-save RUN-NONINTERACTIVE image drawable '
            f'"{escaped_path}" "{fname}" {quality:.4f} 0 0 0 "" 0 1 0 2 0))'
        )
    elif fmt_key == "tiff":
        script = (
            f"{preamble}"
            f'(file-tiff-save RUN-NONINTERACTIVE image drawable '
            f'"{escaped_path}" "{fname}" 0))'
        )
    elif fmt_key == "webp":
        quality = int(opts.get("quality", 85))
        script = (
            f"{preamble}"
            f'(file-webp-save RUN-NONINTERACTIVE image drawable '
            f'"{escaped_path}" "{fname}" 0 {quality} 0 0 0))'
        )
    elif fmt_key == "pdf":
        script = (
            f"{preamble}"
            f'(file-pdf-save RUN-NONINTERACTIVE image drawable '
            f'"{escaped_path}" "{fname}" 0 0))'
        )
    else:
        raise ExportError(f"No script template for format {fmt_key!r}")

    return [
        "gimp",
        "--no-interface",
        "--batch",
        script,
        "--batch",
        "(gimp-quit 0)",
    ]
