"""Interactive REPL console for the LibreOffice harness."""

from __future__ import annotations

from ..shared import Console, Style
from .backend import LibreOfficeBackend, LibreOfficeError
from .session import LibreOfficeSession
from .core import writer as writer_mod
from .core import calc as calc_mod
from .core import impress as impress_mod


class LibreOfficeConsole(Console):
    """REPL console for driving LibreOffice via the headless CLI backend."""

    harness_name = "libreoffice"
    intro_extra = "Controls LibreOffice via headless subprocess."

    def __init__(
        self,
        session: LibreOfficeSession,
        backend: LibreOfficeBackend,
        **kwargs: object,
    ) -> None:
        super().__init__(session_name=session.name, **kwargs)
        self._session = session
        self._backend = backend

    # ------------------------------------------------------------------
    # do_status

    def do_status(self, _arg: str) -> None:
        """Display current session and document status."""
        self.section("Session")
        for key, val in self._session.status().items():
            self.bullet(f"{key}: {val}")

    # ------------------------------------------------------------------
    # do_convert

    def do_convert(self, arg: str) -> None:
        """Convert a document to a different format.

        Usage: convert <input_path> <output_format> [output_dir]
        """
        tokens = self.parse_args(arg)
        if len(tokens) < 2:
            print(Style.warn("  Usage: convert <input_path> <format> [output_dir]"))
            return
        src = tokens[0]
        fmt = tokens[1]
        out_dir = tokens[2] if len(tokens) > 2 else None
        try:
            result = self._backend.convert(src, fmt, out_dir)
            self.success(f"Converted → {result}")
        except (LibreOfficeError, FileNotFoundError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_writer

    def do_writer(self, arg: str) -> None:
        """Writer commands: create|heading|paragraph|table|wordcount.

        Usage: writer create <title>
               writer heading <level> <text>
               writer paragraph <text>
               writer wordcount
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: writer <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "create":
                title = " ".join(rest) if rest else "Untitled"
                doc_model = writer_mod.create_document(title)
                self.success(f"Writer document created: {title!r}")
                self._store_writer(doc_model)
            elif sub == "heading":
                level = int(rest[0])
                text = " ".join(rest[1:])
                doc_model = self._load_writer()
                writer_mod.set_heading(doc_model, level, text)
                self._store_writer(doc_model)
                self.success(f"Heading level {level}: {text!r}")
            elif sub == "paragraph":
                text = " ".join(rest)
                doc_model = self._load_writer()
                writer_mod.append_paragraph(doc_model, text)
                self._store_writer(doc_model)
                self.success(f"Paragraph appended")
            elif sub == "wordcount":
                doc_model = self._load_writer()
                count = writer_mod.get_word_count(doc_model)
                self.success(f"Word count: {count}")
            else:
                self.failure(f"Unknown writer subcommand: {sub!r}")
        except (IndexError, ValueError, RuntimeError) as exc:
            self.failure(str(exc))

    def _load_writer(self) -> writer_mod.WriterDocument:
        raw = self._session.data.get("writer")
        if raw is None:
            raise RuntimeError("No Writer document — use 'writer create' first")
        return writer_mod.WriterDocument(**raw)

    def _store_writer(self, doc: writer_mod.WriterDocument) -> None:
        self._session.data["writer"] = doc.to_dict()
        self._session.save()

    # ------------------------------------------------------------------
    # do_calc

    def do_calc(self, arg: str) -> None:
        """Calc commands: create|set|get|add-sheet|delete-sheet.

        Usage: calc create <name>
               calc set <sheet> <ref> <value>
               calc get <sheet> <ref>
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: calc <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "create":
                name = " ".join(rest) if rest else "Workbook"
                wb = calc_mod.create_spreadsheet(name)
                self._store_calc(wb)
                self.success(f"Spreadsheet created: {name!r}")
            elif sub == "set":
                wb = self._load_calc()
                calc_mod.set_cell(wb, rest[0], rest[1], rest[2])
                self._store_calc(wb)
                self.success(f"Set {rest[0]}!{rest[1]} = {rest[2]}")
            elif sub == "get":
                wb = self._load_calc()
                val = calc_mod.get_cell(wb, rest[0], rest[1])
                self.success(f"{rest[0]}!{rest[1]} = {val}")
            elif sub == "add-sheet":
                wb = self._load_calc()
                calc_mod.add_sheet(wb, rest[0])
                self._store_calc(wb)
                self.success(f"Sheet {rest[0]!r} added")
            elif sub == "delete-sheet":
                wb = self._load_calc()
                calc_mod.delete_sheet(wb, rest[0])
                self._store_calc(wb)
                self.success(f"Sheet {rest[0]!r} deleted")
            else:
                self.failure(f"Unknown calc subcommand: {sub!r}")
        except (IndexError, ValueError, KeyError, RuntimeError) as exc:
            self.failure(str(exc))

    def _load_calc(self) -> calc_mod.CalcSpreadsheet:
        raw = self._session.data.get("calc")
        if raw is None:
            raise RuntimeError("No Calc workbook — use 'calc create' first")
        wb = calc_mod.CalcSpreadsheet(name=raw["name"])
        for sd in raw.get("sheets", []):
            sheet = calc_mod.CalcSheet(name=sd["name"])
            for ref, cd in sd.get("cells", {}).items():
                sheet.cells[ref] = calc_mod.CalcCell(
                    value=cd.get("value"),
                    formula=cd.get("formula", ""),
                    number_format=cd.get("number_format", ""),
                )
            sheet.column_widths = sd.get("column_widths", {})
            wb.sheets.append(sheet)
        return wb

    def _store_calc(self, wb: calc_mod.CalcSpreadsheet) -> None:
        self._session.data["calc"] = wb.to_dict()
        self._session.save()

    # ------------------------------------------------------------------
    # do_impress

    def do_impress(self, arg: str) -> None:
        """Impress commands: create|add-slide|set-title|set-content|slide-count.

        Usage: impress create <title>
               impress add-slide [layout]
               impress set-title <idx> <title>
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: impress <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "create":
                title = " ".join(rest) if rest else "Untitled"
                pres = impress_mod.create_presentation(title)
                self._store_impress(pres)
                self.success(f"Presentation created: {title!r}")
            elif sub == "add-slide":
                pres = self._load_impress()
                layout = int(rest[0]) if rest else 1
                impress_mod.add_slide(pres, layout)
                self._store_impress(pres)
                self.success(f"Slide added (total: {impress_mod.get_slide_count(pres)})")
            elif sub == "set-title":
                pres = self._load_impress()
                impress_mod.set_slide_title(pres, int(rest[0]), " ".join(rest[1:]))
                self._store_impress(pres)
                self.success(f"Slide {rest[0]} title set")
            elif sub == "set-content":
                pres = self._load_impress()
                impress_mod.set_slide_content(pres, int(rest[0]), " ".join(rest[1:]))
                self._store_impress(pres)
                self.success(f"Slide {rest[0]} content set")
            elif sub == "slide-count":
                pres = self._load_impress()
                self.success(f"Slides: {impress_mod.get_slide_count(pres)}")
            else:
                self.failure(f"Unknown impress subcommand: {sub!r}")
        except (IndexError, ValueError, RuntimeError) as exc:
            self.failure(str(exc))

    def _load_impress(self) -> impress_mod.ImpressPresentation:
        raw = self._session.data.get("impress")
        if raw is None:
            raise RuntimeError("No presentation — use 'impress create' first")
        pres = impress_mod.ImpressPresentation(title=raw["title"])
        for sd in raw.get("slides", []):
            slide = impress_mod.ImpressSlide(
                index=sd["index"],
                title=sd.get("title", ""),
                content=sd.get("content", ""),
                layout=sd.get("layout", 1),
                background_color=sd.get("background_color", "#ffffff"),
            )
            pres.slides.append(slide)
        return pres

    def _store_impress(self, pres: impress_mod.ImpressPresentation) -> None:
        self._session.data["impress"] = pres.to_dict()
        self._session.save()
