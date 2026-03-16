"""LibreOffice session — persistent state for the libreoffice harness."""

from __future__ import annotations

from typing import Any

from ..shared import BaseSession
from .project import OfficeDocument


class LibreOfficeSession(BaseSession):
    """Named persistent session for a LibreOffice workspace.

    ``data`` stores the serialised ``OfficeDocument`` under the ``"document"`` key.
    """

    harness: str = "libreoffice"

    def get_document(self) -> OfficeDocument | None:
        raw = self.data.get("document")
        if raw is None:
            return None
        return OfficeDocument.from_dict(raw)

    def set_document(self, doc: OfficeDocument) -> None:
        self.data["document"] = doc.to_dict()

    def has_document(self) -> bool:
        return "document" in self.data

    def status(self) -> dict[str, Any]:
        doc = self.get_document()
        return {
            "session": self.name,
            "harness": self.harness,
            "has_document": doc is not None,
            "doc_type": doc.doc_type if doc else None,
            "title": doc.title if doc else None,
            "modified": doc.modified if doc else False,
        }
