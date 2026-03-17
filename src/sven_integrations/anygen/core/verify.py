"""File integrity verification for AnyGen output files."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

VERIFIABLE_EXTENSIONS = frozenset(
    {".pptx", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".json", ".xml"}
)


class VerifyError(ValueError):
    """Raised when a file fails an integrity check."""


def verify_file(path: str | Path) -> dict[str, Any]:
    """Verify the integrity of an AnyGen output file.

    Returns a dict: ``{path, type, size, ok, details}``.
    Raises ``VerifyError`` on any integrity failure.
    """
    p = Path(path)
    if not p.exists():
        raise VerifyError(f"File not found: {path}")

    suffix = p.suffix.lower()
    size = p.stat().st_size

    if suffix in (".pptx", ".docx"):
        _verify_office_zip(p, suffix)
        details = f"Valid {suffix.lstrip('.').upper()} (ZIP/OPC container)"
    elif suffix == ".pdf":
        _verify_pdf(p)
        details = "Valid PDF"
    elif suffix in (".png", ".jpg", ".jpeg"):
        _verify_image(p, suffix)
        details = f"Valid {suffix.lstrip('.').upper()} image"
    elif suffix == ".svg":
        _verify_svg(p)
        details = "Valid SVG"
    elif suffix == ".json":
        _verify_json(p)
        details = "Valid JSON"
    elif suffix == ".xml":
        _verify_xml(p)
        details = "Valid XML"
    else:
        details = f"Unknown extension {suffix!r} — skipped integrity check"

    return {
        "path": str(p.resolve()),
        "type": suffix.lstrip(".") or "unknown",
        "size": size,
        "ok": True,
        "details": details,
    }


# ------------------------------------------------------------------
# Per-format checkers


def _verify_office_zip(p: Path, suffix: str) -> None:
    """PPTX and DOCX are ZIP/OPC containers; must contain [Content_Types].xml."""
    if p.stat().st_size == 0:
        raise VerifyError(f"{p.name}: file is empty")
    try:
        with zipfile.ZipFile(p, "r") as zf:
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise VerifyError(f"{p.name}: not a valid ZIP archive: {exc}") from exc

    if "[Content_Types].xml" not in names:
        raise VerifyError(
            f"{p.name}: missing [Content_Types].xml — not a valid {suffix.upper()}"
        )
    if suffix == ".pptx" and not any(n.startswith("ppt/") for n in names):
        raise VerifyError(f"{p.name}: missing ppt/ directory — not a valid PPTX")
    if suffix == ".docx" and not any(n.startswith("word/") for n in names):
        raise VerifyError(f"{p.name}: missing word/ directory — not a valid DOCX")


def _verify_pdf(p: Path) -> None:
    if p.stat().st_size < 5:
        raise VerifyError(f"{p.name}: file too small to be a PDF")
    with p.open("rb") as fh:
        header = fh.read(5)
    if header[:4] != b"%PDF":
        raise VerifyError(f"{p.name}: invalid PDF magic bytes (got {header[:4]!r})")


def _verify_image(p: Path, suffix: str) -> None:
    if p.stat().st_size < 8:
        raise VerifyError(f"{p.name}: file too small to be an image")
    with p.open("rb") as fh:
        header = fh.read(8)
    if suffix == ".png":
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            raise VerifyError(f"{p.name}: invalid PNG magic bytes")
    elif suffix in (".jpg", ".jpeg"):
        if header[:2] != b"\xff\xd8":
            raise VerifyError(f"{p.name}: invalid JPEG magic bytes")


def _verify_svg(p: Path) -> None:
    text = p.read_text(encoding="utf-8", errors="replace")
    if "<svg" not in text.lower():
        raise VerifyError(f"{p.name}: no <svg> element found — not a valid SVG")


def _verify_json(p: Path) -> None:
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerifyError(f"{p.name}: invalid JSON: {exc}") from exc


def _verify_xml(p: Path) -> None:
    try:
        ET.parse(str(p))
    except ET.ParseError as exc:
        raise VerifyError(f"{p.name}: invalid XML: {exc}") from exc
