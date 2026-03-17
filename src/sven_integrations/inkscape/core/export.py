"""Export helpers for the Inkscape harness.

:func:`build_actions` is the canonical factory used by the higher-level
``export_*`` wrappers.  All functions return a result dict containing an
``"actions"`` key with a ``list[str]`` ready for
:meth:`~sven_integrations.inkscape.backend.InkscapeBackend.run_actions`.

:func:`run_export` invokes the Inkscape binary to produce output files.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Literal

_SUPPORTED_FORMATS: frozenset[str] = frozenset({"png", "pdf", "eps", "emf", "svg"})


class ExportError(ValueError):
    """Raised for unsupported or misconfigured export requests."""


def export_png(
    svg_path: str,
    out_path: str,
    dpi: float = 96.0,
    area: Literal["page", "drawing", "selection"] = "page",
) -> dict[str, Any]:
    """Export an SVG to PNG.

    Parameters
    ----------
    dpi:
        Rasterisation resolution in dots per inch.
    area:
        Which portion of the document to export:
        ``"page"`` (default), ``"drawing"``, or ``"selection"``.
    """
    actions = build_actions("png", out_path, dpi=dpi, area=area)
    return {
        "action": "export_png",
        "svg_path": svg_path,
        "out_path": out_path,
        "dpi": dpi,
        "area": area,
        "actions": actions,
    }


def export_pdf(svg_path: str, out_path: str) -> dict[str, Any]:
    """Export an SVG to PDF."""
    actions = build_actions("pdf", out_path)
    return {
        "action": "export_pdf",
        "svg_path": svg_path,
        "out_path": out_path,
        "actions": actions,
    }


def export_eps(svg_path: str, out_path: str) -> dict[str, Any]:
    """Export an SVG to EPS (Encapsulated PostScript)."""
    actions = build_actions("eps", out_path)
    return {
        "action": "export_eps",
        "svg_path": svg_path,
        "out_path": out_path,
        "actions": actions,
    }


def export_emf(svg_path: str, out_path: str) -> dict[str, Any]:
    """Export an SVG to EMF (Enhanced Metafile)."""
    actions = build_actions("emf", out_path)
    return {
        "action": "export_emf",
        "svg_path": svg_path,
        "out_path": out_path,
        "actions": actions,
    }


def export_area(
    svg_path: str,
    out_path: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    dpi: float = 96.0,
) -> dict[str, Any]:
    """Export a rectangular area of the document as PNG.

    *(x0, y0)* is the top-left corner; *(x1, y1)* is the bottom-right,
    both in SVG user units.
    """
    actions = build_actions(
        "png", out_path, dpi=dpi, area_rect=(x0, y0, x1, y1)
    )
    return {
        "action": "export_area",
        "svg_path": svg_path,
        "out_path": out_path,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "dpi": dpi,
        "actions": actions,
    }


def build_actions(fmt: str, out_path: str, **opts: Any) -> list[str]:
    """Build the Inkscape action list for exporting *out_path* as *fmt*.

    Returns a ``list[str]`` of action strings suitable for
    :meth:`~sven_integrations.inkscape.backend.InkscapeBackend.run_actions`.

    Raises
    ------
    ExportError
        If *fmt* is not in :data:`_SUPPORTED_FORMATS`.
    """
    fmt_key = fmt.lower().lstrip(".")
    if fmt_key not in _SUPPORTED_FORMATS:
        raise ExportError(
            f"Unsupported format {fmt!r}. "
            f"Choose from: {', '.join(sorted(_SUPPORTED_FORMATS))}"
        )

    actions: list[str] = [f"export-type:{fmt_key}"]

    if fmt_key == "png":
        dpi = float(opts.get("dpi", 96.0))
        actions.append(f"export-dpi:{dpi}")
        area_rect: tuple[float, float, float, float] | None = opts.get("area_rect")
        if area_rect is not None:
            x0, y0, x1, y1 = area_rect
            actions.append(f"export-area:{x0},{y0},{x1},{y1}")
        else:
            area_name = str(opts.get("area", "page"))
            if area_name == "drawing":
                actions.append("export-area-drawing")
            elif area_name == "selection":
                actions.append("export-area-snap-to-drawing")
            else:
                actions.append("export-area-page")

    actions.append(f"export-filename:{out_path}")
    actions.append("export-do")
    return actions


def find_inkscape() -> str | None:
    """Return path to Inkscape executable, or None if not found."""
    return shutil.which("inkscape")


def _export_png_cairosvg(svg_path: str, out_path: str, dpi: float) -> dict[str, Any]:
    """Fallback: use cairosvg when Inkscape is unavailable or produces no output."""
    try:
        from cairosvg import svg2png
    except ImportError:
        raise ExportError(
            "cairosvg is not installed. Install with: pip install cairosvg"
        )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    out_abs = os.path.abspath(out_path)
    # cairosvg: scale = dpi/96 gives correct pixel dimensions for requested DPI
    scale = dpi / 96.0
    svg2png(url=svg_path, write_to=out_abs, scale=scale)
    if not os.path.exists(out_abs):
        raise ExportError("cairosvg produced no output")
    return {
        "ok": True,
        "output": out_abs,
        "format": "png",
        "method": "cairosvg",
        "file_size": os.path.getsize(out_abs),
    }


def run_export(
    svg_path: str,
    out_path: str,
    fmt: str,
    dpi: float = 96.0,
    timeout: int = 60,
) -> dict[str, Any]:
    """Export SVG to the given format.

    For PNG: tries Inkscape first; falls back to cairosvg if Inkscape is
    unavailable or produces no output.
    For PDF/EPS/EMF: requires Inkscape.
    Returns a result dict with ``ok``, ``output``, ``method``.
    """
    if not os.path.exists(svg_path):
        raise ExportError(f"SVG file not found: {svg_path}")

    fmt_key = fmt.lower().lstrip(".")
    if fmt_key not in _SUPPORTED_FORMATS:
        raise ExportError(
            f"Unsupported format {fmt!r}. "
            f"Choose from: {', '.join(sorted(_SUPPORTED_FORMATS))}"
        )

    out_abs = os.path.abspath(out_path)
    svg_abs = os.path.abspath(svg_path)
    os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)

    # PNG: try Inkscape, fall back to cairosvg
    if fmt_key == "png":
        inkscape = find_inkscape()
        if inkscape:
            cmd: list[str] = [
                inkscape,
                "--batch-process",
                "--export-type=png",
                f"--export-filename={out_abs}",
                "--export-overwrite",
                f"--export-dpi={dpi}",
                "--export-area-page",
                svg_abs,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0 and os.path.exists(out_abs):
                return {
                    "ok": True,
                    "output": out_abs,
                    "format": fmt_key,
                    "method": "inkscape",
                    "file_size": os.path.getsize(out_abs),
                }
        return _export_png_cairosvg(svg_path, out_path, dpi)

    # PDF/EPS/EMF: Inkscape only
    inkscape = find_inkscape()
    if not inkscape:
        raise ExportError(
            "Inkscape is not installed. Install it with: apt install inkscape"
        )
    cmd = [
        inkscape,
        "--batch-process",
        f"--export-type={fmt_key}",
        f"--export-filename={out_abs}",
        "--export-overwrite",
        svg_abs,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-500:]
        raise ExportError(f"Inkscape export failed: {detail}")
    if not os.path.exists(out_abs):
        raise ExportError(f"Inkscape produced no output: {out_abs}")
    return {
        "ok": True,
        "output": out_abs,
        "format": fmt_key,
        "method": "inkscape",
        "file_size": os.path.getsize(out_abs),
    }
