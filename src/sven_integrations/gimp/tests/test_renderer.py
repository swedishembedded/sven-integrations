"""Integration tests for the Pillow-based renderer and full CLI pipeline.

Tests verify that:
- GimpProject with draw operations produces actual image files
- All draw operation types render correctly (rect, ellipse, circle, line, text)
- Filters are applied during render
- Multi-layer compositing works
- The full CLI round-trip produces files with correct dimensions and non-trivial size
- export render with JPEG and WebP formats works
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from sven_integrations.gimp.core.renderer import RenderError, render_project
from sven_integrations.gimp.project import DrawOperation, FilterInfo, GimpProject, LayerInfo

# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture()
def white_bg_project() -> GimpProject:
    """A 400x300 project with a white background layer at index 0."""
    proj = GimpProject(width=400, height=300, name="test")
    bg = LayerInfo(id=0, name="Background", width=400, height=300, fill_color="white")
    proj.layers = [bg]
    return proj


@pytest.fixture()
def tmp_png(tmp_path: Path) -> Path:
    return tmp_path / "output.png"


@pytest.fixture()
def project_file(tmp_path: Path) -> Path:
    return tmp_path / "proj.json"


# ---------------------------------------------------------------------------
# DrawOperation / FilterInfo model tests


class TestDrawOperation:
    def test_round_trip(self) -> None:
        op = DrawOperation(op_type="ellipse", params={"cx": 100, "cy": 200, "rx": 50, "ry": 40, "fill": "#ff0000"})
        restored = DrawOperation.from_dict(op.to_dict())
        assert restored.op_type == "ellipse"
        assert restored.params["cx"] == 100
        assert restored.params["fill"] == "#ff0000"

    def test_empty_params(self) -> None:
        op = DrawOperation(op_type="text")
        d = op.to_dict()
        assert d["params"] == {}
        restored = DrawOperation.from_dict(d)
        assert restored.op_type == "text"


class TestFilterInfo:
    def test_round_trip(self) -> None:
        fi = FilterInfo(name="brightness", params={"factor": 1.5})
        restored = FilterInfo.from_dict(fi.to_dict())
        assert restored.name == "brightness"
        assert restored.params["factor"] == 1.5

    def test_no_params(self) -> None:
        fi = FilterInfo(name="grayscale")
        d = fi.to_dict()
        assert d["params"] == {}


class TestLayerInfoWithOps:
    def test_draw_ops_round_trip(self) -> None:
        layer = LayerInfo(id=0, name="BG", fill_color="white")
        layer.draw_ops.append(DrawOperation(op_type="rect", params={"x1": 0, "y1": 0, "x2": 100, "y2": 100, "fill": "#000000"}))
        layer.filters.append(FilterInfo(name="grayscale"))
        d = layer.to_dict()
        restored = LayerInfo.from_dict(d)
        assert len(restored.draw_ops) == 1
        assert restored.draw_ops[0].op_type == "rect"
        assert len(restored.filters) == 1
        assert restored.filters[0].name == "grayscale"

    def test_empty_ops_not_serialized(self) -> None:
        layer = LayerInfo(id=0, name="Empty")
        d = layer.to_dict()
        assert "draw_ops" not in d
        assert "filters" not in d


# ---------------------------------------------------------------------------
# Renderer unit tests


class TestRendererBasic:
    def test_render_requires_layers(self, tmp_png: Path) -> None:
        proj = GimpProject(width=100, height=100)
        with pytest.raises(RenderError, match="no layers"):
            render_project(proj, str(tmp_png))

    def test_render_produces_png(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        result = render_project(white_bg_project, str(tmp_png))
        assert result["ok"] is True
        assert tmp_png.exists()
        assert result["size_bytes"] > 100
        assert result["width"] == 400
        assert result["height"] == 300

    def test_render_png_dimensions(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        render_project(white_bg_project, str(tmp_png))
        img = Image.open(tmp_png)
        assert img.size == (400, 300)

    def test_render_jpeg(self, white_bg_project: GimpProject, tmp_path: Path) -> None:
        out = tmp_path / "out.jpg"
        result = render_project(white_bg_project, str(out), fmt="jpeg", quality=85)
        assert result["ok"] is True
        assert out.exists()
        img = Image.open(out)
        assert img.size == (400, 300)

    def test_render_webp(self, white_bg_project: GimpProject, tmp_path: Path) -> None:
        out = tmp_path / "out.webp"
        result = render_project(white_bg_project, str(out), fmt="webp", quality=80)
        assert result["ok"] is True
        assert out.exists()

    def test_render_unsupported_format(self, white_bg_project: GimpProject, tmp_path: Path) -> None:
        with pytest.raises(RenderError, match="Unsupported format"):
            render_project(white_bg_project, str(tmp_path / "x.bmp"), fmt="bmp")

    def test_render_white_background(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        render_project(white_bg_project, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        # Sample center pixel — should be white (or very close) since only background layer
        r, g, b = img.getpixel((200, 150))
        assert r > 250 and g > 250 and b > 250


class TestRendererShapes:
    def test_rect_draws_color(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        white_bg_project.layers[0].draw_ops.append(
            DrawOperation("rect", {"x1": 0, "y1": 0, "x2": 400, "y2": 300, "fill": "#ff0000"})
        )
        render_project(white_bg_project, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((200, 150))
        assert r > 200 and g < 50 and b < 50  # predominantly red

    def test_ellipse_draws_color(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        white_bg_project.layers[0].draw_ops.append(
            DrawOperation("ellipse", {"cx": 200, "cy": 150, "rx": 180, "ry": 130, "fill": "#0000ff"})
        )
        render_project(white_bg_project, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((200, 150))
        assert b > 200 and r < 50

    def test_line_draws(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        white_bg_project.layers[0].draw_ops.append(
            DrawOperation("line", {"x1": 0, "y1": 0, "x2": 400, "y2": 300, "stroke": "#000000", "stroke_width": 5})
        )
        render_project(white_bg_project, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        # Corner pixel at origin should be dark (line starts there)
        r, g, b = img.getpixel((2, 2))
        assert r < 50 and g < 50 and b < 50

    def test_text_renders(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        white_bg_project.layers[0].draw_ops.append(
            DrawOperation("text", {"text": "Hi", "x": 50, "y": 100, "size": 40, "color": "#000000"})
        )
        render_project(white_bg_project, str(tmp_png))
        # Should not raise; file should exist with content
        assert tmp_png.exists()
        assert tmp_png.stat().st_size > 500


class TestRendererFilters:
    def test_grayscale_filter(self, tmp_png: Path) -> None:
        proj = GimpProject(width=100, height=100)
        layer = LayerInfo(id=0, name="BG", width=100, height=100, fill_color="#ff0000")
        layer.filters.append(FilterInfo(name="grayscale"))
        proj.layers = [layer]
        render_project(proj, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        # Grayscale: all channels equal
        assert abs(r - g) < 5 and abs(g - b) < 5

    def test_brightness_filter(self, tmp_png: Path) -> None:
        proj = GimpProject(width=100, height=100)
        layer = LayerInfo(id=0, name="BG", width=100, height=100, fill_color="#888888")
        layer.filters.append(FilterInfo(name="brightness", params={"factor": 2.0}))
        proj.layers = [layer]
        render_project(proj, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        # Should be brighter than 0x88 = 136
        assert r > 150

    def test_invert_filter(self, tmp_png: Path) -> None:
        proj = GimpProject(width=100, height=100)
        layer = LayerInfo(id=0, name="BG", width=100, height=100, fill_color="#ffffff")
        layer.filters.append(FilterInfo(name="invert"))
        proj.layers = [layer]
        render_project(proj, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        # Inverted white = black
        assert r < 10 and g < 10 and b < 10

    def test_blur_filter_does_not_crash(self, white_bg_project: GimpProject, tmp_png: Path) -> None:
        white_bg_project.layers[0].draw_ops.append(
            DrawOperation("rect", {"x1": 100, "y1": 100, "x2": 300, "y2": 200, "fill": "#000000"})
        )
        white_bg_project.layers[0].filters.append(FilterInfo(name="gaussian_blur", params={"radius": 3}))
        render_project(white_bg_project, str(tmp_png))
        assert tmp_png.exists()


class TestRendererMultiLayer:
    def test_two_layers_composite(self, tmp_png: Path) -> None:
        proj = GimpProject(width=200, height=200)
        bg = LayerInfo(id=0, name="BG", width=200, height=200, fill_color="#ff0000")
        fg = LayerInfo(id=1, name="FG", width=200, height=200, fill_color=None)
        fg.draw_ops.append(DrawOperation("ellipse", {"cx": 100, "cy": 100, "rx": 50, "ry": 50, "fill": "#0000ff"}))
        proj.layers = [fg, bg]  # fg on top (index 0), bg below (index 1)
        render_project(proj, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        # Center of ellipse should be blue
        r, g, b = img.getpixel((100, 100))
        assert b > 200 and r < 50
        # Corner outside ellipse should be red (bg)
        r2, g2, b2 = img.getpixel((5, 5))
        assert r2 > 200 and b2 < 50

    def test_invisible_layer_skipped(self, tmp_png: Path) -> None:
        proj = GimpProject(width=100, height=100)
        bg = LayerInfo(id=0, name="BG", width=100, height=100, fill_color="white")
        hidden = LayerInfo(id=1, name="Hidden", width=100, height=100, fill_color="#ff0000", visible=False)
        proj.layers = [hidden, bg]
        render_project(proj, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        # Hidden red layer should not appear; background is white
        assert r > 240 and g > 240 and b > 240

    def test_opacity_blending(self, tmp_png: Path) -> None:
        proj = GimpProject(width=100, height=100)
        bg = LayerInfo(id=0, name="BG", width=100, height=100, fill_color="white")
        overlay = LayerInfo(id=1, name="OVL", width=100, height=100, fill_color="#000000", opacity=0.5)
        proj.layers = [overlay, bg]
        render_project(proj, str(tmp_png))
        img = Image.open(tmp_png).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        # Semi-transparent black over white -> mid-gray
        assert 100 < r < 200


# ---------------------------------------------------------------------------
# CLI integration tests


class TestCLIIntegration:
    """Full CLI round-trip tests using the installed sven-integrations-gimp binary."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sven-integrations-gimp", "--json", *args],
            capture_output=True, text=True
        )

    def test_project_new_creates_background_layer(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        result = self._run("project", "new", "--width", "400", "--height", "300", "-o", str(proj_file))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert len(data["project"]["layers"]) == 1
        assert data["project"]["layers"][0]["name"] == "Background"
        assert data["project"]["layers"][0]["fill_color"] == "white"

    def test_project_new_saves_json(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "--width", "400", "--height", "300", "-o", str(proj_file))
        assert proj_file.exists()
        data = json.loads(proj_file.read_text())
        assert data["width"] == 400

    def test_draw_ellipse_stored(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "--width", "400", "--height", "300", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "draw", "ellipse",
                           "--cx", "200", "--cy", "150", "--rx", "100", "--ry", "80",
                           "--fill", "#ff8800", "--layer", "0")
        assert result.returncode == 0
        # Verify operation stored in JSON
        data = json.loads(proj_file.read_text())
        ops = data["layers"][0].get("draw_ops", [])
        assert len(ops) == 1
        assert ops[0]["op_type"] == "ellipse"
        assert ops[0]["params"]["fill"] == "#ff8800"

    def test_draw_rect_stored(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "--width", "400", "--height", "300", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "draw", "rect",
                           "--x", "10", "--y", "10", "--w", "200", "--h", "100",
                           "--fill", "#0000ff", "--layer", "0")
        assert result.returncode == 0
        data = json.loads(proj_file.read_text())
        ops = data["layers"][0].get("draw_ops", [])
        assert ops[0]["op_type"] == "rect"

    def test_draw_line_stored(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "draw", "line",
                           "--x1", "0", "--y1", "0", "--x2", "100", "--y2", "100",
                           "--stroke", "#ff0000", "--width", "3", "--layer", "0")
        assert result.returncode == 0
        data = json.loads(proj_file.read_text())
        ops = data["layers"][0].get("draw_ops", [])
        assert ops[0]["op_type"] == "line"

    def test_draw_text_stored(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "draw", "text",
                           "--text", "Hello", "--x", "50", "--y", "50",
                           "--size", "24", "--color", "#000000", "--layer", "0")
        assert result.returncode == 0
        data = json.loads(proj_file.read_text())
        ops = data["layers"][0].get("draw_ops", [])
        assert ops[0]["op_type"] == "text"
        assert ops[0]["params"]["text"] == "Hello"

    def test_filter_add_stored(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "filter", "add", "grayscale", "--layer", "0")
        assert result.returncode == 0
        data = json.loads(proj_file.read_text())
        filters = data["layers"][0].get("filters", [])
        assert len(filters) == 1
        assert filters[0]["name"] == "grayscale"

    def test_export_render_creates_file(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        out_file = tmp_path / "output.png"
        self._run("project", "new", "--width", "400", "--height", "300", "-o", str(proj_file))
        self._run("-p", str(proj_file), "draw", "ellipse",
                  "--cx", "200", "--cy", "150", "--rx", "100", "--ry", "80",
                  "--fill", "#ff8800", "--layer", "0")
        result = self._run("-p", str(proj_file), "export", "render", str(out_file), "--overwrite")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["size_bytes"] > 100
        assert out_file.exists()
        img = Image.open(out_file)
        assert img.size == (400, 300)

    def test_export_render_overwrite_required(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        out_file = tmp_path / "output.png"
        out_file.write_bytes(b"placeholder")
        self._run("project", "new", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "export", "render", str(out_file))
        assert result.returncode != 0  # Should fail without --overwrite

    def test_full_cat_drawing_pipeline(self, tmp_path: Path) -> None:
        """Replicate the failed cat-drawing conversation end-to-end."""
        proj_file = tmp_path / "cat.json"
        out_file = tmp_path / "cat.png"

        # Create project
        r = self._run("project", "new", "--width", "800", "--height", "800",
                      "--name", "Cat Drawing", "-o", str(proj_file))
        assert r.returncode == 0

        # Draw cat body
        self._run("-p", str(proj_file), "draw", "ellipse",
                  "--cx", "400", "--cy", "520", "--rx", "180", "--ry", "120",
                  "--fill", "#f4a460", "--layer", "0")
        # Draw cat head
        self._run("-p", str(proj_file), "draw", "ellipse",
                  "--cx", "360", "--cy", "420", "--rx", "70", "--ry", "60",
                  "--fill", "#f4a460", "--layer", "0")
        # Eyes
        self._run("-p", str(proj_file), "draw", "circle",
                  "--cx", "340", "--cy", "410", "--r", "10",
                  "--fill", "#222222", "--layer", "0")
        self._run("-p", str(proj_file), "draw", "circle",
                  "--cx", "380", "--cy", "410", "--r", "10",
                  "--fill", "#222222", "--layer", "0")
        # Whiskers
        self._run("-p", str(proj_file), "draw", "line",
                  "--x1", "360", "--y1", "430", "--x2", "300", "--y2", "425",
                  "--stroke", "#888888", "--width", "2", "--layer", "0")

        # Render
        r = self._run("-p", str(proj_file), "export", "render", str(out_file), "--overwrite")
        assert r.returncode == 0
        assert out_file.exists()
        assert out_file.stat().st_size > 1000
        img = Image.open(out_file)
        assert img.size == (800, 800)

    def test_layer_out_of_range_error(self, tmp_path: Path) -> None:
        proj_file = tmp_path / "proj.json"
        self._run("project", "new", "-o", str(proj_file))
        result = self._run("-p", str(proj_file), "draw", "ellipse",
                           "--cx", "100", "--cy", "100", "--rx", "50", "--ry", "50",
                           "--layer", "99")
        assert result.returncode != 0
        assert "out of range" in result.stderr.lower()
