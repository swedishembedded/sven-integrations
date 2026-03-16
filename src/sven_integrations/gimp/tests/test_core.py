"""pytest tests for the GIMP harness.

Tests cover:
- GimpProject / LayerInfo data model and serialisation round-trips
- GimpSession persistence via tmp_path
- Layer CRUD helpers
- Export command building
- Filter and canvas script generation

No real GIMP binary is required — backend calls are mocked where needed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sven_integrations.gimp.project import GimpProject, LayerInfo
from sven_integrations.gimp.session import GimpSession
from sven_integrations.gimp.core import layers as layer_ops
from sven_integrations.gimp.core import filters as filter_ops
from sven_integrations.gimp.core import canvas as canvas_ops
from sven_integrations.gimp.core.export import (
    build_export_cmd,
    export_png,
    export_jpeg,
    export_tiff,
    export_webp,
    export_pdf,
    ExportError,
)


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture()
def sample_layer() -> LayerInfo:
    return LayerInfo(id=1, name="Background", opacity=1.0, visible=True, blend_mode="normal")


@pytest.fixture()
def blank_project() -> GimpProject:
    return GimpProject(width=800, height=600)


@pytest.fixture()
def gimp_session(tmp_path: Path) -> GimpSession:
    os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
    sess = GimpSession("test-gimp")
    yield sess
    os.environ.pop("SVEN_INTEGRATIONS_STATE_DIR", None)


# ---------------------------------------------------------------------------
# LayerInfo tests


class TestLayerInfo:
    def test_defaults(self, sample_layer: LayerInfo) -> None:
        assert sample_layer.opacity == 1.0
        assert sample_layer.visible is True
        assert sample_layer.blend_mode == "normal"
        assert sample_layer.group is False

    def test_round_trip(self, sample_layer: LayerInfo) -> None:
        restored = LayerInfo.from_dict(sample_layer.to_dict())
        assert restored.id == sample_layer.id
        assert restored.name == sample_layer.name
        assert restored.opacity == sample_layer.opacity
        assert restored.visible == sample_layer.visible
        assert restored.blend_mode == sample_layer.blend_mode

    def test_from_dict_partial(self) -> None:
        lyr = LayerInfo.from_dict({"id": 7, "name": "Overlay"})
        assert lyr.opacity == 1.0
        assert lyr.visible is True
        assert lyr.blend_mode == "normal"


# ---------------------------------------------------------------------------
# GimpProject tests


class TestGimpProject:
    def test_initial_state(self, blank_project: GimpProject) -> None:
        assert blank_project.width == 800
        assert blank_project.height == 600
        assert blank_project.color_mode == "RGB"
        assert blank_project.dpi == 72.0
        assert blank_project.layers == []
        assert blank_project.active_layer is None

    def test_add_layer(self, blank_project: GimpProject, sample_layer: LayerInfo) -> None:
        blank_project.add_layer(sample_layer)
        assert len(blank_project.layers) == 1
        blank_project.active_layer_index = 0
        assert blank_project.active_layer is sample_layer

    def test_remove_layer_found(self, blank_project: GimpProject, sample_layer: LayerInfo) -> None:
        blank_project.add_layer(sample_layer)
        removed = blank_project.remove_layer(1)
        assert removed is True
        assert blank_project.layers == []

    def test_remove_layer_missing(self, blank_project: GimpProject) -> None:
        removed = blank_project.remove_layer(999)
        assert removed is False

    def test_active_layer_index_clamps(self, blank_project: GimpProject) -> None:
        blank_project.add_layer(LayerInfo(id=1, name="A"))
        blank_project.add_layer(LayerInfo(id=2, name="B"))
        blank_project.active_layer_index = 1
        blank_project.remove_layer(2)
        assert blank_project.active_layer_index == 0

    def test_round_trip(self, blank_project: GimpProject, sample_layer: LayerInfo) -> None:
        blank_project.add_layer(sample_layer)
        blank_project.history.append("created layer")
        restored = GimpProject.from_dict(blank_project.to_dict())
        assert restored.width == blank_project.width
        assert restored.height == blank_project.height
        assert len(restored.layers) == 1
        assert restored.layers[0].name == "Background"
        assert restored.history == ["created layer"]

    def test_from_dict_defaults(self) -> None:
        proj = GimpProject.from_dict({"width": 100, "height": 200})
        assert proj.color_mode == "RGB"
        assert proj.dpi == 72.0
        assert proj.layers == []


# ---------------------------------------------------------------------------
# GimpSession tests


class TestGimpSession:
    def test_new_project(self, gimp_session: GimpSession) -> None:
        proj = gimp_session.new_project(1920, 1080, "RGBA", 96.0)
        assert proj.width == 1920
        assert proj.height == 1080
        assert proj.color_mode == "RGBA"
        assert proj.dpi == 96.0

    def test_project_property_none_when_empty(self, gimp_session: GimpSession) -> None:
        assert gimp_session.project is None

    def test_project_setter_and_getter(
        self, gimp_session: GimpSession, blank_project: GimpProject
    ) -> None:
        gimp_session.project = blank_project
        retrieved = gimp_session.project
        assert retrieved is not None
        assert retrieved.width == 800

    def test_save_and_load(self, gimp_session: GimpSession, blank_project: GimpProject) -> None:
        gimp_session.project = blank_project
        gimp_session.save()
        fresh = GimpSession("test-gimp")
        fresh.load()
        assert fresh.project is not None
        assert fresh.project.width == 800

    def test_close_clears_project(self, gimp_session: GimpSession, blank_project: GimpProject) -> None:
        gimp_session.project = blank_project
        gimp_session.close()
        assert gimp_session.project is None

    def test_delete(self, gimp_session: GimpSession) -> None:
        gimp_session.new_project(400, 300)
        removed = gimp_session.delete()
        assert removed is True
        assert not gimp_session._path.exists()

    def test_list_sessions(self, tmp_path: Path) -> None:
        os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
        for name in ("alpha", "beta", "gamma"):
            s = GimpSession(name)
            s.save()
        names = GimpSession.list_sessions()
        assert set(names) == {"alpha", "beta", "gamma"}
        os.environ.pop("SVEN_INTEGRATIONS_STATE_DIR", None)


# ---------------------------------------------------------------------------
# Layer operation tests


class TestLayerOps:
    def test_create_layer_returns_script(self) -> None:
        result = layer_ops.create_layer("Test", 200, 100)
        assert result["action"] == "create_layer"
        assert "script" in result
        assert "Test" in result["script"]
        assert "200" in result["script"]

    def test_duplicate_layer(self) -> None:
        result = layer_ops.duplicate_layer(42)
        assert result["layer_id"] == 42
        assert "42" in result["script"]

    def test_set_layer_opacity_valid(self) -> None:
        result = layer_ops.set_layer_opacity(3, 0.75)
        assert result["opacity"] == 0.75
        assert "75.0" in result["script"]

    def test_set_layer_opacity_invalid(self) -> None:
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            layer_ops.set_layer_opacity(3, 1.5)

    def test_move_layer(self) -> None:
        result = layer_ops.move_layer(5, 100, 200)
        assert result["x"] == 100
        assert result["y"] == 200

    def test_resize_layer(self) -> None:
        result = layer_ops.resize_layer(5, 400, 300)
        assert result["width"] == 400
        assert result["height"] == 300

    def test_flatten_image(self) -> None:
        result = layer_ops.flatten_image()
        assert "flatten" in result["script"]

    def test_merge_visible(self) -> None:
        result = layer_ops.merge_visible()
        assert "merge-visible" in result["script"]


# ---------------------------------------------------------------------------
# Export command building tests


class TestExportOps:
    def test_build_export_cmd_png(self) -> None:
        cmd = build_export_cmd("png", "/tmp/out.png")
        assert cmd[0] == "gimp"
        assert "--no-interface" in cmd
        assert any("file-png-save" in token for token in cmd)

    def test_build_export_cmd_jpeg(self) -> None:
        cmd = build_export_cmd("jpeg", "/tmp/out.jpg", quality=85)
        assert any("file-jpeg-save" in token for token in cmd)

    def test_build_export_cmd_webp(self) -> None:
        cmd = build_export_cmd("webp", "/tmp/out.webp", quality=75)
        assert any("file-webp-save" in token for token in cmd)

    def test_build_export_cmd_pdf(self) -> None:
        cmd = build_export_cmd("pdf", "/tmp/out.pdf")
        assert any("file-pdf-save" in token for token in cmd)

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(ExportError):
            build_export_cmd("bmp", "/tmp/out.bmp")

    def test_export_jpeg_quality_out_of_range(self) -> None:
        with pytest.raises(ExportError):
            export_jpeg("/tmp/x.jpg", quality=110)

    def test_export_webp_quality_out_of_range(self) -> None:
        with pytest.raises(ExportError):
            export_webp("/tmp/x.webp", quality=-1)

    def test_export_png_result_structure(self) -> None:
        result = export_png("/tmp/test.png", interlace=0, compression=6)
        assert result["action"] == "export_png"
        assert result["path"] == "/tmp/test.png"
        assert isinstance(result["cmd"], list)

    def test_export_tiff_result_structure(self) -> None:
        result = export_tiff("/tmp/test.tiff")
        assert result["action"] == "export_tiff"

    def test_export_pdf_result_structure(self) -> None:
        result = export_pdf("/tmp/out.pdf")
        assert result["action"] == "export_pdf"


# ---------------------------------------------------------------------------
# Filter tests


class TestFilterOps:
    def test_apply_blur(self) -> None:
        result = filter_ops.apply_blur(3.0)
        assert result["action"] == "apply_blur"
        assert "plug-in-gauss" in result["script"]

    def test_apply_sharpen(self) -> None:
        result = filter_ops.apply_sharpen(60.0)
        assert "plug-in-sharpen" in result["script"]

    def test_apply_unsharp_mask(self) -> None:
        result = filter_ops.apply_unsharp_mask(5.0, 0.5, 0)
        assert result["radius"] == 5.0
        assert "plug-in-unsharp-mask" in result["script"]

    def test_apply_levels(self) -> None:
        result = filter_ops.apply_levels((0, 220, 1.2), (10, 245))
        assert "gimp-levels" in result["script"]

    def test_apply_hue_saturation(self) -> None:
        result = filter_ops.apply_hue_saturation(15.0, -10.0, 5.0)
        assert "hue-saturation" in result["script"]


# ---------------------------------------------------------------------------
# Canvas tests


class TestCanvasOps:
    def test_crop(self) -> None:
        result = canvas_ops.crop(10, 20, 300, 200)
        assert "gimp-image-crop" in result["script"]

    def test_resize_canvas(self) -> None:
        result = canvas_ops.resize_canvas(1024, 768, 0, 0)
        assert "gimp-image-resize" in result["script"]

    def test_scale_image(self) -> None:
        result = canvas_ops.scale_image(640, 480)
        assert "gimp-image-scale-full" in result["script"]

    def test_rotate(self) -> None:
        result = canvas_ops.rotate(90.0)
        assert result["angle_deg"] == 90.0
        assert "transform-rotate" in result["script"]

    def test_flip_horizontal(self) -> None:
        result = canvas_ops.flip("h")
        assert "HORIZONTAL" in result["script"]

    def test_flip_vertical(self) -> None:
        result = canvas_ops.flip("v")
        assert "VERTICAL" in result["script"]

    def test_flip_invalid(self) -> None:
        with pytest.raises(ValueError):
            canvas_ops.flip("x")  # type: ignore[arg-type]

    def test_set_resolution(self) -> None:
        result = canvas_ops.set_resolution(300.0)
        assert "300.0" in result["script"]
