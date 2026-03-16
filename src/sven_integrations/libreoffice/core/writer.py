"""Writer document operations — builds an in-memory document model for export."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WriterParagraph:
    """A single paragraph or heading in a Writer document."""

    text: str
    style: str = "Default"
    heading_level: int = 0


@dataclass
class WriterTable:
    """A table to be inserted into a Writer document."""

    rows: int
    cols: int
    data: list[list[str]] = field(default_factory=list)


@dataclass
class WriterDocument:
    """In-memory model for a LibreOffice Writer document."""

    title: str
    author: str = ""
    paragraphs: list[WriterParagraph] = field(default_factory=list)
    tables: list[WriterTable] = field(default_factory=list)
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    orientation: str = "portrait"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "paragraphs": [
                {"text": p.text, "style": p.style, "heading_level": p.heading_level}
                for p in self.paragraphs
            ],
            "tables": [
                {"rows": t.rows, "cols": t.cols, "data": t.data}
                for t in self.tables
            ],
            "page_width_mm": self.page_width_mm,
            "page_height_mm": self.page_height_mm,
            "orientation": self.orientation,
        }


def create_document(title: str, author: str = "") -> WriterDocument:
    """Initialise a new blank Writer document."""
    return WriterDocument(title=title, author=author)


def set_content(doc: WriterDocument, text: str) -> WriterDocument:
    """Replace all paragraph content with a single body paragraph."""
    doc.paragraphs = [WriterParagraph(text=text, style="Body Text")]
    return doc


def append_paragraph(doc: WriterDocument, text: str, style: str = "Default") -> WriterDocument:
    """Append a paragraph with the given style."""
    doc.paragraphs.append(WriterParagraph(text=text, style=style))
    return doc


def set_heading(doc: WriterDocument, level: int, text: str) -> WriterDocument:
    """Append a heading paragraph at the specified level (1–6)."""
    if not (1 <= level <= 6):
        raise ValueError(f"Heading level must be 1–6, got {level}")
    style = f"Heading {level}"
    doc.paragraphs.append(WriterParagraph(text=text, style=style, heading_level=level))
    return doc


def insert_table(
    doc: WriterDocument,
    rows: int,
    cols: int,
    data: list[list[str]] | None = None,
) -> WriterDocument:
    """Append a table with the given dimensions and optional cell data."""
    if rows < 1 or cols < 1:
        raise ValueError(f"Table must have at least 1 row and 1 column, got {rows}×{cols}")
    table_data = data or [[""] * cols for _ in range(rows)]
    doc.tables.append(WriterTable(rows=rows, cols=cols, data=table_data))
    return doc


def set_page_size(
    doc: WriterDocument,
    width_mm: float,
    height_mm: float,
    orientation: str = "portrait",
) -> WriterDocument:
    """Set the page dimensions."""
    if orientation not in ("portrait", "landscape"):
        raise ValueError(f"orientation must be 'portrait' or 'landscape', got {orientation!r}")
    doc.page_width_mm = width_mm
    doc.page_height_mm = height_mm
    doc.orientation = orientation
    return doc


def find_replace(
    doc: WriterDocument,
    search: str,
    replacement: str,
    case_sensitive: bool = False,
) -> int:
    """Perform find-and-replace across all paragraph text.

    Returns the number of substitutions made.
    """
    count = 0
    for para in doc.paragraphs:
        if case_sensitive:
            new_text = para.text.replace(search, replacement)
        else:
            import re
            new_text, n = re.subn(re.escape(search), replacement, para.text, flags=re.IGNORECASE)
            count += n
            para.text = new_text
            continue
        if new_text != para.text:
            count += para.text.count(search)
            para.text = new_text
    return count


def get_word_count(doc: WriterDocument) -> int:
    """Return approximate word count across all paragraphs."""
    total = 0
    for para in doc.paragraphs:
        total += len(para.text.split())
    return total
