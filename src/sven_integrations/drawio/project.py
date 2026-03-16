"""Draw.io document model using dataclasses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CellGeometry:
    x: float = 0.0
    y: float = 0.0
    width: float = 120.0
    height: float = 60.0

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CellGeometry":
        return cls(
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            width=float(d.get("width", 120.0)),
            height=float(d.get("height", 60.0)),
        )


@dataclass
class DrawioCell:
    cell_id: str
    value: str = ""
    style: str = ""
    vertex: bool = True
    edge: bool = False
    source_id: str | None = None
    target_id: str | None = None
    geometry: CellGeometry = field(default_factory=CellGeometry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "value": self.value,
            "style": self.style,
            "vertex": self.vertex,
            "edge": self.edge,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "geometry": self.geometry.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DrawioCell":
        return cls(
            cell_id=d["cell_id"],
            value=d.get("value", ""),
            style=d.get("style", ""),
            vertex=bool(d.get("vertex", True)),
            edge=bool(d.get("edge", False)),
            source_id=d.get("source_id"),
            target_id=d.get("target_id"),
            geometry=CellGeometry.from_dict(d.get("geometry", {})),
        )


@dataclass
class DrawioPage:
    page_id: str
    name: str
    cells: list[DrawioCell] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "name": self.name,
            "cells": [c.to_dict() for c in self.cells],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DrawioPage":
        return cls(
            page_id=d["page_id"],
            name=d["name"],
            cells=[DrawioCell.from_dict(c) for c in d.get("cells", [])],
        )


@dataclass
class DrawioDocument:
    file_path: str | None = None
    pages: list[DrawioPage] = field(default_factory=list)

    def add_page(self, name: str, page_id: str | None = None) -> DrawioPage:
        pid = page_id or str(uuid.uuid4())
        page = DrawioPage(page_id=pid, name=name)
        self.pages.append(page)
        return page

    def remove_page(self, name: str) -> bool:
        for i, page in enumerate(self.pages):
            if page.name == name:
                self.pages.pop(i)
                return True
        return False

    def add_cell(self, page_idx: int, cell: DrawioCell) -> None:
        if page_idx < 0 or page_idx >= len(self.pages):
            raise IndexError(f"Page index {page_idx} out of range")
        self.pages[page_idx].cells.append(cell)

    def find_cell(self, cell_id: str) -> DrawioCell | None:
        for page in self.pages:
            for cell in page.cells:
                if cell.cell_id == cell_id:
                    return cell
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "pages": [p.to_dict() for p in self.pages],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DrawioDocument":
        return cls(
            file_path=d.get("file_path"),
            pages=[DrawioPage.from_dict(p) for p in d.get("pages", [])],
        )

    def to_xml(self) -> str:
        from .drawio_xml import render_xml

        return render_xml(self)
