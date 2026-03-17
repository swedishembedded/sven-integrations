"""Pillow-based renderer for GimpProject.

Composites all visible layers bottom-to-top, draws stored drawing operations
on each layer, applies layer filters, then saves to the requested format.
This is the default rendering backend — no GIMP installation required.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

if TYPE_CHECKING:
    from ..project import DrawOperation, FilterInfo, GimpProject, LayerInfo


class RenderError(ValueError):
    """Raised when rendering fails for a known reason."""


# ---------------------------------------------------------------------------
# Color parsing


def _parse_color(color: str | None, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Parse a CSS-style color string into an RGBA tuple."""
    if color is None:
        return default
    color = color.strip()
    if color.lower() in ("transparent", "none", ""):
        return (0, 0, 0, 0)
    if color.lower() == "white":
        return (255, 255, 255, 255)
    if color.lower() == "black":
        return (0, 0, 0, 255)
    if color.lower() == "red":
        return (255, 0, 0, 255)
    if color.lower() == "green":
        return (0, 128, 0, 255)
    if color.lower() == "blue":
        return (0, 0, 255, 255)
    if color.lower() == "yellow":
        return (255, 255, 0, 255)
    if color.lower() == "orange":
        return (255, 165, 0, 255)
    if color.lower() == "gray" or color.lower() == "grey":
        return (128, 128, 128, 255)
    if color.startswith("#"):
        h = color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (r, g, b, 255)
        if len(h) == 8:
            r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
            return (r, g, b, a)
    # Fallback: use PIL to parse
    try:
        img = Image.new("RGBA", (1, 1), color)
        return img.getpixel((0, 0))  # type: ignore[return-value]
    except Exception:
        return default


def _rgba_to_pil(rgba: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return rgba


# ---------------------------------------------------------------------------
# Font loading


def _load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a font by name, fall back to Pillow default.

    Searches platform-appropriate font paths so the renderer works on Linux,
    macOS, and Windows without requiring a specific font installation.
    """
    import platform
    sys_name = platform.system()

    linux_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
    ]
    macos_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        os.path.expanduser("~/Library/Fonts/Arial.ttf"),
    ]
    windows_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]

    candidates = [font_name, f"{font_name}.ttf"]
    if sys_name == "Darwin":
        candidates += macos_paths + linux_paths
    elif sys_name == "Windows":
        candidates += windows_paths + linux_paths
    else:
        candidates += linux_paths + macos_paths

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Per-layer drawing


def _render_layer(layer: "LayerInfo", canvas_w: int, canvas_h: int) -> Image.Image:
    """Render a single layer to an RGBA PIL image."""
    w = layer.width if layer.width is not None else canvas_w
    h = layer.height if layer.height is not None else canvas_h

    # Initialize layer image
    fill_color = layer.fill_color or "transparent"
    bg = _parse_color(fill_color, (0, 0, 0, 0))
    img = Image.new("RGBA", (w, h), bg)

    # Load source image if present
    if layer.source is not None:
        if not os.path.exists(layer.source):
            raise RenderError(
                f"Layer source image not found: {layer.source!r}. "
                "Use an absolute path to an existing image file."
            )
        try:
            src = Image.open(layer.source).convert("RGBA")
            src = src.resize((w, h), Image.LANCZOS)
            img = src
        except OSError as exc:
            raise RenderError(f"Cannot open source image {layer.source!r}: {exc}") from exc

    draw = ImageDraw.Draw(img)

    # Execute all draw operations
    for op in layer.draw_ops:
        _execute_draw_op(draw, img, op, w, h)

    return img


def _execute_draw_op(draw: ImageDraw.ImageDraw, img: Image.Image, op: "DrawOperation", w: int, h: int) -> None:
    """Execute a single DrawOperation on the given ImageDraw context."""
    p = op.params
    op_type = op.op_type

    if op_type == "rect":
        x1 = int(p.get("x1", 0))
        y1 = int(p.get("y1", 0))
        x2 = int(p.get("x2", w))
        y2 = int(p.get("y2", h))
        fill = _parse_color(p.get("fill"), (0, 0, 0, 0))
        stroke_width = int(p.get("stroke_width", 1))
        outline_color = _parse_color(p.get("outline"), (0, 0, 0, 255)) if p.get("outline") else None
        draw.rectangle([x1, y1, x2, y2], fill=fill if fill[3] > 0 else None,
                       outline=outline_color, width=stroke_width)

    elif op_type in ("ellipse", "circle"):
        cx = int(p.get("cx", w // 2))
        cy = int(p.get("cy", h // 2))
        rx = int(p.get("rx", 50))
        ry = int(p.get("ry", rx))
        fill_rgba = _parse_color(p.get("fill"), (0, 0, 0, 255))
        outline_color = _parse_color(p.get("outline"), (0, 0, 0, 255)) if p.get("outline") else None
        stroke_width = int(p.get("stroke_width", 1))
        bbox = [cx - rx, cy - ry, cx + rx, cy + ry]
        draw.ellipse(bbox, fill=fill_rgba, outline=outline_color, width=stroke_width)

    elif op_type == "line":
        x1 = int(p.get("x1", 0))
        y1 = int(p.get("y1", 0))
        x2 = int(p.get("x2", w))
        y2 = int(p.get("y2", h))
        stroke = _parse_color(p.get("stroke", p.get("fill")), (0, 0, 0, 255))
        stroke_width = int(p.get("stroke_width", p.get("width", 1)))
        draw.line([x1, y1, x2, y2], fill=stroke, width=stroke_width)

    elif op_type == "text":
        x = int(p.get("x", 0))
        y = int(p.get("y", 0))
        text = str(p.get("text", ""))
        color = _parse_color(p.get("color", p.get("fill")), (0, 0, 0, 255))
        font_name = str(p.get("font", "DejaVuSans"))
        font_size = int(p.get("size", 24))
        font = _load_font(font_name, font_size)
        draw.text((x, y), text, fill=color, font=font)


# ---------------------------------------------------------------------------
# Filter application


def _apply_filters(img: Image.Image, filters: list["FilterInfo"]) -> Image.Image:
    """Apply a sequence of filters to an RGBA image."""
    for f in filters:
        img = _apply_single_filter(img, f.name, f.params)
    return img


def _apply_single_filter(img: Image.Image, name: str, params: dict[str, Any]) -> Image.Image:
    """Apply one named filter to an image."""
    name = name.lower()

    if name == "blur":
        radius = float(params.get("radius", params.get("factor", 2)))
        return img.filter(ImageFilter.GaussianBlur(radius=radius))

    if name == "gaussian_blur":
        radius = float(params.get("radius", params.get("factor", 2)))
        return img.filter(ImageFilter.GaussianBlur(radius=radius))

    if name == "box_blur":
        radius = float(params.get("radius", 2))
        return img.filter(ImageFilter.BoxBlur(radius=radius))

    if name == "sharpen" or name == "sharpness":
        factor = float(params.get("factor", 1.5))
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(factor)

    if name == "edge_enhance":
        return img.filter(ImageFilter.EDGE_ENHANCE)

    if name == "brightness":
        factor = float(params.get("factor", 1.2))
        enhancer = ImageEnhance.Brightness(img)
        return enhancer.enhance(factor)

    if name == "contrast":
        factor = float(params.get("factor", 1.2))
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    if name == "saturation":
        factor = float(params.get("factor", 1.2))
        enhancer = ImageEnhance.Color(img)
        return enhancer.enhance(factor)

    if name == "grayscale":
        gray = img.convert("L").convert("RGBA")
        return gray

    if name == "sepia":
        strength = float(params.get("strength", 1.0))
        gray = img.convert("L").convert("RGB")
        r_data = gray.split()[0]
        g_data = gray.split()[1]
        b_data = gray.split()[2]
        # Classic sepia tone matrix
        from PIL import ImageOps
        r = r_data.point(lambda i: min(255, int(i * (1 - strength) + (i * 0.393 + i * 0.769 * 0.5 + i * 0.189 * 0.1) * strength)))
        g = g_data.point(lambda i: min(255, int(i * (1 - strength) + (i * 0.349 + i * 0.686 * 0.5 + i * 0.168 * 0.1) * strength)))
        b = b_data.point(lambda i: min(255, int(i * (1 - strength) + (i * 0.272 + i * 0.534 * 0.5 + i * 0.131 * 0.1) * strength)))
        sepia = Image.merge("RGB", (r, g, b))
        if img.mode == "RGBA":
            sepia = sepia.convert("RGBA")
        return sepia

    if name == "invert":
        from PIL import ImageOps
        if img.mode == "RGBA":
            r, g, b, a = img.split()
            rgb = Image.merge("RGB", (r, g, b))
            inverted = ImageOps.invert(rgb)
            ir, ig, ib = inverted.split()
            return Image.merge("RGBA", (ir, ig, ib, a))
        return ImageOps.invert(img)

    if name == "flip_h":
        return img.transpose(Image.FLIP_LEFT_RIGHT)

    if name == "flip_v":
        return img.transpose(Image.FLIP_TOP_BOTTOM)

    if name == "rotate":
        angle = float(params.get("angle", params.get("factor", 90)))
        return img.rotate(-angle, expand=False)

    known_filters = (
        "blur", "gaussian_blur", "box_blur", "sharpen", "sharpness",
        "edge_enhance", "brightness", "contrast", "saturation",
        "grayscale", "sepia", "invert", "flip_h", "flip_v", "rotate",
    )
    raise RenderError(
        f"Unknown filter {name!r}. Available filters: {', '.join(sorted(known_filters))}"
    )


# ---------------------------------------------------------------------------
# Layer compositing


def _apply_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """Multiply the alpha channel by *opacity*."""
    if opacity >= 1.0:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda v: int(v * opacity))
    return Image.merge("RGBA", (r, g, b, a))


# ---------------------------------------------------------------------------
# Main entry point


def render_project(
    project: "GimpProject",
    output_path: str,
    fmt: str = "png",
    quality: int = 90,
) -> dict[str, Any]:
    """Render *project* to *output_path*.

    Returns a dict with at least ``{"ok": True, "path": output_path, "size_bytes": int}``.

    Raises
    ------
    RenderError
        If the project has no layers or the format is unsupported.
    """
    if not project.layers:
        raise RenderError("Project has no layers. Add at least one layer before rendering.")

    supported = {"png", "jpeg", "jpg", "webp", "tiff"}
    fmt_key = fmt.lower().lstrip(".")
    if fmt_key not in supported:
        raise RenderError(f"Unsupported format {fmt!r}. Supported: {', '.join(sorted(supported))}")

    w, h = project.width, project.height

    # Start with transparent canvas
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Composite layers bottom-to-top (layers list is top-to-bottom, so reverse)
    for layer in reversed(project.layers):
        if not layer.visible:
            continue
        layer_img = _render_layer(layer, w, h)
        layer_img = _apply_filters(layer_img, layer.filters)
        layer_img = _apply_opacity(layer_img, layer.opacity)
        # Position layer at its offset
        ox = layer.offset_x
        oy = layer.offset_y
        if ox != 0 or oy != 0:
            positioned = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            positioned.paste(layer_img, (ox, oy))
            layer_img = positioned
        else:
            # Ensure layer is same size as canvas for compositing
            if layer_img.size != (w, h):
                padded = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                padded.paste(layer_img, (0, 0))
                layer_img = padded
        canvas = Image.alpha_composite(canvas, layer_img)

    # Ensure output directory exists
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Save in requested format
    if fmt_key == "png":
        canvas.save(str(out_path), format="PNG")
    elif fmt_key in ("jpeg", "jpg"):
        flat = Image.new("RGB", (w, h), (255, 255, 255))
        flat.paste(canvas, mask=canvas.split()[3])
        flat.save(str(out_path), format="JPEG", quality=quality)
    elif fmt_key == "webp":
        canvas.save(str(out_path), format="WEBP", quality=quality)
    elif fmt_key == "tiff":
        canvas.save(str(out_path), format="TIFF")
    else:
        raise RenderError(f"No save handler for format {fmt_key!r}")

    size_bytes = out_path.stat().st_size
    return {
        "ok": True,
        "path": str(out_path),
        "format": fmt_key,
        "width": w,
        "height": h,
        "size_bytes": size_bytes,
    }
