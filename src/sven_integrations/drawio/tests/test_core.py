"""Tests for the draw.io harness core functionality."""

from __future__ import annotations

import pytest

from sven_integrations.drawio.drawio_xml import (
    add_connector,
    add_shape,
    new_diagram,
    parse_diagram,
    remove_cell,
    render_xml,
    update_cell_label,
    update_cell_style,
)
from sven_integrations.drawio.project import (
    CellGeometry,
    DrawioCell,
    DrawioDocument,
    DrawioPage,
)

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestCellGeometry:
    def test_defaults(self) -> None:
        g = CellGeometry()
        assert g.x == 0.0
        assert g.width == 120.0

    def test_roundtrip(self) -> None:
        g = CellGeometry(x=10, y=20, width=200, height=100)
        assert CellGeometry.from_dict(g.to_dict()) == g


class TestDrawioCell:
    def test_vertex_defaults(self) -> None:
        c = DrawioCell(cell_id="c1", value="Hello")
        assert c.vertex is True
        assert c.edge is False
        assert c.source_id is None

    def test_roundtrip(self) -> None:
        c = DrawioCell(
            cell_id="e1",
            value="Edge",
            style="edgeStyle=orthogonal;",
            vertex=False,
            edge=True,
            source_id="s",
            target_id="t",
            geometry=CellGeometry(x=0, y=0, width=0, height=0),
        )
        assert DrawioCell.from_dict(c.to_dict()) == c


class TestDrawioPage:
    def test_roundtrip(self) -> None:
        page = DrawioPage(page_id="p1", name="Main")
        page.cells.append(DrawioCell(cell_id="c1", value="Box"))
        assert DrawioPage.from_dict(page.to_dict()) == page


class TestDrawioDocument:
    def test_add_page(self) -> None:
        doc = DrawioDocument()
        page = doc.add_page("Diagram 1")
        assert len(doc.pages) == 1
        assert page.name == "Diagram 1"

    def test_remove_page(self) -> None:
        doc = DrawioDocument()
        doc.add_page("First")
        doc.add_page("Second")
        removed = doc.remove_page("First")
        assert removed is True
        assert len(doc.pages) == 1
        assert doc.pages[0].name == "Second"

    def test_remove_nonexistent_page(self) -> None:
        doc = DrawioDocument()
        assert doc.remove_page("Ghost") is False

    def test_add_cell(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        cell = DrawioCell(cell_id="c99", value="Node")
        doc.add_cell(0, cell)
        assert len(doc.pages[0].cells) == 1

    def test_find_cell(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        doc.add_cell(0, DrawioCell(cell_id="abc", value="Found"))
        assert doc.find_cell("abc") is not None
        assert doc.find_cell("missing") is None

    def test_roundtrip(self) -> None:
        doc = DrawioDocument(file_path="/tmp/test.drawio")
        pg = doc.add_page("Page 1")
        pg.cells.append(DrawioCell(cell_id="v1", value="Vertex"))
        restored = DrawioDocument.from_dict(doc.to_dict())
        assert restored.file_path == doc.file_path
        assert len(restored.pages) == 1
        assert restored.pages[0].cells[0].value == "Vertex"


# ---------------------------------------------------------------------------
# XML generation / parsing tests
# ---------------------------------------------------------------------------


class TestNewDiagram:
    def test_returns_valid_xml(self) -> None:
        xml = new_diagram("Test Page")
        assert "<mxGraphModel" in xml
        assert "Test Page" in xml

    def test_is_parseable_by_parse_diagram(self) -> None:
        xml = new_diagram("My Diagram")
        doc = parse_diagram(xml)
        assert len(doc.pages) == 1
        assert doc.pages[0].name == "My Diagram"


class TestRenderXml:
    def test_outputs_mxfile_format(self) -> None:
        """Saved files must use mxfile root so Draw.io can open them."""
        doc = DrawioDocument()
        doc.add_page("P")
        add_shape(doc, 0, "rectangle", "A", 0, 0, 100, 60)
        xml = render_xml(doc)
        assert xml.strip().startswith("<mxfile ")
        assert 'compressed="false"' in xml
        assert "<diagram " in xml
        assert "<mxGraphModel " in xml


class TestParseRenderRoundtrip:
    def test_roundtrip_preserves_cells(self) -> None:
        doc = DrawioDocument()
        doc.add_page("Round")
        cid = add_shape(doc, 0, "rectangle", "A", 10, 20, 100, 50)
        xml = render_xml(doc)
        assert cid in xml
        doc2 = parse_diagram(xml)
        assert len(doc2.pages) == 1
        cell = next((c for c in doc2.pages[0].cells if c.cell_id == cid), None)
        assert cell is not None
        assert cell.value == "A"

    def test_roundtrip_preserves_edges(self) -> None:
        doc = DrawioDocument()
        doc.add_page("E")
        src = add_shape(doc, 0, "rectangle", "S", 0, 0, 100, 60)
        tgt = add_shape(doc, 0, "rectangle", "T", 200, 0, 100, 60)
        eid = add_connector(doc, 0, src, tgt, "link")
        xml = render_xml(doc)
        doc2 = parse_diagram(xml)
        edge = next((c for c in doc2.pages[0].cells if c.cell_id == eid), None)
        assert edge is not None
        assert edge.edge is True
        assert edge.source_id == src
        assert edge.target_id == tgt


# ---------------------------------------------------------------------------
# add_shape / add_connector tests
# ---------------------------------------------------------------------------


class TestAddShape:
    def test_creates_vertex(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        cid = add_shape(doc, 0, "ellipse", "Circle", 50, 50, 80, 80)
        cell = doc.find_cell(cid)
        assert cell is not None
        assert cell.vertex is True
        assert "ellipse" in cell.style

    def test_invalid_page_idx(self) -> None:
        doc = DrawioDocument()
        with pytest.raises(IndexError):
            add_shape(doc, 5, "rectangle", "X", 0, 0, 100, 60)

    def test_style_overrides(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        cid = add_shape(doc, 0, "rectangle", "R", 0, 0, 100, 60, style_overrides={"fillColor": "#ff0000"})
        cell = doc.find_cell(cid)
        assert cell is not None
        assert "fillColor=#ff0000" in cell.style


class TestAddConnector:
    def test_creates_edge(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        s = add_shape(doc, 0, "rectangle", "S", 0, 0, 100, 60)
        t = add_shape(doc, 0, "rectangle", "T", 200, 0, 100, 60)
        eid = add_connector(doc, 0, s, t)
        cell = doc.find_cell(eid)
        assert cell is not None
        assert cell.edge is True
        assert cell.source_id == s
        assert cell.target_id == t


class TestRemoveCell:
    def test_removes_existing(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        cid = add_shape(doc, 0, "rectangle", "X", 0, 0, 100, 60)
        assert remove_cell(doc, 0, cid) is True
        assert doc.find_cell(cid) is None

    def test_returns_false_for_missing(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        assert remove_cell(doc, 0, "nonexistent") is False


class TestUpdateCellLabel:
    def test_updates_value(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        cid = add_shape(doc, 0, "rectangle", "Old", 0, 0, 100, 60)
        ok = update_cell_label(doc, 0, cid, "New")
        assert ok is True
        assert doc.find_cell(cid).value == "New"


class TestUpdateCellStyle:
    def test_merges_styles(self) -> None:
        doc = DrawioDocument()
        doc.add_page("P")
        cid = add_shape(doc, 0, "rectangle", "R", 0, 0, 100, 60)
        ok = update_cell_style(doc, 0, cid, {"fillColor": "#0000ff", "fontColor": "#ffffff"})
        assert ok is True
        cell = doc.find_cell(cid)
        assert "fillColor=#0000ff" in cell.style
        assert "fontColor=#ffffff" in cell.style


# ---------------------------------------------------------------------------
# Backend export command building test (no actual subprocess)
# ---------------------------------------------------------------------------


class TestDrawioBackend:
    def test_validate_xml_valid(self) -> None:
        from sven_integrations.drawio.backend import DrawioBackend

        be = DrawioBackend()
        doc = DrawioDocument()
        doc.add_page("P")
        add_shape(doc, 0, "rectangle", "A", 0, 0, 100, 60)
        xml = render_xml(doc)
        assert be.validate_xml(xml) is True

    def test_validate_xml_invalid(self) -> None:
        from sven_integrations.drawio.backend import DrawioBackend

        be = DrawioBackend()
        assert be.validate_xml("<not valid xml <<<") is False

    def test_get_diagram_info(self, tmp_path) -> None:
        from sven_integrations.drawio.backend import DrawioBackend

        doc = DrawioDocument()
        doc.add_page("Info Page")
        add_shape(doc, 0, "rectangle", "Node", 0, 0, 100, 60)
        xml = render_xml(doc)
        fpath = tmp_path / "test.drawio"
        fpath.write_text(xml)
        be = DrawioBackend()
        info = be.get_diagram_info(str(fpath))
        assert info["total_pages"] == 1
        assert info["pages"][0]["name"] == "Info Page"
        assert info["total_cells"] == 1
