"""Tests for the LibreOffice harness: project model, core modules, and backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sven_integrations.libreoffice.project import OfficeDocument, SheetInfo
from sven_integrations.libreoffice.backend import LibreOfficeBackend, LibreOfficeError
from sven_integrations.libreoffice.core import writer as writer_mod
from sven_integrations.libreoffice.core import calc as calc_mod
from sven_integrations.libreoffice.core import impress as impress_mod
from sven_integrations.libreoffice.core.export import (
    get_supported_formats,
    export_pdf,
    export_docx,
    export_xlsx,
)
from sven_integrations.libreoffice.core import document as doc_mod
from sven_integrations.libreoffice.core import styles as styles_mod
from sven_integrations.libreoffice.core.document import (
    DocumentProfile,
    DocumentSettings,
    DOCUMENT_PROFILES,
    create_document,
    get_document_info,
    list_profiles,
    set_document_property,
)
from sven_integrations.libreoffice.core.styles import (
    StyleDefinition,
    BUILT_IN_STYLES,
    ALLOWED_PROPERTIES,
    create_style,
    modify_style,
    remove_style,
    list_styles,
    get_style,
    apply_style,
)


# ---------------------------------------------------------------------------
# SheetInfo tests

class TestSheetInfo:
    def test_roundtrip(self) -> None:
        s = SheetInfo(index=0, name="Summary", visible=False, cells={"A1": 42})
        restored = SheetInfo.from_dict(s.to_dict())
        assert restored.name == "Summary"
        assert restored.visible is False
        assert restored.cells["A1"] == 42


# ---------------------------------------------------------------------------
# OfficeDocument tests

class TestOfficeDocument:
    def _make_doc(self) -> OfficeDocument:
        return OfficeDocument(doc_type="calc", title="Budget")

    def test_invalid_doc_type(self) -> None:
        with pytest.raises(ValueError, match="doc_type"):
            OfficeDocument(doc_type="unknown", title="X")

    def test_valid_types(self) -> None:
        for dt in ("writer", "calc", "impress", "draw"):
            doc = OfficeDocument(doc_type=dt, title="Doc")
            assert doc.doc_type == dt

    def test_add_sheet(self) -> None:
        doc = self._make_doc()
        doc.add_sheet(SheetInfo(index=0, name="Q1"))
        assert doc.sheet_count() == 1
        assert doc.modified is True

    def test_remove_sheet(self) -> None:
        doc = self._make_doc()
        doc.add_sheet(SheetInfo(index=0, name="Q1"))
        removed = doc.remove_sheet("Q1")
        assert removed.name == "Q1"
        assert doc.sheet_count() == 0

    def test_remove_missing_raises(self) -> None:
        doc = self._make_doc()
        with pytest.raises(KeyError):
            doc.remove_sheet("Ghost")

    def test_find_sheet(self) -> None:
        doc = self._make_doc()
        doc.add_sheet(SheetInfo(index=0, name="Data"))
        found = doc.find_sheet("Data")
        assert found is not None
        assert found.index == 0

    def test_find_missing_returns_none(self) -> None:
        doc = self._make_doc()
        assert doc.find_sheet("Nowhere") is None

    def test_roundtrip_empty(self) -> None:
        doc = self._make_doc()
        restored = OfficeDocument.from_dict(doc.to_dict())
        assert restored.title == "Budget"
        assert restored.doc_type == "calc"

    def test_roundtrip_with_sheets(self) -> None:
        doc = self._make_doc()
        doc.add_sheet(SheetInfo(index=0, name="Revenue"))
        restored = OfficeDocument.from_dict(doc.to_dict())
        assert len(restored.sheets_or_slides) == 1
        assert restored.sheets_or_slides[0].name == "Revenue"


# ---------------------------------------------------------------------------
# Writer core tests

class TestWriterCore:
    def test_create_document(self) -> None:
        doc = writer_mod.create_document("My Report", author="Alice")
        assert doc.title == "My Report"
        assert doc.author == "Alice"
        assert doc.paragraphs == []

    def test_append_paragraph(self) -> None:
        doc = writer_mod.create_document("Test")
        writer_mod.append_paragraph(doc, "Hello world")
        assert len(doc.paragraphs) == 1
        assert doc.paragraphs[0].text == "Hello world"

    def test_set_heading(self) -> None:
        doc = writer_mod.create_document("Test")
        writer_mod.set_heading(doc, 1, "Introduction")
        assert doc.paragraphs[0].style == "Heading 1"
        assert doc.paragraphs[0].heading_level == 1

    def test_heading_invalid_level(self) -> None:
        doc = writer_mod.create_document("Test")
        with pytest.raises(ValueError, match="level"):
            writer_mod.set_heading(doc, 7, "Too deep")

    def test_insert_table(self) -> None:
        doc = writer_mod.create_document("Test")
        writer_mod.insert_table(doc, 3, 4)
        assert len(doc.tables) == 1
        assert doc.tables[0].rows == 3
        assert doc.tables[0].cols == 4

    def test_insert_table_invalid_dims(self) -> None:
        doc = writer_mod.create_document("Test")
        with pytest.raises(ValueError):
            writer_mod.insert_table(doc, 0, 2)

    def test_set_page_size(self) -> None:
        doc = writer_mod.create_document("Test")
        writer_mod.set_page_size(doc, 297.0, 210.0, "landscape")
        assert doc.orientation == "landscape"
        assert doc.page_width_mm == 297.0

    def test_set_page_size_invalid_orientation(self) -> None:
        doc = writer_mod.create_document("Test")
        with pytest.raises(ValueError, match="orientation"):
            writer_mod.set_page_size(doc, 210.0, 297.0, "diagonal")

    def test_find_replace(self) -> None:
        doc = writer_mod.create_document("Test")
        writer_mod.append_paragraph(doc, "The quick brown fox")
        writer_mod.append_paragraph(doc, "Fox jumps over a fox")
        count = writer_mod.find_replace(doc, "fox", "cat", case_sensitive=False)
        assert count >= 2
        for para in doc.paragraphs:
            assert "fox" not in para.text.lower()

    def test_get_word_count(self) -> None:
        doc = writer_mod.create_document("Test")
        writer_mod.append_paragraph(doc, "one two three")
        writer_mod.append_paragraph(doc, "four five")
        assert writer_mod.get_word_count(doc) == 5


# ---------------------------------------------------------------------------
# Calc core tests

class TestCalcCore:
    def test_create_spreadsheet(self) -> None:
        wb = calc_mod.create_spreadsheet("Sales")
        assert wb.name == "Sales"
        assert len(wb.sheets) == 1
        assert wb.sheets[0].name == "Sheet1"

    def test_set_and_get_cell(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        calc_mod.set_cell(wb, "Sheet1", "B2", 99)
        val = calc_mod.get_cell(wb, "Sheet1", "B2")
        assert val == 99

    def test_get_missing_cell_returns_none(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        assert calc_mod.get_cell(wb, "Sheet1", "Z99") is None

    def test_set_formula(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        calc_mod.set_formula(wb, "Sheet1", "C1", "=SUM(A1:B1)")
        cell = wb.sheets[0].cells.get("C1")
        assert cell is not None
        assert cell.formula == "=SUM(A1:B1)"

    def test_add_sheet(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        calc_mod.add_sheet(wb, "Charts")
        assert len(wb.sheets) == 2

    def test_add_duplicate_sheet_raises(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        with pytest.raises(ValueError, match="already exists"):
            calc_mod.add_sheet(wb, "Sheet1")

    def test_delete_sheet(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        calc_mod.add_sheet(wb, "Temp")
        calc_mod.delete_sheet(wb, "Temp")
        assert len(wb.sheets) == 1

    def test_delete_missing_sheet_raises(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        with pytest.raises(KeyError):
            calc_mod.delete_sheet(wb, "Ghost")

    def test_set_column_width(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        calc_mod.set_column_width(wb, "Sheet1", "A", 20)
        assert wb.sheets[0].column_widths["A"] == 20

    def test_cell_case_insensitive_ref(self) -> None:
        wb = calc_mod.create_spreadsheet("Test")
        calc_mod.set_cell(wb, "Sheet1", "a1", "hello")
        assert calc_mod.get_cell(wb, "Sheet1", "A1") == "hello"


# ---------------------------------------------------------------------------
# Impress core tests

class TestImpressCore:
    def test_create_presentation(self) -> None:
        pres = impress_mod.create_presentation("Q4 Review")
        assert pres.title == "Q4 Review"
        assert impress_mod.get_slide_count(pres) == 1

    def test_add_slide(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.add_slide(pres, layout=2)
        assert impress_mod.get_slide_count(pres) == 2

    def test_set_slide_title(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.set_slide_title(pres, 0, "Agenda")
        assert pres.slides[0].title == "Agenda"

    def test_set_slide_content(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.set_slide_content(pres, 0, "Bullet 1\nBullet 2")
        assert "Bullet 1" in pres.slides[0].content

    def test_add_image(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.add_image(pres, 0, "/img/logo.png", 10, 10, 80, 60)
        assert len(pres.slides[0].images) == 1
        assert pres.slides[0].images[0].image_path == "/img/logo.png"

    def test_set_slide_background(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.set_slide_background(pres, 0, "#112233")
        assert pres.slides[0].background_color == "#112233"

    def test_duplicate_slide(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.set_slide_title(pres, 0, "Original")
        impress_mod.duplicate_slide(pres, 0)
        assert impress_mod.get_slide_count(pres) == 2
        assert pres.slides[1].title == "Original"

    def test_delete_slide(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.add_slide(pres, 1)
        impress_mod.set_slide_title(pres, 1, "Extra")
        impress_mod.delete_slide(pres, 1)
        assert impress_mod.get_slide_count(pres) == 1

    def test_invalid_slide_index(self) -> None:
        pres = impress_mod.create_presentation("Test")
        with pytest.raises(IndexError):
            impress_mod.set_slide_title(pres, 99, "Nope")

    def test_slide_indices_renumbered_after_delete(self) -> None:
        pres = impress_mod.create_presentation("Test")
        impress_mod.add_slide(pres, 1)
        impress_mod.add_slide(pres, 1)
        impress_mod.delete_slide(pres, 0)
        for i, s in enumerate(pres.slides):
            assert s.index == i


# ---------------------------------------------------------------------------
# Export helpers tests

class TestExportHelpers:
    def test_get_supported_formats_keys(self) -> None:
        fmt = get_supported_formats()
        assert "writer" in fmt
        assert "calc" in fmt
        assert "impress" in fmt
        assert "pdf" in fmt["writer"]

    def test_export_pdf_quality_validation(self) -> None:
        backend = MagicMock(spec=LibreOfficeBackend)
        with pytest.raises(ValueError, match="quality"):
            export_pdf(backend, "/in/doc.odt", "/out/doc.pdf", quality=0)

    def test_export_pdf_calls_backend(self) -> None:
        backend = MagicMock(spec=LibreOfficeBackend)
        backend.convert.return_value = Path("/out/doc.pdf")
        export_pdf(backend, "/in/doc.odt", "/out/doc.pdf", quality=90)
        backend.convert.assert_called_once()
        args = backend.convert.call_args[0]
        assert args[0] == "/in/doc.odt"
        assert args[1] == "pdf"

    def test_export_docx_calls_backend(self) -> None:
        backend = MagicMock(spec=LibreOfficeBackend)
        backend.convert.return_value = Path("/out/doc.docx")
        export_docx(backend, "/in/doc.odt", "/out/doc.docx")
        backend.convert.assert_called_once()
        assert backend.convert.call_args[0][1] == "docx"

    def test_export_xlsx_calls_backend(self) -> None:
        backend = MagicMock(spec=LibreOfficeBackend)
        backend.convert.return_value = Path("/out/sheet.xlsx")
        export_xlsx(backend, "/in/sheet.ods", "/out/sheet.xlsx")
        assert backend.convert.call_args[0][1] == "xlsx"


# ---------------------------------------------------------------------------
# Document core tests

class TestDocumentCore:
    def test_create_document_writer(self) -> None:
        doc = create_document("writer", "My Report", profile="a4")
        assert doc.doc_type == "writer"
        assert doc.title == "My Report"
        assert doc.extra["metadata"]["profile"] == "a4"

    def test_create_document_calc(self) -> None:
        doc = create_document("calc", "Sales", profile="letter")
        assert doc.doc_type == "calc"
        assert doc.extra["metadata"]["profile"] == "letter"

    def test_create_document_invalid_profile_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown profile"):
            create_document("writer", "X", profile="nonexistent")

    def test_create_document_with_settings(self) -> None:
        doc = create_document(
            "writer",
            "Report",
            profile="a4",
            settings={"author": "Alice", "language": "de-DE"},
        )
        assert doc.author == "Alice"
        assert doc.extra["metadata"]["language"] == "de-DE"

    def test_get_document_info_writer(self) -> None:
        doc = create_document("writer", "Doc", profile="a4")
        info = get_document_info(doc)
        assert info["type"] == "writer"
        assert info["name"] == "Doc"
        assert info["profile"] == "a4"
        assert "content_count" in info

    def test_get_document_info_calc(self) -> None:
        doc = create_document("calc", "Sheet", profile="letter")
        doc.add_sheet(SheetInfo(index=0, name="Q1"))
        info = get_document_info(doc)
        assert info["sheet_count"] == 1

    def test_list_profiles_returns_all(self) -> None:
        profiles = list_profiles()
        names = {p["name"] for p in profiles}
        assert {"a4", "a5", "letter", "legal", "presentation_4_3", "presentation_16_9", "b5"}.issubset(names)

    def test_list_profiles_have_dimensions(self) -> None:
        for p in list_profiles():
            assert p["width_mm"] > 0
            assert p["height_mm"] > 0

    def test_set_document_property_title(self) -> None:
        doc = create_document("writer", "Old Name")
        result = set_document_property(doc, "title", "New Name")
        assert result["key"] == "title"
        assert doc.title == "New Name"
        assert doc.modified is True

    def test_set_document_property_author(self) -> None:
        doc = create_document("writer", "Doc")
        set_document_property(doc, "author", "Bob")
        assert doc.author == "Bob"
        assert doc.extra["metadata"]["author"] == "Bob"

    def test_set_document_property_subject(self) -> None:
        doc = create_document("writer", "Doc")
        set_document_property(doc, "subject", "Annual Review")
        assert doc.extra["metadata"]["subject"] == "Annual Review"

    def test_set_document_property_invalid_key_raises(self) -> None:
        doc = create_document("writer", "Doc")
        with pytest.raises(ValueError, match="Unknown document property"):
            set_document_property(doc, "background_color", "#ffffff")

    def test_document_roundtrip_preserves_extra(self) -> None:
        doc = create_document("writer", "Test", profile="letter")
        set_document_property(doc, "subject", "Testing")
        raw = doc.to_dict()
        restored = OfficeDocument.from_dict(raw)
        assert restored.extra["metadata"]["subject"] == "Testing"
        assert restored.extra["metadata"]["profile"] == "letter"


# ---------------------------------------------------------------------------
# Styles core tests

def _make_writer_doc() -> OfficeDocument:
    return create_document("writer", "Style Test", profile="a4")


class TestStylesCore:
    def test_create_style_basic(self) -> None:
        doc = _make_writer_doc()
        result = create_style(doc, "My Heading", family="paragraph")
        assert result["action"] == "create_style"
        assert result["style"]["name"] == "My Heading"
        assert doc.modified is True

    def test_create_style_with_properties(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Bold Body", properties={"font-weight": "bold", "font-size": "12pt"})
        result = get_style(doc, "Bold Body")
        assert result["style"]["properties"]["font-weight"] == "bold"
        assert result["style"]["properties"]["font-size"] == "12pt"

    def test_create_style_filters_unknown_properties(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Filtered", properties={"font-size": "10pt", "border-radius": "5px"})
        result = get_style(doc, "Filtered")
        assert "border-radius" not in result["style"]["properties"]
        assert "font-size" in result["style"]["properties"]

    def test_create_style_duplicate_raises(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Custom")
        with pytest.raises(ValueError, match="already exists"):
            create_style(doc, "Custom")

    def test_create_style_invalid_family_raises(self) -> None:
        doc = _make_writer_doc()
        with pytest.raises(ValueError, match="Invalid style family"):
            create_style(doc, "X", family="unknown")

    def test_modify_style_updates_properties(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Body Alt", properties={"font-size": "11pt"})
        result = modify_style(doc, "Body Alt", properties={"font-size": "13pt", "color": "#333333"})
        assert result["style"]["properties"]["font-size"] == "13pt"
        assert result["style"]["properties"]["color"] == "#333333"

    def test_modify_style_missing_raises(self) -> None:
        doc = _make_writer_doc()
        with pytest.raises(KeyError):
            modify_style(doc, "Ghost Style", properties={})

    def test_remove_style(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Temp Style")
        result = remove_style(doc, "Temp Style")
        assert result["action"] == "remove_style"
        with pytest.raises(KeyError):
            get_style(doc, "Temp Style")

    def test_remove_builtin_style_raises(self) -> None:
        doc = _make_writer_doc()
        with pytest.raises(ValueError, match="built-in"):
            remove_style(doc, "Heading 1")

    def test_remove_missing_style_raises(self) -> None:
        doc = _make_writer_doc()
        with pytest.raises(KeyError):
            remove_style(doc, "Does Not Exist")

    def test_list_styles_empty(self) -> None:
        doc = _make_writer_doc()
        result = list_styles(doc)
        assert result["count"] == 0
        assert result["styles"] == []

    def test_list_styles_populated(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "S1")
        create_style(doc, "S2", family="character")
        result = list_styles(doc)
        assert result["count"] == 2
        names = {s["name"] for s in result["styles"]}
        assert {"S1", "S2"} == names

    def test_get_style(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Code Block", family="paragraph", properties={"font-name": "Monospace"})
        result = get_style(doc, "Code Block")
        assert result["style"]["family"] == "paragraph"
        assert result["style"]["properties"]["font-name"] == "Monospace"

    def test_get_style_missing_raises(self) -> None:
        doc = _make_writer_doc()
        with pytest.raises(KeyError):
            get_style(doc, "Missing")

    def test_apply_style_custom(self) -> None:
        doc = _make_writer_doc()
        create_style(doc, "Fancy")
        result = apply_style(doc, "Fancy", content_index=2)
        assert result["action"] == "apply_style"
        assert result["content_index"] == 2
        assert doc.extra["applied_styles"]["2"] == "Fancy"

    def test_apply_style_builtin(self) -> None:
        doc = _make_writer_doc()
        result = apply_style(doc, "Heading 1", content_index=0)
        assert doc.extra["applied_styles"]["0"] == "Heading 1"

    def test_apply_style_missing_raises(self) -> None:
        doc = _make_writer_doc()
        with pytest.raises(KeyError):
            apply_style(doc, "Unknown Style", content_index=0)

    def test_style_definition_roundtrip(self) -> None:
        sd = StyleDefinition(
            name="My Style",
            family="character",
            parent_name="Default Paragraph Style",
            properties={"font-size": "10pt"},
        )
        restored = StyleDefinition.from_dict(sd.to_dict())
        assert restored.name == "My Style"
        assert restored.family == "character"
        assert restored.parent_name == "Default Paragraph Style"
        assert restored.properties["font-size"] == "10pt"

    def test_allowed_properties_contains_expected_keys(self) -> None:
        required = {"font-name", "font-size", "font-weight", "color", "text-align"}
        assert required.issubset(ALLOWED_PROPERTIES)

    def test_built_in_styles_not_empty(self) -> None:
        assert len(BUILT_IN_STYLES) >= 7
        assert "Heading 1" in BUILT_IN_STYLES
        assert "Body Text" in BUILT_IN_STYLES


# ---------------------------------------------------------------------------
# Backend unit tests

class TestLibreOfficeBackend:
    def test_convert_missing_file_raises(self, tmp_path: Path) -> None:
        backend = LibreOfficeBackend.__new__(LibreOfficeBackend)
        backend._binary = "libreoffice"
        backend._timeout = 30
        with pytest.raises(FileNotFoundError):
            backend.convert(str(tmp_path / "nonexistent.odt"), "pdf")

    def test_run_raises_on_nonzero_exit(self) -> None:
        import subprocess
        backend = LibreOfficeBackend.__new__(LibreOfficeBackend)
        backend._binary = "false"
        backend._timeout = 10
        with pytest.raises(LibreOfficeError):
            backend._run(["false"])
