"""LibreOffice document model — dataclass representation of an office document."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SheetInfo:
    """Metadata about a single sheet (Calc) or slide (Impress)."""

    index: int
    name: str
    visible: bool = True
    cells: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SheetInfo":
        return cls(
            index=int(data["index"]),
            name=data["name"],
            visible=bool(data.get("visible", True)),
            cells=data.get("cells", {}),
        )


@dataclass
class OfficeDocument:
    """Top-level model for a LibreOffice document of any type."""

    doc_type: str  # writer | calc | impress | draw
    title: str
    file_path: str | None = None
    author: str = ""
    modified: bool = False
    sheets_or_slides: list[SheetInfo] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    _VALID_TYPES = frozenset({"writer", "calc", "impress", "draw"})

    def __post_init__(self) -> None:
        if self.doc_type not in self._VALID_TYPES:
            raise ValueError(
                f"doc_type must be one of {self._VALID_TYPES}, got {self.doc_type!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "title": self.title,
            "file_path": self.file_path,
            "author": self.author,
            "modified": self.modified,
            "sheets_or_slides": [s.to_dict() for s in self.sheets_or_slides],
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OfficeDocument":
        sheets = [SheetInfo.from_dict(s) for s in data.get("sheets_or_slides", [])]
        return cls(
            doc_type=data["doc_type"],
            title=data["title"],
            file_path=data.get("file_path"),
            author=data.get("author", ""),
            modified=bool(data.get("modified", False)),
            sheets_or_slides=sheets,
            extra=data.get("extra", {}),
        )

    def add_sheet(self, sheet: SheetInfo) -> None:
        self.sheets_or_slides.append(sheet)
        self.modified = True

    def remove_sheet(self, name: str) -> SheetInfo:
        for i, s in enumerate(self.sheets_or_slides):
            if s.name == name:
                removed = self.sheets_or_slides.pop(i)
                self.modified = True
                return removed
        raise KeyError(f"No sheet/slide named {name!r}")

    def find_sheet(self, name: str) -> SheetInfo | None:
        for s in self.sheets_or_slides:
            if s.name == name:
                return s
        return None

    def sheet_count(self) -> int:
        return len(self.sheets_or_slides)
