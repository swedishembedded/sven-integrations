"""Document profile and settings management for LibreOffice projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..project import OfficeDocument


# ---------------------------------------------------------------------------
# Document profiles

@dataclass
class DocumentProfile:
    """Physical page-size profile for a document."""

    name: str
    width_mm: float
    height_mm: float
    height_mm_landscape: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "height_mm_landscape": self.height_mm_landscape,
            "description": self.description,
        }


DOCUMENT_PROFILES: dict[str, DocumentProfile] = {
    "a4": DocumentProfile(
        name="a4",
        width_mm=210.0,
        height_mm=297.0,
        height_mm_landscape=210.0,
        description="ISO A4 (210 × 297 mm)",
    ),
    "a5": DocumentProfile(
        name="a5",
        width_mm=148.0,
        height_mm=210.0,
        height_mm_landscape=148.0,
        description="ISO A5 (148 × 210 mm)",
    ),
    "b5": DocumentProfile(
        name="b5",
        width_mm=176.0,
        height_mm=250.0,
        height_mm_landscape=176.0,
        description="ISO B5 (176 × 250 mm)",
    ),
    "letter": DocumentProfile(
        name="letter",
        width_mm=215.9,
        height_mm=279.4,
        height_mm_landscape=215.9,
        description="US Letter (8.5 × 11 in)",
    ),
    "legal": DocumentProfile(
        name="legal",
        width_mm=215.9,
        height_mm=355.6,
        height_mm_landscape=215.9,
        description="US Legal (8.5 × 14 in)",
    ),
    "presentation_4_3": DocumentProfile(
        name="presentation_4_3",
        width_mm=254.0,
        height_mm=190.5,
        height_mm_landscape=254.0,
        description="Presentation 4:3 (10 × 7.5 in)",
    ),
    "presentation_16_9": DocumentProfile(
        name="presentation_16_9",
        width_mm=330.2,
        height_mm=190.5,
        height_mm_landscape=330.2,
        description="Widescreen 16:9 (13 × 7.5 in)",
    ),
}


# ---------------------------------------------------------------------------
# Document settings

@dataclass
class DocumentSettings:
    """Optional creation settings for a new document."""

    margins_mm: dict[str, float] = field(
        default_factory=lambda: {"top": 25.0, "bottom": 25.0, "left": 25.0, "right": 25.0}
    )
    language: str = "en-US"
    author: str = ""
    title: str = ""
    subject: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "margins_mm": self.margins_mm,
            "language": self.language,
            "author": self.author,
            "title": self.title,
            "subject": self.subject,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentSettings":
        return cls(
            margins_mm=data.get("margins_mm", {"top": 25.0, "bottom": 25.0, "left": 25.0, "right": 25.0}),
            language=data.get("language", "en-US"),
            author=data.get("author", ""),
            title=data.get("title", ""),
            subject=data.get("subject", ""),
        )


# ---------------------------------------------------------------------------
# Public API

_VALID_METADATA_KEYS = frozenset({"title", "author", "subject", "language"})


def create_document(
    doc_type: str,
    name: str,
    profile: str = "a4",
    settings: dict[str, Any] | None = None,
) -> OfficeDocument:
    """Create a new :class:`OfficeDocument` with the given profile and settings.

    Parameters
    ----------
    doc_type:
        One of ``writer``, ``calc``, ``impress``, ``draw``.
    name:
        Display name / title of the document.
    profile:
        Key into :data:`DOCUMENT_PROFILES`.  Defaults to ``"a4"``.
    settings:
        Optional dict of document settings (margins, author, language, etc.).
        Missing keys fall back to :class:`DocumentSettings` defaults.
    """
    if profile not in DOCUMENT_PROFILES:
        raise ValueError(
            f"Unknown profile {profile!r}.  Available: {sorted(DOCUMENT_PROFILES)}"
        )

    doc_settings = DocumentSettings.from_dict(settings or {})
    meta: dict[str, Any] = {
        "profile": profile,
        "margins_mm": doc_settings.margins_mm,
        "language": doc_settings.language,
    }
    if doc_settings.author:
        meta["author"] = doc_settings.author
    if doc_settings.title:
        meta["title"] = doc_settings.title
    if doc_settings.subject:
        meta["subject"] = doc_settings.subject

    doc = OfficeDocument(
        doc_type=doc_type,
        title=name,
        author=doc_settings.author,
    )
    doc.extra["metadata"] = meta
    return doc


def get_document_info(doc: OfficeDocument) -> dict[str, Any]:
    """Return a concise summary of the document's type, name, and contents."""
    meta = doc.extra.get("metadata", {})
    styles = doc.extra.get("styles", {})

    info: dict[str, Any] = {
        "type": doc.doc_type,
        "name": doc.title,
        "profile": meta.get("profile", "a4"),
        "author": doc.author,
        "modified": doc.modified,
        "language": meta.get("language", "en-US"),
        "style_count": len(styles),
    }

    if doc.doc_type == "writer":
        info["content_count"] = 0
    elif doc.doc_type in ("calc", "impress", "draw"):
        info["sheet_count"] = doc.sheet_count()

    return info


def list_profiles() -> list[dict[str, Any]]:
    """Return all available document profiles as a list of dicts."""
    return [p.to_dict() for p in DOCUMENT_PROFILES.values()]


def set_document_property(
    doc: OfficeDocument,
    key: str,
    value: Any,
) -> dict[str, Any]:
    """Set a metadata property on the document.

    Recognised keys: ``title``, ``author``, ``subject``, ``language``.
    The value is stored in ``doc.extra["metadata"]`` and also reflected on
    the top-level ``doc.title`` / ``doc.author`` fields where applicable.
    """
    if key not in _VALID_METADATA_KEYS:
        raise ValueError(
            f"Unknown document property {key!r}.  "
            f"Allowed: {sorted(_VALID_METADATA_KEYS)}"
        )

    meta = doc.extra.setdefault("metadata", {})
    meta[key] = value
    doc.modified = True

    if key == "title":
        doc.title = str(value)
    elif key == "author":
        doc.author = str(value)

    return {
        "action": "set_document_property",
        "key": key,
        "value": value,
    }
