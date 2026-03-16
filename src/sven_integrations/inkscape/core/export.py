"""Export helpers for the Inkscape harness.

:func:`build_actions` is the canonical factory used by the higher-level
``export_*`` wrappers.  All functions return a result dict containing an
``"actions"`` key with a ``list[str]`` ready for
:meth:`~sven_integrations.inkscape.backend.InkscapeBackend.run_actions`.
"""

from __future__ import annotations

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
