"""Interactive REPL console for the draw.io harness."""

from __future__ import annotations

from typing import Any

from ..shared import Console, Style
from .drawio_xml import add_connector, add_shape, render_xml, update_cell_label
from .project import DrawioDocument
from .session import DrawioSession


class DrawioConsole(Console):
    """REPL for draw.io diagram editing."""

    harness_name = "drawio"
    intro_extra = "Commands: shape, connector, page, export, status, help"

    def __init__(self, session_name: str = "default", **kwargs: Any) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._session = DrawioSession.open_or_create(session_name)
        self._doc: DrawioDocument | None = None
        raw = self._session.data.get("document")
        if raw:
            self._doc = DrawioDocument.from_dict(raw)

    def _save(self) -> None:
        if self._doc is not None:
            self._session.data["document"] = self._doc.to_dict()
        self._session.save()

    # ------------------------------------------------------------------
    # Commands

    def do_status(self, _arg: str) -> None:
        """Show current document and session status."""
        self.section("Session")
        self.bullet(f"name: {self._session.name}")
        if self._doc is None:
            self.bullet("document: (none)")
        else:
            self.bullet(f"pages: {len(self._doc.pages)}")
            for i, page in enumerate(self._doc.pages):
                self.bullet(f"  [{i}] {page.name!r} – {len(page.cells)} cells")

    def do_shape(self, arg: str) -> None:
        """Manage shapes. Usage: shape add|remove|label|list [options]"""
        parts = self.parse_args(arg)
        if not parts:
            print(Style.err("  Usage: shape add|remove|label|list [...]"))
            return
        sub = parts[0]
        if sub == "add":
            self._shape_add(parts[1:])
        elif sub == "remove":
            self._shape_remove(parts[1:])
        elif sub == "label":
            self._shape_label(parts[1:])
        elif sub == "list":
            self._shape_list()
        else:
            print(Style.err(f"  Unknown shape sub-command: {sub!r}"))

    def _shape_add(self, parts: list[str]) -> None:
        if self._doc is None or not self._doc.pages:
            print(Style.err("  No document open. Use 'new' first."))
            return
        # parse --type --label --x --y --width --height
        kwargs: dict[str, Any] = {
            "shape_type": "rectangle",
            "label": "",
            "x": 100.0,
            "y": 100.0,
            "w": 120.0,
            "h": 60.0,
        }
        it = iter(parts)
        for tok in it:
            if tok in ("--type", "-t"):
                kwargs["shape_type"] = next(it, "rectangle")
            elif tok in ("--label", "-l"):
                kwargs["label"] = next(it, "")
            elif tok == "--x":
                kwargs["x"] = float(next(it, 100))
            elif tok == "--y":
                kwargs["y"] = float(next(it, 100))
            elif tok in ("--width", "-w"):
                kwargs["w"] = float(next(it, 120))
            elif tok in ("--height", "-H"):
                kwargs["h"] = float(next(it, 60))
        cid = add_shape(self._doc, 0, **kwargs)
        self._save()
        self.success(f"Shape added: {cid}")

    def _shape_remove(self, parts: list[str]) -> None:
        if self._doc is None or not self._doc.pages:
            print(Style.err("  No document open."))
            return
        from .drawio_xml import remove_cell

        cell_id = parts[0] if parts else ""
        if not cell_id:
            print(Style.err("  Provide --id <cell_id>"))
            return
        if cell_id.startswith("--id"):
            cell_id = parts[1] if len(parts) > 1 else ""
        removed = remove_cell(self._doc, 0, cell_id)
        if removed:
            self._save()
            self.success(f"Removed cell {cell_id}")
        else:
            self.failure(f"Cell not found: {cell_id}")

    def _shape_label(self, parts: list[str]) -> None:
        if self._doc is None or not self._doc.pages:
            print(Style.err("  No document open."))
            return
        cell_id = ""
        label = ""
        it = iter(parts)
        for tok in it:
            if tok == "--id":
                cell_id = next(it, "")
            elif tok in ("--text", "--label"):
                label = next(it, "")
        if not cell_id:
            print(Style.err("  Provide --id <cell_id> --text <label>"))
            return
        ok = update_cell_label(self._doc, 0, cell_id, label)
        if ok:
            self._save()
            self.success(f"Label updated on {cell_id}")
        else:
            self.failure(f"Cell not found: {cell_id}")

    def _shape_list(self) -> None:
        if self._doc is None or not self._doc.pages:
            self.bullet("(no document)")
            return
        for page in self._doc.pages:
            self.section(f"Page: {page.name}")
            for cell in page.cells:
                if cell.vertex:
                    self.bullet(f"{cell.cell_id[:8]}… value={cell.value!r} style={cell.style[:40]}")

    def do_connector(self, arg: str) -> None:
        """Manage connectors. Usage: connector add|remove [options]"""
        parts = self.parse_args(arg)
        if not parts:
            print(Style.err("  Usage: connector add|remove [...]"))
            return
        sub = parts[0]
        if sub == "add":
            self._connector_add(parts[1:])
        elif sub == "remove":
            self._connector_remove(parts[1:])
        else:
            print(Style.err(f"  Unknown connector sub-command: {sub!r}"))

    def _connector_add(self, parts: list[str]) -> None:
        if self._doc is None or not self._doc.pages:
            print(Style.err("  No document open."))
            return
        src = ""
        tgt = ""
        label = ""
        it = iter(parts)
        for tok in it:
            if tok in ("--from", "--src"):
                src = next(it, "")
            elif tok in ("--to", "--tgt"):
                tgt = next(it, "")
            elif tok in ("--label", "-l"):
                label = next(it, "")
        if not src or not tgt:
            print(Style.err("  Provide --from <id> --to <id>"))
            return
        eid = add_connector(self._doc, 0, src, tgt, label)
        self._save()
        self.success(f"Connector added: {eid}")

    def _connector_remove(self, parts: list[str]) -> None:
        from .drawio_xml import remove_cell

        if self._doc is None or not self._doc.pages:
            print(Style.err("  No document open."))
            return
        cell_id = parts[1] if len(parts) > 1 and parts[0] == "--id" else (parts[0] if parts else "")
        if not cell_id:
            print(Style.err("  Provide --id <edge_id>"))
            return
        removed = remove_cell(self._doc, 0, cell_id)
        if removed:
            self._save()
            self.success(f"Connector removed: {cell_id}")
        else:
            self.failure(f"Edge not found: {cell_id}")

    def do_page(self, arg: str) -> None:
        """Manage pages. Usage: page add|remove|list [--name NAME]"""
        parts = self.parse_args(arg)
        if not parts:
            print(Style.err("  Usage: page add|remove|list [--name NAME]"))
            return
        sub = parts[0]
        if sub == "add":
            if self._doc is None:
                print(Style.err("  No document. Use 'new' first."))
                return
            name = parts[2] if len(parts) > 2 and parts[1] == "--name" else (parts[1] if len(parts) > 1 else "New Page")
            page = self._doc.add_page(name)
            self._save()
            self.success(f"Page added: {page.name!r}")
        elif sub == "remove":
            if self._doc is None:
                return
            name = parts[2] if len(parts) > 2 and parts[1] == "--name" else (parts[1] if len(parts) > 1 else "")
            removed = self._doc.remove_page(name)
            if removed:
                self._save()
                self.success(f"Page removed: {name!r}")
            else:
                self.failure(f"Page not found: {name!r}")
        elif sub == "list":
            if self._doc is None:
                self.bullet("(no document)")
                return
            for i, page in enumerate(self._doc.pages):
                self.bullet(f"[{i}] {page.name!r}")
        else:
            print(Style.err(f"  Unknown page sub-command: {sub!r}"))

    def do_export(self, arg: str) -> None:
        """Export diagram. Usage: export --format png|svg|pdf --output PATH"""
        if self._doc is None:
            print(Style.err("  No document open."))
            return
        parts = self.parse_args(arg)
        fmt = "png"
        output = "diagram.png"
        it = iter(parts)
        for tok in it:
            if tok in ("--format", "-f"):
                fmt = next(it, "png")
            elif tok in ("--output", "-o"):
                output = next(it, "diagram.png")
        xml = render_xml(self._doc)
        from .backend import DrawioBackend

        be = DrawioBackend()
        try:
            out = be.convert_xml(xml, output, fmt=fmt)
            self.success(f"Exported to {out}")
        except Exception as exc:
            self.failure(str(exc))

    def do_new(self, arg: str) -> None:
        """Create a new document. Usage: new [--name NAME] [--page-name PAGE]"""
        parts = self.parse_args(arg)
        name = "Untitled"
        page_name = "Page-1"
        it = iter(parts)
        for tok in it:
            if tok == "--name":
                name = next(it, "Untitled")
            elif tok == "--page-name":
                page_name = next(it, "Page-1")
        from .project import DrawioDocument

        self._doc = DrawioDocument()
        self._doc.add_page(page_name)
        self._session.data["name"] = name
        self._save()
        self.success(f"Created document {name!r} with page {page_name!r}")

    def do_session(self, arg: str) -> None:
        """Session management. Usage: session show|list|delete"""
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "show"
        if sub == "show":
            self.section("Session info")
            self.bullet(f"name: {self._session.name}")
            self.bullet(f"harness: {self._session.harness}")
        elif sub == "list":
            sessions = DrawioSession.list_sessions()
            self.section("Sessions")
            for s in sessions:
                self.bullet(s)
        elif sub == "delete":
            self._session.delete()
            self.success("Session deleted")
        else:
            print(Style.err(f"  Unknown: {sub!r}"))
