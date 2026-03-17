"""pytest tests for the Inkscape harness.

Tests cover:
- InkscapeProject / SvgElement data model and serialisation
- InkscapeSession persistence via tmp_path
- Element manipulation action building
- Text action building
- Export action building
- Document creation, info, and canvas sizing
- Shape creation and listing (rect, circle, ellipse, line, polygon, path, star)
- Style parse/render and property mutations
- Transform parse/serialize and element mutations
- Layer CRUD (add, remove, move, reorder)
- Path boolean ops and shape_to_path_data
- Gradient add, list, apply

No real Inkscape binary is required.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sven_integrations.inkscape.backend import InkscapeBackend, InkscapeError
from sven_integrations.inkscape.core import document as doc_ops
from sven_integrations.inkscape.core import elements as elem_ops
from sven_integrations.inkscape.core import gradients as gradient_ops
from sven_integrations.inkscape.core import layers as layer_ops
from sven_integrations.inkscape.core import paths as path_ops
from sven_integrations.inkscape.core import shapes as shape_ops
from sven_integrations.inkscape.core import styles as style_ops
from sven_integrations.inkscape.core import text as text_ops
from sven_integrations.inkscape.core import transforms as transform_ops
from sven_integrations.inkscape.core.export import (
    ExportError,
    build_actions,
    export_area,
    export_emf,
    export_eps,
    export_pdf,
    export_png,
)
from sven_integrations.inkscape.project import InkscapeProject, SvgElement
from sven_integrations.inkscape.session import InkscapeSession

# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture()
def sample_element() -> SvgElement:
    return SvgElement(
        element_id="rect1",
        tag="rect",
        label="Blue box",
        stroke="#000000",
        fill="#0000ff",
        transform="translate(10,20)",
    )


@pytest.fixture()
def blank_project() -> InkscapeProject:
    return InkscapeProject(
        svg_path="/tmp/drawing.svg",
        width_mm=210.0,
        height_mm=297.0,
    )


@pytest.fixture()
def inkscape_session(tmp_path: Path) -> InkscapeSession:
    os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
    sess = InkscapeSession("test-inkscape")
    yield sess
    os.environ.pop("SVEN_INTEGRATIONS_STATE_DIR", None)


@pytest.fixture()
def project_with_rect() -> InkscapeProject:
    """Project with a single rect element added via shape_ops."""
    proj = InkscapeProject(width_mm=100.0, height_mm=100.0)
    shape_ops.add_rect(proj, 10, 20, 50, 30, name="box", fill="red", stroke="blue")
    return proj


# ---------------------------------------------------------------------------
# SvgElement tests


class TestSvgElement:
    def test_defaults(self) -> None:
        elem = SvgElement(element_id="g1")
        assert elem.tag == "g"
        assert elem.fill == "#000000"
        assert elem.stroke == "none"
        assert elem.transform == ""
        assert elem.style == ""
        assert elem.attrs == {}

    def test_round_trip(self, sample_element: SvgElement) -> None:
        restored = SvgElement.from_dict(sample_element.to_dict())
        assert restored.element_id == "rect1"
        assert restored.fill == "#0000ff"
        assert restored.tag == "rect"
        assert restored.label == "Blue box"

    def test_from_dict_partial(self) -> None:
        elem = SvgElement.from_dict({"element_id": "path42"})
        assert elem.tag == "g"
        assert elem.stroke == "none"

    def test_to_dict_has_all_keys(self, sample_element: SvgElement) -> None:
        d = sample_element.to_dict()
        assert set(d.keys()) == {
            "element_id", "tag", "label", "stroke", "fill", "transform", "style", "attrs"
        }

    def test_style_field_persists(self) -> None:
        elem = SvgElement(element_id="e1", style="fill:red;stroke:blue")
        restored = SvgElement.from_dict(elem.to_dict())
        assert restored.style == "fill:red;stroke:blue"

    def test_attrs_field_persists(self) -> None:
        elem = SvgElement(element_id="e2", attrs={"cx": 50, "cy": 60, "r": 20})
        restored = SvgElement.from_dict(elem.to_dict())
        assert restored.attrs["r"] == 20


# ---------------------------------------------------------------------------
# InkscapeProject tests


class TestInkscapeProject:
    def test_initial_state(self, blank_project: InkscapeProject) -> None:
        assert blank_project.width_mm == 210.0
        assert blank_project.height_mm == 297.0
        assert blank_project.elements == []
        assert blank_project.svg_path == "/tmp/drawing.svg"

    def test_data_field_default(self, blank_project: InkscapeProject) -> None:
        assert isinstance(blank_project.data, dict)

    def test_add_element(
        self, blank_project: InkscapeProject, sample_element: SvgElement
    ) -> None:
        blank_project.add_element(sample_element)
        assert len(blank_project.elements) == 1

    def test_remove_element_found(
        self, blank_project: InkscapeProject, sample_element: SvgElement
    ) -> None:
        blank_project.add_element(sample_element)
        removed = blank_project.remove_element("rect1")
        assert removed is True
        assert blank_project.elements == []

    def test_remove_element_missing(self, blank_project: InkscapeProject) -> None:
        removed = blank_project.remove_element("ghost99")
        assert removed is False

    def test_find_by_id(
        self, blank_project: InkscapeProject, sample_element: SvgElement
    ) -> None:
        blank_project.add_element(sample_element)
        found = blank_project.find_by_id("rect1")
        assert found is sample_element
        assert blank_project.find_by_id("nope") is None

    def test_round_trip(
        self, blank_project: InkscapeProject, sample_element: SvgElement
    ) -> None:
        blank_project.add_element(sample_element)
        blank_project.data["custom"] = "hello"
        restored = InkscapeProject.from_dict(blank_project.to_dict())
        assert restored.svg_path == "/tmp/drawing.svg"
        assert len(restored.elements) == 1
        assert restored.elements[0].element_id == "rect1"
        assert restored.data.get("custom") == "hello"

    def test_viewbox_serialisation(self) -> None:
        proj = InkscapeProject(viewbox=(5.0, 10.0, 200.0, 280.0))
        restored = InkscapeProject.from_dict(proj.to_dict())
        assert restored.viewbox == (5.0, 10.0, 200.0, 280.0)

    def test_from_dict_defaults(self) -> None:
        proj = InkscapeProject.from_dict({})
        assert proj.width_mm == 210.0
        assert proj.viewbox == (0.0, 0.0, 210.0, 297.0)


# ---------------------------------------------------------------------------
# InkscapeSession tests


class TestInkscapeSession:
    def test_project_none_initially(self, inkscape_session: InkscapeSession) -> None:
        assert inkscape_session.project is None

    def test_open_document(self, inkscape_session: InkscapeSession) -> None:
        proj = inkscape_session.open_document("/docs/logo.svg", 100, 100)
        assert proj.svg_path == "/docs/logo.svg"
        assert proj.width_mm == 100.0

    def test_project_setter_and_getter(
        self, inkscape_session: InkscapeSession, blank_project: InkscapeProject
    ) -> None:
        inkscape_session.project = blank_project
        retrieved = inkscape_session.project
        assert retrieved is not None
        assert retrieved.width_mm == 210.0

    def test_save_and_reload(
        self, inkscape_session: InkscapeSession, blank_project: InkscapeProject
    ) -> None:
        inkscape_session.project = blank_project
        inkscape_session.save()
        fresh = InkscapeSession("test-inkscape")
        fresh.load()
        assert fresh.project is not None
        assert fresh.project.svg_path == "/tmp/drawing.svg"

    def test_close_clears_project(
        self, inkscape_session: InkscapeSession, blank_project: InkscapeProject
    ) -> None:
        inkscape_session.project = blank_project
        inkscape_session.close()
        assert inkscape_session.project is None

    def test_list_sessions(self, tmp_path: Path) -> None:
        os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
        for name in ("logo", "poster", "icon"):
            s = InkscapeSession(name)
            s.save()
        assert set(InkscapeSession.list_sessions()) == {"logo", "poster", "icon"}
        os.environ.pop("SVEN_INTEGRATIONS_STATE_DIR", None)


# ---------------------------------------------------------------------------
# InkscapeBackend tests


class TestInkscapeBackend:
    def test_run_actions_raises_on_nonzero(self) -> None:
        backend = InkscapeBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
            with pytest.raises(InkscapeError, match="Inkscape exited 1"):
                backend.run_actions("/tmp/x.svg", ["export-do"])

    def test_run_actions_builds_correct_cmd(self) -> None:
        backend = InkscapeBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            backend.run_actions("/tmp/x.svg", ["select-all", "export-do"])
            cmd = mock_run.call_args[0][0]
            assert "inkscape" in cmd[0]
            assert "/tmp/x.svg" in cmd
            assert "--actions=select-all;export-do" in cmd


# ---------------------------------------------------------------------------
# Element operation tests


class TestElementOps:
    def test_move_element(self) -> None:
        result = elem_ops.move_element("rect1", 10.0, 20.0)
        assert result["element_id"] == "rect1"
        assert "transform-translate:10.0,20.0" in result["actions"]

    def test_scale_element(self) -> None:
        result = elem_ops.scale_element("circle2", 2.0, 0.5)
        assert "transform-scale:2.0,0.5" in result["actions"]

    def test_rotate_element(self) -> None:
        result = elem_ops.rotate_element("path3", 45.0, 100.0, 100.0)
        assert "transform-rotate:45.0,100.0,100.0" in result["actions"]

    def test_set_fill(self) -> None:
        result = elem_ops.set_fill("rect1", "#ff0000")
        assert any("fill" in a and "#ff0000" in a for a in result["actions"])

    def test_set_stroke(self) -> None:
        result = elem_ops.set_stroke("rect1", "#000000", 2.0)
        assert any("stroke-width" in a and "2.0" in a for a in result["actions"])

    def test_duplicate_element(self) -> None:
        result = elem_ops.duplicate_element("g5")
        assert "edit-duplicate" in result["actions"]

    def test_delete_element(self) -> None:
        result = elem_ops.delete_element("text1")
        assert "edit-delete" in result["actions"]
        assert "select-by-id:text1" in result["actions"]

    def test_group_elements(self) -> None:
        result = elem_ops.group_elements(["r1", "r2", "r3"], "my-group")
        assert "object-group" in result["actions"]
        assert any("my-group" in a for a in result["actions"])

    def test_group_elements_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="not be empty"):
            elem_ops.group_elements([], "g1")

    def test_select_element(self) -> None:
        result = elem_ops.select_element("logo")
        assert result["actions"] == ["select-by-id:logo"]


# ---------------------------------------------------------------------------
# Text operation tests


class TestTextOps:
    def test_add_text(self) -> None:
        result = text_ops.add_text(10, 20, "Hello", "serif", 16.0, "#333333")
        assert result["action"] == "add_text"
        assert result["x"] == 10
        assert result["content"] == "Hello"
        assert any("font-family" in a for a in result["actions"])

    def test_edit_text(self) -> None:
        result = text_ops.edit_text("t1", "Updated content")
        assert "Updated content" in " ".join(result["actions"])

    def test_set_font(self) -> None:
        result = text_ops.set_font("t2", "Georgia", 18.0, "bold")
        stmts = " ".join(result["actions"])
        assert "Georgia" in stmts
        assert "bold" in stmts
        assert "18.0px" in stmts

    def test_convert_text_to_path(self) -> None:
        result = text_ops.convert_text_to_path("headline")
        assert "object-to-path" in result["actions"]
        assert "select-by-id:headline" in result["actions"]

    def test_flow_text_in_frame(self) -> None:
        result = text_ops.flow_text_in_frame("frame1", "Body copy here.")
        assert "text-flow-into-frame" in " ".join(result["actions"])


# ---------------------------------------------------------------------------
# Export action building tests


class TestExportActions:
    def test_build_actions_png(self) -> None:
        actions = build_actions("png", "/out/image.png", dpi=150.0)
        assert "export-type:png" in actions
        assert "export-dpi:150.0" in actions
        assert "export-filename:/out/image.png" in actions
        assert "export-do" in actions

    def test_build_actions_pdf(self) -> None:
        actions = build_actions("pdf", "/out/doc.pdf")
        assert "export-type:pdf" in actions
        assert "export-do" in actions

    def test_build_actions_eps(self) -> None:
        actions = build_actions("eps", "/out/art.eps")
        assert "export-type:eps" in actions

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(ExportError, match="Unsupported format"):
            build_actions("bmp", "/out/image.bmp")

    def test_png_area_drawing(self) -> None:
        actions = build_actions("png", "/out/draw.png", area="drawing")
        assert "export-area-drawing" in actions

    def test_png_area_selection(self) -> None:
        actions = build_actions("png", "/out/sel.png", area="selection")
        assert "export-area-snap-to-drawing" in actions

    def test_export_png_result_structure(self) -> None:
        result = export_png("/in/doc.svg", "/out/img.png", dpi=300, area="page")
        assert result["action"] == "export_png"
        assert result["dpi"] == 300
        assert isinstance(result["actions"], list)

    def test_export_pdf_result_structure(self) -> None:
        result = export_pdf("/in/doc.svg", "/out/doc.pdf")
        assert result["action"] == "export_pdf"

    def test_export_eps_result_structure(self) -> None:
        result = export_eps("/in/doc.svg", "/out/art.eps")
        assert result["action"] == "export_eps"

    def test_export_emf_result_structure(self) -> None:
        result = export_emf("/in/doc.svg", "/out/art.emf")
        assert result["action"] == "export_emf"

    def test_export_area_builds_rect_action(self) -> None:
        result = export_area("/in/doc.svg", "/out/crop.png", 0, 0, 100, 100)
        assert any("0,0,100,100" in a for a in result["actions"])


# ---------------------------------------------------------------------------
# Document tests


class TestDocumentOps:
    def test_new_document_creates_project(self) -> None:
        proj = doc_ops.new_document("Test", 200.0, 150.0)
        assert isinstance(proj, InkscapeProject)
        assert proj.width_mm == 200.0
        assert proj.height_mm == 150.0
        assert proj.data["name"] == "Test"

    def test_new_document_viewbox_matches(self) -> None:
        proj = doc_ops.new_document("VB", 300.0, 200.0)
        assert proj.viewbox == (0.0, 0.0, 300.0, 200.0)

    def test_new_document_background_stored(self) -> None:
        proj = doc_ops.new_document("BG", 100, 100, background="transparent")
        assert proj.data["background"] == "transparent"

    def test_get_document_info_keys(self, blank_project: InkscapeProject) -> None:
        info = doc_ops.get_document_info(blank_project)
        assert set(info.keys()) == {
            "name", "width_mm", "height_mm", "viewbox", "element_count", "page_layer_count"
        }

    def test_get_document_info_element_count(self, project_with_rect: InkscapeProject) -> None:
        info = doc_ops.get_document_info(project_with_rect)
        assert info["element_count"] == 1

    def test_set_canvas_size(self, blank_project: InkscapeProject) -> None:
        result = doc_ops.set_canvas_size(blank_project, 100.0, 50.0)
        assert blank_project.width_mm == 100.0
        assert blank_project.height_mm == 50.0
        assert result["viewbox"][2] == 100.0
        assert result["viewbox"][3] == 50.0

    def test_list_profiles_returns_ten(self) -> None:
        profiles = doc_ops.list_profiles()
        assert len(profiles) >= 10
        keys = {p["key"] for p in profiles}
        assert "a4_portrait" in keys
        assert "icon_256" in keys

    def test_save_svg_creates_file(self, tmp_path: Path) -> None:
        proj = doc_ops.new_document("SaveTest", 100, 100)
        shape_ops.add_rect(proj, 10, 10, 50, 50, fill="red")
        out = str(tmp_path / "out.svg")
        result = doc_ops.save_svg(proj, out)
        assert result["ok"] is True
        assert Path(out).exists()
        content = Path(out).read_text()
        assert "<svg" in content
        assert "rect" in content

    def test_document_profile_a4(self) -> None:
        p = doc_ops.DOCUMENT_PROFILES["a4_portrait"]
        assert p.width_mm == 210.0
        assert p.height_mm == 297.0


# ---------------------------------------------------------------------------
# Shape tests


class TestShapeOps:
    def test_add_rect_returns_element(self) -> None:
        proj = InkscapeProject()
        result = shape_ops.add_rect(proj, 0, 0, 100, 50)
        assert result["action"] == "add_shape"
        assert result["tag"] == "rect"
        assert len(proj.elements) == 1

    def test_add_rect_attrs(self) -> None:
        proj = InkscapeProject()
        shape_ops.add_rect(proj, 5, 10, 80, 40, rx=5, name="mybox", fill="green")
        elem = proj.elements[0]
        assert elem.attrs["x"] == 5
        assert elem.attrs["width"] == 80
        assert elem.attrs["rx"] == 5
        assert elem.fill == "green"

    def test_add_circle(self) -> None:
        proj = InkscapeProject()
        result = shape_ops.add_circle(proj, 50, 50, 25)
        assert result["tag"] == "circle"
        assert proj.elements[0].attrs["r"] == 25

    def test_add_ellipse(self) -> None:
        proj = InkscapeProject()
        result = shape_ops.add_ellipse(proj, 60, 60, 30, 15)
        assert result["tag"] == "ellipse"
        elem = proj.elements[0]
        assert elem.attrs["rx"] == 30
        assert elem.attrs["ry"] == 15

    def test_add_line(self) -> None:
        proj = InkscapeProject()
        result = shape_ops.add_line(proj, 0, 0, 100, 100)
        assert result["tag"] == "line"

    def test_add_polygon(self) -> None:
        proj = InkscapeProject()
        pts = [(0, 0), (50, 100), (100, 0)]
        result = shape_ops.add_polygon(proj, pts)
        assert result["tag"] == "polygon"
        assert "points" in proj.elements[0].attrs

    def test_add_path(self) -> None:
        proj = InkscapeProject()
        d = "M0,0 L100,0 L100,100 Z"
        result = shape_ops.add_path(proj, d)
        assert result["tag"] == "path"
        assert proj.elements[0].attrs["d"] == d

    def test_add_star_five_points(self) -> None:
        proj = InkscapeProject()
        result = shape_ops.add_star(proj, 50, 50, 5, 40, 20)
        assert result["tag"] == "path"
        d = proj.elements[0].attrs["d"]
        assert d.startswith("M")
        assert d.endswith("Z")
        # 10 vertices + Z
        assert d.count("L") == 9

    def test_add_star_requires_three_points(self) -> None:
        proj = InkscapeProject()
        with pytest.raises(ValueError, match="at least 3"):
            shape_ops.add_star(proj, 0, 0, 2, 10, 5)

    def test_list_objects(self) -> None:
        proj = InkscapeProject()
        shape_ops.add_rect(proj, 0, 0, 10, 10)
        shape_ops.add_circle(proj, 5, 5, 5)
        objects = shape_ops.list_objects(proj)
        assert len(objects) == 2
        tags = {o["tag"] for o in objects}
        assert "rect" in tags
        assert "circle" in tags

    def test_unique_element_ids(self) -> None:
        proj = InkscapeProject()
        for _ in range(5):
            shape_ops.add_rect(proj, 0, 0, 10, 10)
        ids = [e.element_id for e in proj.elements]
        assert len(set(ids)) == 5

    def test_style_string_set_on_shape(self) -> None:
        proj = InkscapeProject()
        shape_ops.add_rect(proj, 0, 0, 10, 10, fill="blue", stroke="red", stroke_width=2.0)
        elem = proj.elements[0]
        assert "fill:blue" in elem.style
        assert "stroke:red" in elem.style
        assert "stroke-width:2.0" in elem.style


# ---------------------------------------------------------------------------
# Style tests


class TestStyleOps:
    def test_parse_style_string(self) -> None:
        result = style_ops.parse_style_string("fill:red;stroke:black;stroke-width:2")
        assert result == {"fill": "red", "stroke": "black", "stroke-width": "2"}

    def test_parse_empty(self) -> None:
        assert style_ops.parse_style_string("") == {}

    def test_parse_with_spaces(self) -> None:
        result = style_ops.parse_style_string("fill: red ; stroke : blue")
        assert result["fill"] == "red"
        assert result["stroke"] == "blue"

    def test_render_style_string(self) -> None:
        d = {"fill": "red", "stroke": "black"}
        s = style_ops.render_style_string(d)
        assert "fill:red" in s
        assert "stroke:black" in s

    def test_set_fill(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        result = style_ops.set_fill(project_with_rect, elem_id, "#ff0000")
        assert result["action"] == "set_fill"
        elem = project_with_rect.find_by_id(elem_id)
        assert elem.fill == "#ff0000"
        assert "fill:#ff0000" in elem.style

    def test_set_stroke(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        style_ops.set_stroke(project_with_rect, elem_id, "green", width=3.0)
        elem = project_with_rect.find_by_id(elem_id)
        assert elem.stroke == "green"
        parsed = style_ops.parse_style_string(elem.style)
        assert parsed.get("stroke") == "green"
        assert parsed.get("stroke-width") == "3.0"

    def test_set_opacity(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        style_ops.set_opacity(project_with_rect, elem_id, 0.5)
        parsed = style_ops.parse_style_string(
            project_with_rect.find_by_id(elem_id).style
        )
        assert parsed.get("opacity") == "0.5"

    def test_set_opacity_clamped(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        style_ops.set_opacity(project_with_rect, elem_id, 1.5)
        parsed = style_ops.parse_style_string(
            project_with_rect.find_by_id(elem_id).style
        )
        assert float(parsed["opacity"]) == 1.0

    def test_set_style_property_valid(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        style_ops.set_style_property(project_with_rect, elem_id, "stroke-dasharray", "5,3")
        parsed = style_ops.parse_style_string(
            project_with_rect.find_by_id(elem_id).style
        )
        assert parsed.get("stroke-dasharray") == "5,3"

    def test_set_style_property_invalid_raises(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        with pytest.raises(ValueError, match="Unknown style property"):
            style_ops.set_style_property(project_with_rect, elem_id, "background-color", "red")

    def test_get_element_style(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        info = style_ops.get_element_style(project_with_rect, elem_id)
        assert "raw" in info
        assert "properties" in info

    def test_set_fill_missing_element(self, blank_project: InkscapeProject) -> None:
        with pytest.raises(KeyError):
            style_ops.set_fill(blank_project, "nonexistent", "red")

    def test_list_style_properties(self) -> None:
        props = style_ops.list_style_properties()
        prop_names = {p["prop"] for p in props}
        assert "fill" in prop_names
        assert "stroke" in prop_names
        assert "opacity" in prop_names


# ---------------------------------------------------------------------------
# Transform tests


class TestTransformOps:
    def test_parse_simple(self) -> None:
        ops = transform_ops.parse_transform_string("translate(10,20)")
        assert len(ops) == 1
        assert ops[0]["func"] == "translate"
        assert ops[0]["args"] == [10.0, 20.0]

    def test_parse_multiple(self) -> None:
        ops = transform_ops.parse_transform_string("translate(5,5) rotate(45) scale(2)")
        assert len(ops) == 3
        assert ops[1]["func"] == "rotate"

    def test_parse_empty(self) -> None:
        assert transform_ops.parse_transform_string("") == []

    def test_serialize_round_trip(self) -> None:
        original = "translate(10.0,20.0) rotate(45.0)"
        ops = transform_ops.parse_transform_string(original)
        result = transform_ops.serialize_transform(ops)
        assert "translate(10.0,20.0)" in result
        assert "rotate(45.0)" in result

    def test_translate_appends(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.translate(project_with_rect, elem_id, 10.0, 20.0)
        elem = project_with_rect.find_by_id(elem_id)
        assert "translate(10.0,20.0)" in elem.transform

    def test_rotate_appends(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.rotate(project_with_rect, elem_id, 45.0)
        assert "rotate(45.0)" in project_with_rect.find_by_id(elem_id).transform

    def test_rotate_with_center(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.rotate(project_with_rect, elem_id, 90.0, 50.0, 50.0)
        assert "rotate(90.0,50.0,50.0)" in project_with_rect.find_by_id(elem_id).transform

    def test_scale_uniform(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.scale(project_with_rect, elem_id, 2.0)
        assert "scale(2.0)" in project_with_rect.find_by_id(elem_id).transform

    def test_scale_non_uniform(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.scale(project_with_rect, elem_id, 2.0, 0.5)
        assert "scale(2.0,0.5)" in project_with_rect.find_by_id(elem_id).transform

    def test_skew_x(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.skew_x(project_with_rect, elem_id, 30.0)
        assert "skewX(30.0)" in project_with_rect.find_by_id(elem_id).transform

    def test_skew_y(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.skew_y(project_with_rect, elem_id, 15.0)
        assert "skewY(15.0)" in project_with_rect.find_by_id(elem_id).transform

    def test_set_transform_overwrites(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.translate(project_with_rect, elem_id, 5, 5)
        transform_ops.set_transform(project_with_rect, elem_id, "matrix(1,0,0,1,0,0)")
        assert project_with_rect.find_by_id(elem_id).transform == "matrix(1,0,0,1,0,0)"

    def test_get_transform(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.translate(project_with_rect, elem_id, 3, 4)
        info = transform_ops.get_transform(project_with_rect, elem_id)
        assert "raw_string" in info
        assert "operations" in info
        assert info["operations"][0]["func"] == "translate"

    def test_clear_transform(self, project_with_rect: InkscapeProject) -> None:
        elem_id = project_with_rect.elements[0].element_id
        transform_ops.translate(project_with_rect, elem_id, 10, 10)
        transform_ops.clear_transform(project_with_rect, elem_id)
        assert project_with_rect.find_by_id(elem_id).transform == ""

    def test_missing_element_raises(self, blank_project: InkscapeProject) -> None:
        with pytest.raises(KeyError):
            transform_ops.translate(blank_project, "ghost", 1, 1)


# ---------------------------------------------------------------------------
# Layer tests


class TestLayerOps:
    def test_add_layer(self, blank_project: InkscapeProject) -> None:
        result = layer_ops.add_layer(blank_project, "Background")
        assert result["action"] == "add_layer"
        assert result["index"] == 0
        assert result["layer"]["name"] == "Background"

    def test_add_multiple_layers(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "L1")
        layer_ops.add_layer(blank_project, "L2")
        layer_ops.add_layer(blank_project, "L3")
        info = layer_ops.list_layers(blank_project)
        assert info["layer_count"] == 3

    def test_remove_layer(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "A")
        layer_ops.add_layer(blank_project, "B")
        result = layer_ops.remove_layer(blank_project, 0)
        assert result["action"] == "remove_layer"
        assert layer_ops.list_layers(blank_project)["layer_count"] == 1

    def test_remove_layer_out_of_range(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "Only")
        with pytest.raises(IndexError):
            layer_ops.remove_layer(blank_project, 5)

    def test_move_to_layer(self, project_with_rect: InkscapeProject) -> None:
        layer_ops.add_layer(project_with_rect, "Base")
        layer_ops.add_layer(project_with_rect, "Top")
        elem_id = project_with_rect.elements[0].element_id
        result = layer_ops.move_to_layer(project_with_rect, elem_id, 1)
        assert result["action"] == "move_to_layer"
        assert elem_id in project_with_rect.data["layers"][1]["element_ids"]

    def test_set_layer_property_visibility(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "L1")
        layer_ops.set_layer_property(blank_project, 0, "visible", False)
        assert blank_project.data["layers"][0]["visible"] is False

    def test_set_layer_property_opacity_clamped(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "L1")
        layer_ops.set_layer_property(blank_project, 0, "opacity", 2.5)
        assert blank_project.data["layers"][0]["opacity"] == 1.0

    def test_set_layer_property_invalid(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "L1")
        with pytest.raises(ValueError):
            layer_ops.set_layer_property(blank_project, 0, "z_index", 99)

    def test_reorder_layers(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "First")
        layer_ops.add_layer(blank_project, "Second")
        layer_ops.add_layer(blank_project, "Third")
        layer_ops.reorder_layers(blank_project, 0, 2)
        layers = blank_project.data["layers"]
        assert layers[2]["name"] == "First"

    def test_get_layer(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "MyLayer", opacity=0.8)
        info = layer_ops.get_layer(blank_project, 0)
        assert info["name"] == "MyLayer"
        assert info["opacity"] == 0.8

    def test_list_layers_includes_index(self, blank_project: InkscapeProject) -> None:
        layer_ops.add_layer(blank_project, "A")
        layer_ops.add_layer(blank_project, "B")
        result = layer_ops.list_layers(blank_project)
        assert result["layers"][0]["index"] == 0
        assert result["layers"][1]["index"] == 1


# ---------------------------------------------------------------------------
# Path operation tests


class TestPathOps:
    def _two_rect_project(self) -> tuple[InkscapeProject, str, str]:
        proj = InkscapeProject()
        shape_ops.add_rect(proj, 0, 0, 50, 50)
        shape_ops.add_rect(proj, 25, 25, 50, 50)
        return proj, proj.elements[0].element_id, proj.elements[1].element_id

    def test_path_union(self) -> None:
        proj, id_a, id_b = self._two_rect_project()
        result = path_ops.path_union(proj, id_a, id_b)
        assert result["action"] == "path_union"
        assert len(proj.elements) == 1
        assert proj.elements[0].tag == "path"

    def test_path_intersection(self) -> None:
        proj, id_a, id_b = self._two_rect_project()
        result = path_ops.path_intersection(proj, id_a, id_b)
        assert result["action"] == "path_intersection"
        assert len(proj.elements) == 1

    def test_path_difference(self) -> None:
        proj, id_a, id_b = self._two_rect_project()
        result = path_ops.path_difference(proj, id_a, id_b)
        assert result["action"] == "path_difference"

    def test_path_exclusion(self) -> None:
        proj, id_a, id_b = self._two_rect_project()
        result = path_ops.path_exclusion(proj, id_a, id_b)
        assert result["action"] == "path_exclusion"

    def test_boolean_op_sources_removed(self) -> None:
        proj, id_a, id_b = self._two_rect_project()
        path_ops.path_union(proj, id_a, id_b)
        assert proj.find_by_id(id_a) is None
        assert proj.find_by_id(id_b) is None

    def test_boolean_op_missing_element(self) -> None:
        proj = InkscapeProject()
        with pytest.raises(KeyError):
            path_ops.path_union(proj, "ghost_a", "ghost_b")

    def test_list_path_operations(self) -> None:
        ops = path_ops.list_path_operations()
        names = {op["name"] for op in ops}
        assert {"union", "intersection", "difference", "exclusion"} == names

    def test_shape_to_path_rect(self) -> None:
        elem = SvgElement(element_id="r", tag="rect",
                          attrs={"x": 0, "y": 0, "width": 100, "height": 50})
        d = path_ops.shape_to_path_data(elem)
        assert d.startswith("M0")
        assert "Z" in d

    def test_shape_to_path_circle(self) -> None:
        elem = SvgElement(element_id="c", tag="circle",
                          attrs={"cx": 50, "cy": 50, "r": 25})
        d = path_ops.shape_to_path_data(elem)
        assert "C" in d
        assert "Z" in d

    def test_shape_to_path_line(self) -> None:
        elem = SvgElement(element_id="l", tag="line",
                          attrs={"x1": 0, "y1": 0, "x2": 100, "y2": 100})
        d = path_ops.shape_to_path_data(elem)
        assert d == "M0.0,0.0 L100.0,100.0"

    def test_shape_to_path_polygon(self) -> None:
        elem = SvgElement(element_id="p", tag="polygon",
                          attrs={"points": "0,0 50,100 100,0"})
        d = path_ops.shape_to_path_data(elem)
        assert "M0,0" in d
        assert "Z" in d

    def test_convert_to_path(self) -> None:
        proj = InkscapeProject()
        shape_ops.add_rect(proj, 0, 0, 10, 10)
        elem_id = proj.elements[0].element_id
        result = path_ops.convert_to_path(proj, elem_id)
        assert result["previous_tag"] == "rect"
        assert proj.find_by_id(elem_id).tag == "path"

    def test_shape_to_path_unsupported(self) -> None:
        elem = SvgElement(element_id="t", tag="text")
        with pytest.raises(ValueError, match="Unsupported"):
            path_ops.shape_to_path_data(elem)


# ---------------------------------------------------------------------------
# Gradient tests


class TestGradientOps:
    def _two_stop_stops(self) -> list[dict]:
        return [
            {"offset": 0.0, "color": "white", "opacity": 1.0},
            {"offset": 1.0, "color": "black", "opacity": 1.0},
        ]

    def test_add_linear_gradient(self, blank_project: InkscapeProject) -> None:
        result = gradient_ops.add_linear_gradient(blank_project, self._two_stop_stops())
        assert result["action"] == "add_linear_gradient"
        assert result["index"] == 0
        assert "gradient_id" in result

    def test_add_radial_gradient(self, blank_project: InkscapeProject) -> None:
        result = gradient_ops.add_radial_gradient(blank_project, self._two_stop_stops())
        assert result["action"] == "add_radial_gradient"
        assert result["index"] == 0

    def test_list_gradients(self, blank_project: InkscapeProject) -> None:
        gradient_ops.add_linear_gradient(blank_project, self._two_stop_stops())
        gradient_ops.add_radial_gradient(blank_project, self._two_stop_stops())
        result = gradient_ops.list_gradients(blank_project)
        assert result["gradient_count"] == 2

    def test_get_gradient(self, blank_project: InkscapeProject) -> None:
        gradient_ops.add_linear_gradient(blank_project, self._two_stop_stops(), name="TestGrad")
        info = gradient_ops.get_gradient(blank_project, 0)
        assert info["name"] == "TestGrad"
        assert info["index"] == 0

    def test_remove_gradient(self, blank_project: InkscapeProject) -> None:
        gradient_ops.add_linear_gradient(blank_project, self._two_stop_stops())
        result = gradient_ops.remove_gradient(blank_project, 0)
        assert result["action"] == "remove_gradient"
        assert gradient_ops.list_gradients(blank_project)["gradient_count"] == 0

    def test_apply_gradient_fill(self, project_with_rect: InkscapeProject) -> None:
        gradient_ops.add_linear_gradient(project_with_rect, self._two_stop_stops())
        elem_id = project_with_rect.elements[0].element_id
        result = gradient_ops.apply_gradient(project_with_rect, 0, elem_id, target="fill")
        assert result["action"] == "apply_gradient"
        elem = project_with_rect.find_by_id(elem_id)
        assert elem.fill.startswith("url(#")
        assert "fill:url(#" in elem.style

    def test_apply_gradient_invalid_target(self, project_with_rect: InkscapeProject) -> None:
        gradient_ops.add_linear_gradient(project_with_rect, self._two_stop_stops())
        elem_id = project_with_rect.elements[0].element_id
        with pytest.raises(ValueError, match="target must be"):
            gradient_ops.apply_gradient(project_with_rect, 0, elem_id, target="texture")

    def test_get_gradient_out_of_range(self, blank_project: InkscapeProject) -> None:
        with pytest.raises(IndexError):
            gradient_ops.get_gradient(blank_project, 99)

    def test_build_gradient_svg_linear(self, blank_project: InkscapeProject) -> None:
        gradient_ops.add_linear_gradient(blank_project, self._two_stop_stops(), name="G1")
        grad_dict = gradient_ops.list_gradients(blank_project)["gradients"][0]
        svg = gradient_ops.build_gradient_svg(grad_dict)
        assert "<defs>" in svg
        assert "<linearGradient" in svg
        assert "<stop" in svg

    def test_build_gradient_svg_radial(self, blank_project: InkscapeProject) -> None:
        gradient_ops.add_radial_gradient(blank_project, self._two_stop_stops())
        grad_dict = gradient_ops.list_gradients(blank_project)["gradients"][0]
        svg = gradient_ops.build_gradient_svg(grad_dict)
        assert "<radialGradient" in svg

    def test_gradient_def_round_trip(self) -> None:
        g = gradient_ops.GradientDef(
            gradient_id="abc",
            kind="linear",
            name="Test",
            stops=[gradient_ops.GradientStop(0.0, "red"), gradient_ops.GradientStop(1.0, "blue")],
        )
        d = g.to_dict()
        restored = gradient_ops.GradientDef.from_dict(d)
        assert restored.name == "Test"
        assert len(restored.stops) == 2
        assert restored.stops[0].color == "red"
