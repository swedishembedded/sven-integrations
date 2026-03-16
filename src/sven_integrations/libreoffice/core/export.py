"""Export helpers for LibreOffice documents using the headless CLI."""

from __future__ import annotations

from pathlib import Path

from ..backend import LibreOfficeBackend


_FORMAT_MAP: dict[str, list[str]] = {
    "writer": ["pdf", "docx", "odt", "rtf", "txt", "html"],
    "calc": ["pdf", "xlsx", "ods", "csv", "html"],
    "impress": ["pdf", "pptx", "odp", "html"],
    "draw": ["pdf", "svg", "png", "odg"],
}


def get_supported_formats() -> dict[str, list[str]]:
    """Return a mapping of document type → list of supported output formats."""
    return dict(_FORMAT_MAP)


def export_pdf(
    backend: LibreOfficeBackend,
    input_path: str,
    output_path: str,
    quality: int = 90,
) -> Path:
    """Export *input_path* to PDF.

    *quality* is advisory (1–100); the LibreOffice headless converter
    does not expose per-call quality settings, so this parameter is
    stored for documentation purposes.
    """
    if not (1 <= quality <= 100):
        raise ValueError(f"PDF quality must be 1–100, got {quality}")
    out_dir = str(Path(output_path).parent)
    return backend.convert(input_path, "pdf", out_dir)


def export_docx(
    backend: LibreOfficeBackend,
    odt_path: str,
    output_path: str,
) -> Path:
    """Convert an ODT file to DOCX format."""
    out_dir = str(Path(output_path).parent)
    return backend.convert(odt_path, "docx", out_dir)


def export_xlsx(
    backend: LibreOfficeBackend,
    ods_path: str,
    output_path: str,
) -> Path:
    """Convert an ODS file to XLSX format."""
    out_dir = str(Path(output_path).parent)
    return backend.convert(ods_path, "xlsx", out_dir)


def export_pptx(
    backend: LibreOfficeBackend,
    odp_path: str,
    output_path: str,
) -> Path:
    """Convert an ODP file to PPTX format."""
    out_dir = str(Path(output_path).parent)
    return backend.convert(odp_path, "pptx", out_dir)


def export_html(
    backend: LibreOfficeBackend,
    input_path: str,
    output_path: str,
) -> Path:
    """Export *input_path* to HTML."""
    out_dir = str(Path(output_path).parent)
    return backend.convert(input_path, "html", out_dir)
