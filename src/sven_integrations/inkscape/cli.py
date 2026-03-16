"""Inkscape CLI harness.

Entry point: ``sven-integrations-inkscape``.

All commands share ``--session / -s`` and ``--json`` global options.
"""

from __future__ import annotations

import sys
from typing import Any

import click

from ..shared import emit, emit_error, emit_json, emit_result, OutputFormatter
from ..shared.output import set_json_mode
from .core import elements as elem_ops
from .core import export as export_ops
from .core import text as text_ops
from .core import document as doc_ops
from .core import shapes as shape_ops
from .core import styles as style_ops
from .core import transforms as transform_ops
from .core import layers as layer_ops
from .core import paths as path_ops
from .core import gradients as gradient_ops
from .project import InkscapeProject, SvgElement
from .session import InkscapeSession


# ---------------------------------------------------------------------------
# Shared helpers


def _get_session(ctx: click.Context) -> InkscapeSession:
    return InkscapeSession.open_or_create(ctx.obj["session_name"])


def _require_project(ctx: click.Context) -> tuple[InkscapeSession, InkscapeProject]:
    sess = _get_session(ctx)
    proj = sess.project
    if proj is None:
        emit_error("No project in session.  Use 'document new' or 'open' first.")
        sys.exit(1)
    return sess, proj


def _save_project(sess: InkscapeSession, proj: InkscapeProject) -> None:
    sess.project = proj
    sess.save()


# ---------------------------------------------------------------------------
# Root group


@click.group("inkscape")
@click.option(
    "--session", "-s",
    default="default",
    show_default=True,
    help="Session name (workspace identifier).",
)
@click.option(
    "--json",
    "use_json",
    is_flag=True,
    default=False,
    help="Emit structured JSON output.",
)
@click.pass_context
def inkscape_cli(ctx: click.Context, session: str, use_json: bool) -> None:
    """Control Inkscape from the command line."""
    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session_name"] = session
    ctx.obj["use_json"] = use_json


# ---------------------------------------------------------------------------
# open (top-level)


@inkscape_cli.command("open")
@click.argument("path")
@click.option("--width", type=float, default=210.0, show_default=True, help="Document width in mm.")
@click.option("--height", type=float, default=297.0, show_default=True, help="Document height in mm.")
@click.pass_context
def cmd_open(ctx: click.Context, path: str, width: float, height: float) -> None:
    """Record an SVG file in the active session."""
    sess = _get_session(ctx)
    sess.open_document(path, width_mm=width, height_mm=height)
    emit_result(
        f"Opened '{path}' ({width}×{height} mm) in session '{sess.name}'.",
        {"ok": True, "path": path, "session": sess.name},
    )


# ---------------------------------------------------------------------------
# export (top-level)


@inkscape_cli.command("export")
@click.argument("out_path")
@click.option(
    "--format", "fmt",
    default="png",
    show_default=True,
    help="Export format: png / pdf / eps / emf / svg.",
)
@click.option("--dpi", default=96.0, show_default=True, type=float, help="DPI for PNG export.")
@click.pass_context
def cmd_export(ctx: click.Context, out_path: str, fmt: str, dpi: float) -> None:
    """Export the active SVG document."""
    sess, proj = _require_project(ctx)
    if proj.svg_path is None:
        emit_error("No SVG file path set.  Use 'open' or 'document save' first.")
        return
    svg = proj.svg_path
    try:
        fn_map = {
            "png": lambda: export_ops.export_png(svg, out_path, dpi=dpi),
            "pdf": lambda: export_ops.export_pdf(svg, out_path),
            "eps": lambda: export_ops.export_eps(svg, out_path),
            "emf": lambda: export_ops.export_emf(svg, out_path),
        }
        handler = fn_map.get(fmt.lower())
        if handler is None:
            emit_error(f"Unknown format: {fmt!r}")
            return
        result = handler()
        emit_result(
            f"Export ({fmt.upper()}) → {out_path}",
            {"ok": True, "format": fmt, "out_path": out_path, "actions": result["actions"]},
        )
    except export_ops.ExportError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# document subgroup


@inkscape_cli.group("document")
def document_group() -> None:
    """Document-level operations: create, inspect, resize, save."""


@document_group.command("new")
@click.option("--name", default="untitled", show_default=True, help="Document name.")
@click.option("--width", "width_mm", type=float, default=210.0, show_default=True)
@click.option("--height", "height_mm", type=float, default=297.0, show_default=True)
@click.option("--units", default="mm", show_default=True)
@click.option("--background", default="white", show_default=True)
@click.option("--profile", default=None, help="Named profile key (overrides width/height).")
@click.option("--output", "svg_path", default=None, help="Optional SVG file path to associate.")
@click.pass_context
def document_new(
    ctx: click.Context,
    name: str,
    width_mm: float,
    height_mm: float,
    units: str,
    background: str,
    profile: str | None,
    svg_path: str | None,
) -> None:
    """Create a new document in the current session."""
    if profile is not None:
        if profile not in doc_ops.DOCUMENT_PROFILES:
            emit_error(f"Unknown profile {profile!r}. Use 'document profiles' to list them.")
            return
        p = doc_ops.DOCUMENT_PROFILES[profile]
        width_mm, height_mm = p.width_mm, p.height_mm

    proj = doc_ops.new_document(name, width_mm, height_mm, units=units, background=background)
    if svg_path:
        proj.svg_path = svg_path

    sess = _get_session(ctx)
    _save_project(sess, proj)
    emit_result(
        f"New document '{name}' ({width_mm}×{height_mm} {units})",
        {"ok": True, **doc_ops.get_document_info(proj)},
    )


@document_group.command("info")
@click.pass_context
def document_info(ctx: click.Context) -> None:
    """Show document dimensions, viewbox, and element count."""
    sess, proj = _require_project(ctx)
    info = doc_ops.get_document_info(proj)
    emit_result(
        f"Document: {info.get('name', '')} — {info['width_mm']}×{info['height_mm']} "
        f"({info['element_count']} elements, {info['page_layer_count']} layers)",
        info,
    )


@document_group.command("canvas-size")
@click.option("--width", "width_mm", type=float, required=True)
@click.option("--height", "height_mm", type=float, required=True)
@click.pass_context
def document_canvas_size(ctx: click.Context, width_mm: float, height_mm: float) -> None:
    """Resize the canvas."""
    sess, proj = _require_project(ctx)
    result = doc_ops.set_canvas_size(proj, width_mm, height_mm)
    _save_project(sess, proj)
    emit_result(
        f"Canvas resized to {width_mm}×{height_mm}",
        {"ok": True, **result},
    )


@document_group.command("profiles")
def document_profiles() -> None:
    """List all built-in document profiles."""
    profiles = doc_ops.list_profiles()
    fmt = OutputFormatter()
    for p in profiles:
        fmt.record(**p)
    fmt.flush()


@document_group.command("save")
@click.argument("path", required=False, default=None)
@click.pass_context
def document_save(ctx: click.Context, path: str | None) -> None:
    """Generate SVG XML and write it to PATH (or the session's svg_path)."""
    sess, proj = _require_project(ctx)
    target = path or proj.svg_path
    if not target:
        emit_error("No output path specified and no svg_path set in session.")
        return
    result = doc_ops.save_svg(proj, target)
    proj.svg_path = target
    _save_project(sess, proj)
    emit_result(
        f"Saved SVG → {target} ({result['element_count']} elements)",
        {"ok": True, **result},
    )


# ---------------------------------------------------------------------------
# shape subgroup


@inkscape_cli.group("shape")
def shape_group() -> None:
    """Create and manage SVG shapes."""


@shape_group.command("add-rect")
@click.option("--x", type=float, required=True)
@click.option("--y", type=float, required=True)
@click.option("--width", "w", type=float, required=True)
@click.option("--height", "h", type=float, required=True)
@click.option("--rx", type=float, default=0)
@click.option("--ry", type=float, default=0)
@click.option("--name", default=None)
@click.option("--fill", default="none", show_default=True)
@click.option("--stroke", default="black", show_default=True)
@click.option("--stroke-width", "stroke_width", type=float, default=1.0)
@click.option("--layer", "layer_index", type=int, default=0)
@click.pass_context
def shape_add_rect(
    ctx: click.Context,
    x: float, y: float, w: float, h: float,
    rx: float, ry: float, name: str | None,
    fill: str, stroke: str, stroke_width: float, layer_index: int,
) -> None:
    """Add a rectangle."""
    sess, proj = _require_project(ctx)
    result = shape_ops.add_rect(proj, x, y, w, h, rx=rx, ry=ry, name=name,
                                fill=fill, stroke=stroke, stroke_width=stroke_width,
                                layer_index=layer_index)
    _save_project(sess, proj)
    emit_result(f"Added rect {result['element_id']}", {"ok": True, **result})


@shape_group.command("add-circle")
@click.option("--cx", type=float, required=True)
@click.option("--cy", type=float, required=True)
@click.option("--r", type=float, required=True)
@click.option("--name", default=None)
@click.option("--fill", default="none")
@click.option("--stroke", default="black")
@click.option("--stroke-width", "stroke_width", type=float, default=1.0)
@click.option("--layer", "layer_index", type=int, default=0)
@click.pass_context
def shape_add_circle(
    ctx: click.Context,
    cx: float, cy: float, r: float,
    name: str | None, fill: str, stroke: str, stroke_width: float, layer_index: int,
) -> None:
    """Add a circle."""
    sess, proj = _require_project(ctx)
    result = shape_ops.add_circle(proj, cx, cy, r, name=name,
                                  fill=fill, stroke=stroke,
                                  stroke_width=stroke_width, layer_index=layer_index)
    _save_project(sess, proj)
    emit_result(f"Added circle {result['element_id']}", {"ok": True, **result})


@shape_group.command("add-ellipse")
@click.option("--cx", type=float, required=True)
@click.option("--cy", type=float, required=True)
@click.option("--rx", type=float, required=True)
@click.option("--ry", type=float, required=True)
@click.option("--name", default=None)
@click.option("--fill", default="none")
@click.option("--stroke", default="black")
@click.option("--stroke-width", "stroke_width", type=float, default=1.0)
@click.pass_context
def shape_add_ellipse(
    ctx: click.Context,
    cx: float, cy: float, rx: float, ry: float,
    name: str | None, fill: str, stroke: str, stroke_width: float,
) -> None:
    """Add an ellipse."""
    sess, proj = _require_project(ctx)
    result = shape_ops.add_ellipse(proj, cx, cy, rx, ry, name=name,
                                   fill=fill, stroke=stroke, stroke_width=stroke_width)
    _save_project(sess, proj)
    emit_result(f"Added ellipse {result['element_id']}", {"ok": True, **result})


@shape_group.command("add-line")
@click.option("--x1", type=float, required=True)
@click.option("--y1", type=float, required=True)
@click.option("--x2", type=float, required=True)
@click.option("--y2", type=float, required=True)
@click.option("--name", default=None)
@click.option("--stroke", default="black")
@click.option("--stroke-width", "stroke_width", type=float, default=1.0)
@click.pass_context
def shape_add_line(
    ctx: click.Context,
    x1: float, y1: float, x2: float, y2: float,
    name: str | None, stroke: str, stroke_width: float,
) -> None:
    """Add a line."""
    sess, proj = _require_project(ctx)
    result = shape_ops.add_line(proj, x1, y1, x2, y2, name=name,
                                stroke=stroke, stroke_width=stroke_width)
    _save_project(sess, proj)
    emit_result(f"Added line {result['element_id']}", {"ok": True, **result})


@shape_group.command("add-polygon")
@click.option("--points", required=True, help="Space-separated x,y pairs, e.g. '0,0 50,100 100,0'.")
@click.option("--name", default=None)
@click.option("--fill", default="none")
@click.option("--stroke", default="black")
@click.option("--stroke-width", "stroke_width", type=float, default=1.0)
@click.pass_context
def shape_add_polygon(
    ctx: click.Context,
    points: str,
    name: str | None, fill: str, stroke: str, stroke_width: float,
) -> None:
    """Add a polygon.  --points accepts 'x1,y1 x2,y2 ...' format."""
    parsed: list[tuple[float, float]] = []
    for pair in points.split():
        xs, ys = pair.split(",")
        parsed.append((float(xs), float(ys)))
    sess, proj = _require_project(ctx)
    result = shape_ops.add_polygon(proj, parsed, name=name,
                                   fill=fill, stroke=stroke, stroke_width=stroke_width)
    _save_project(sess, proj)
    emit_result(f"Added polygon {result['element_id']}", {"ok": True, **result})


@shape_group.command("add-path")
@click.option("--d", required=True, help="SVG path data string.")
@click.option("--name", default=None)
@click.option("--fill", default="none")
@click.option("--stroke", default="black")
@click.option("--stroke-width", "stroke_width", type=float, default=1.0)
@click.pass_context
def shape_add_path(
    ctx: click.Context,
    d: str, name: str | None, fill: str, stroke: str, stroke_width: float,
) -> None:
    """Add a raw SVG path element."""
    sess, proj = _require_project(ctx)
    result = shape_ops.add_path(proj, d, name=name,
                                fill=fill, stroke=stroke, stroke_width=stroke_width)
    _save_project(sess, proj)
    emit_result(f"Added path {result['element_id']}", {"ok": True, **result})


@shape_group.command("add-star")
@click.option("--cx", type=float, required=True)
@click.option("--cy", type=float, required=True)
@click.option("--points", "num_points", type=int, default=5, show_default=True)
@click.option("--outer-radius", "outer_radius", type=float, required=True)
@click.option("--inner-radius", "inner_radius", type=float, required=True)
@click.option("--name", default=None)
@click.option("--fill", default="none")
@click.option("--stroke", default="black")
@click.pass_context
def shape_add_star(
    ctx: click.Context,
    cx: float, cy: float, num_points: int,
    outer_radius: float, inner_radius: float,
    name: str | None, fill: str, stroke: str,
) -> None:
    """Add a regular star polygon."""
    sess, proj = _require_project(ctx)
    result = shape_ops.add_star(proj, cx, cy, num_points, outer_radius, inner_radius,
                                name=name, fill=fill, stroke=stroke)
    _save_project(sess, proj)
    emit_result(f"Added star {result['element_id']}", {"ok": True, **result})


@shape_group.command("remove")
@click.argument("element_id")
@click.pass_context
def shape_remove(ctx: click.Context, element_id: str) -> None:
    """Remove a shape by id."""
    sess, proj = _require_project(ctx)
    removed = proj.remove_element(element_id)
    _save_project(sess, proj)
    if removed:
        emit_result(f"Removed element {element_id!r}", {"ok": True, "element_id": element_id})
    else:
        emit_error(f"Element {element_id!r} not found.")


@shape_group.command("duplicate")
@click.argument("element_id")
@click.pass_context
def shape_duplicate(ctx: click.Context, element_id: str) -> None:
    """Duplicate an element (builds Inkscape action list)."""
    result = elem_ops.duplicate_element(element_id)
    emit_result(
        f"Duplicate '#{element_id}' — actions built.",
        {"ok": True, "element_id": element_id, "actions": result["actions"]},
    )


@shape_group.command("list")
@click.pass_context
def shape_list(ctx: click.Context) -> None:
    """List all shapes/elements in the current project."""
    sess, proj = _require_project(ctx)
    objects = shape_ops.list_objects(proj)
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for obj in objects:
        fmt.record(**obj)
    fmt.flush()
    if not objects:
        emit("(no elements)")


@shape_group.command("get")
@click.argument("element_id")
@click.pass_context
def shape_get(ctx: click.Context, element_id: str) -> None:
    """Show details for a single element."""
    sess, proj = _require_project(ctx)
    elem = proj.find_by_id(element_id)
    if elem is None:
        emit_error(f"Element {element_id!r} not found.")
        return
    emit_result(f"Element {element_id}", elem.to_dict())


# ---------------------------------------------------------------------------
# style subgroup


@inkscape_cli.group("style")
def style_group() -> None:
    """CSS style property operations."""


@style_group.command("fill")
@click.argument("element_id")
@click.argument("color")
@click.pass_context
def style_fill(ctx: click.Context, element_id: str, color: str) -> None:
    """Set the fill colour of an element."""
    sess, proj = _require_project(ctx)
    try:
        result = style_ops.set_fill(proj, element_id, color)
        _save_project(sess, proj)
        emit_result(f"Fill {element_id!r} → {color}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@style_group.command("stroke")
@click.argument("element_id")
@click.argument("color")
@click.option("--width", type=float, default=None)
@click.pass_context
def style_stroke(ctx: click.Context, element_id: str, color: str, width: float | None) -> None:
    """Set the stroke colour and optional width of an element."""
    sess, proj = _require_project(ctx)
    try:
        result = style_ops.set_stroke(proj, element_id, color, width)
        _save_project(sess, proj)
        emit_result(f"Stroke {element_id!r} → {color}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@style_group.command("opacity")
@click.argument("element_id")
@click.argument("value", type=float)
@click.pass_context
def style_opacity(ctx: click.Context, element_id: str, value: float) -> None:
    """Set the opacity of an element (0.0–1.0)."""
    sess, proj = _require_project(ctx)
    try:
        result = style_ops.set_opacity(proj, element_id, value)
        _save_project(sess, proj)
        emit_result(f"Opacity {element_id!r} → {value}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@style_group.command("set")
@click.argument("element_id")
@click.argument("prop")
@click.argument("value")
@click.pass_context
def style_set(ctx: click.Context, element_id: str, prop: str, value: str) -> None:
    """Set an arbitrary CSS property on an element."""
    sess, proj = _require_project(ctx)
    try:
        result = style_ops.set_style_property(proj, element_id, prop, value)
        _save_project(sess, proj)
        emit_result(f"Style {element_id!r} {prop}={value}", {"ok": True, **result})
    except (KeyError, ValueError) as exc:
        emit_error(str(exc))


@style_group.command("get")
@click.argument("element_id")
@click.pass_context
def style_get(ctx: click.Context, element_id: str) -> None:
    """Get the parsed style properties of an element."""
    sess, proj = _require_project(ctx)
    try:
        result = style_ops.get_element_style(proj, element_id)
        emit_result(f"Style for {element_id!r}", result)
    except KeyError as exc:
        emit_error(str(exc))


@style_group.command("properties")
def style_properties() -> None:
    """List all supported CSS style properties."""
    props = style_ops.list_style_properties()
    fmt = OutputFormatter()
    for p in props:
        fmt.record(**p)
    fmt.flush()


# ---------------------------------------------------------------------------
# transform subgroup


@inkscape_cli.group("transform")
def transform_group() -> None:
    """SVG transform operations on elements."""


@transform_group.command("translate")
@click.argument("element_id")
@click.argument("tx", type=float)
@click.option("--ty", type=float, default=0.0, show_default=True)
@click.pass_context
def transform_translate(ctx: click.Context, element_id: str, tx: float, ty: float) -> None:
    """Append a translate transform."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.translate(proj, element_id, tx, ty)
        _save_project(sess, proj)
        emit_result(f"Translate {element_id!r} by ({tx},{ty})", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@transform_group.command("rotate")
@click.argument("element_id")
@click.argument("angle", type=float)
@click.option("--cx", type=float, default=0.0)
@click.option("--cy", type=float, default=0.0)
@click.pass_context
def transform_rotate(ctx: click.Context, element_id: str, angle: float, cx: float, cy: float) -> None:
    """Append a rotate transform."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.rotate(proj, element_id, angle, cx, cy)
        _save_project(sess, proj)
        emit_result(f"Rotate {element_id!r} by {angle}°", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@transform_group.command("scale")
@click.argument("element_id")
@click.argument("sx", type=float)
@click.option("--sy", type=float, default=None)
@click.pass_context
def transform_scale(ctx: click.Context, element_id: str, sx: float, sy: float | None) -> None:
    """Append a scale transform."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.scale(proj, element_id, sx, sy)
        _save_project(sess, proj)
        emit_result(f"Scale {element_id!r} ({sx},{result.get('sy', sx)})", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@transform_group.command("skew-x")
@click.argument("element_id")
@click.argument("angle", type=float)
@click.pass_context
def transform_skew_x(ctx: click.Context, element_id: str, angle: float) -> None:
    """Append a skewX transform."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.skew_x(proj, element_id, angle)
        _save_project(sess, proj)
        emit_result(f"SkewX {element_id!r} {angle}°", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@transform_group.command("skew-y")
@click.argument("element_id")
@click.argument("angle", type=float)
@click.pass_context
def transform_skew_y(ctx: click.Context, element_id: str, angle: float) -> None:
    """Append a skewY transform."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.skew_y(proj, element_id, angle)
        _save_project(sess, proj)
        emit_result(f"SkewY {element_id!r} {angle}°", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@transform_group.command("get")
@click.argument("element_id")
@click.pass_context
def transform_get(ctx: click.Context, element_id: str) -> None:
    """Show the current transform of an element."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.get_transform(proj, element_id)
        emit_result(f"Transform of {element_id!r}: {result['raw_string']}", result)
    except KeyError as exc:
        emit_error(str(exc))


@transform_group.command("clear")
@click.argument("element_id")
@click.pass_context
def transform_clear(ctx: click.Context, element_id: str) -> None:
    """Remove all transforms from an element."""
    sess, proj = _require_project(ctx)
    try:
        result = transform_ops.clear_transform(proj, element_id)
        _save_project(sess, proj)
        emit_result(f"Cleared transform on {element_id!r}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# layer subgroup


@inkscape_cli.group("layer")
def layer_group() -> None:
    """Layer management commands."""


@layer_group.command("add")
@click.option("--name", required=True, help="Layer name.")
@click.option("--visible/--hidden", default=True)
@click.option("--locked/--unlocked", default=False)
@click.option("--opacity", type=float, default=1.0)
@click.option("--position", type=int, default=None, help="Insert at index (append if omitted).")
@click.pass_context
def layer_add(
    ctx: click.Context,
    name: str, visible: bool, locked: bool, opacity: float, position: int | None,
) -> None:
    """Add a new layer."""
    sess, proj = _require_project(ctx)
    result = layer_ops.add_layer(proj, name, visible=visible, locked=locked,
                                 opacity=opacity, position=position)
    _save_project(sess, proj)
    emit_result(f"Added layer '{name}' at index {result['index']}", {"ok": True, **result})


@layer_group.command("remove")
@click.argument("index", type=int)
@click.pass_context
def layer_remove(ctx: click.Context, index: int) -> None:
    """Remove the layer at INDEX."""
    sess, proj = _require_project(ctx)
    try:
        result = layer_ops.remove_layer(proj, index)
        _save_project(sess, proj)
        emit_result(f"Removed layer at index {index}", {"ok": True, **result})
    except IndexError as exc:
        emit_error(str(exc))


@layer_group.command("move-element")
@click.argument("element_id")
@click.argument("layer_index", type=int)
@click.pass_context
def layer_move_element(ctx: click.Context, element_id: str, layer_index: int) -> None:
    """Move ELEMENT_ID to the layer at LAYER_INDEX."""
    sess, proj = _require_project(ctx)
    try:
        result = layer_ops.move_to_layer(proj, element_id, layer_index)
        _save_project(sess, proj)
        emit_result(f"Moved {element_id!r} to layer {layer_index}", {"ok": True, **result})
    except (IndexError, KeyError) as exc:
        emit_error(str(exc))


@layer_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@click.pass_context
def layer_set(ctx: click.Context, index: int, prop: str, value: str) -> None:
    """Set a property on a layer (visible, locked, opacity, name)."""
    sess, proj = _require_project(ctx)
    try:
        parsed_value: Any = value
        if prop in ("visible", "locked"):
            parsed_value = value.lower() in ("true", "1", "yes")
        elif prop == "opacity":
            parsed_value = float(value)
        result = layer_ops.set_layer_property(proj, index, prop, parsed_value)
        _save_project(sess, proj)
        emit_result(f"Layer {index} {prop}={value}", {"ok": True, **result})
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))


@layer_group.command("list")
@click.pass_context
def layer_list(ctx: click.Context) -> None:
    """List all layers."""
    sess, proj = _require_project(ctx)
    result = layer_ops.list_layers(proj)
    emit_result(
        f"{result['layer_count']} layer(s)",
        result,
    )


@layer_group.command("reorder")
@click.argument("from_index", type=int)
@click.argument("to_index", type=int)
@click.pass_context
def layer_reorder(ctx: click.Context, from_index: int, to_index: int) -> None:
    """Move the layer at FROM_INDEX to TO_INDEX."""
    sess, proj = _require_project(ctx)
    try:
        result = layer_ops.reorder_layers(proj, from_index, to_index)
        _save_project(sess, proj)
        emit_result(
            f"Reordered layer {from_index} → {to_index}",
            {"ok": True, **result},
        )
    except IndexError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# path subgroup


@inkscape_cli.group("path")
def path_group() -> None:
    """Boolean path operations and shape-to-path conversion."""


@path_group.command("union")
@click.argument("id_a")
@click.argument("id_b")
@click.option("--name", "result_name", default=None)
@click.pass_context
def path_union(ctx: click.Context, id_a: str, id_b: str, result_name: str | None) -> None:
    """Combine two paths with a boolean union."""
    sess, proj = _require_project(ctx)
    try:
        result = path_ops.path_union(proj, id_a, id_b, result_name)
        _save_project(sess, proj)
        emit_result(f"Union {id_a} ∪ {id_b} → {result['result_id']}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@path_group.command("intersection")
@click.argument("id_a")
@click.argument("id_b")
@click.option("--name", "result_name", default=None)
@click.pass_context
def path_intersection(ctx: click.Context, id_a: str, id_b: str, result_name: str | None) -> None:
    """Intersect two paths."""
    sess, proj = _require_project(ctx)
    try:
        result = path_ops.path_intersection(proj, id_a, id_b, result_name)
        _save_project(sess, proj)
        emit_result(f"Intersection {id_a} ∩ {id_b} → {result['result_id']}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@path_group.command("difference")
@click.argument("id_a")
@click.argument("id_b")
@click.option("--name", "result_name", default=None)
@click.pass_context
def path_difference(ctx: click.Context, id_a: str, id_b: str, result_name: str | None) -> None:
    """Subtract id_b from id_a (difference)."""
    sess, proj = _require_project(ctx)
    try:
        result = path_ops.path_difference(proj, id_a, id_b, result_name)
        _save_project(sess, proj)
        emit_result(f"Difference {id_a} − {id_b} → {result['result_id']}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@path_group.command("exclusion")
@click.argument("id_a")
@click.argument("id_b")
@click.option("--name", "result_name", default=None)
@click.pass_context
def path_exclusion(ctx: click.Context, id_a: str, id_b: str, result_name: str | None) -> None:
    """XOR-combine two paths (exclusion)."""
    sess, proj = _require_project(ctx)
    try:
        result = path_ops.path_exclusion(proj, id_a, id_b, result_name)
        _save_project(sess, proj)
        emit_result(f"Exclusion {id_a} ⊕ {id_b} → {result['result_id']}", {"ok": True, **result})
    except KeyError as exc:
        emit_error(str(exc))


@path_group.command("convert")
@click.argument("element_id")
@click.pass_context
def path_convert(ctx: click.Context, element_id: str) -> None:
    """Convert a shape element to a path."""
    sess, proj = _require_project(ctx)
    try:
        result = path_ops.convert_to_path(proj, element_id)
        _save_project(sess, proj)
        emit_result(f"Converted {element_id!r} to path", {"ok": True, **result})
    except (KeyError, ValueError) as exc:
        emit_error(str(exc))


@path_group.command("operations")
def path_operations() -> None:
    """List available path boolean operations."""
    ops = path_ops.list_path_operations()
    fmt = OutputFormatter()
    for op in ops:
        fmt.record(**op)
    fmt.flush()


# ---------------------------------------------------------------------------
# gradient subgroup


@inkscape_cli.group("gradient")
def gradient_group() -> None:
    """Create and apply SVG gradients."""


@gradient_group.command("linear")
@click.option("--x1", type=float, default=0.0)
@click.option("--y1", type=float, default=0.0)
@click.option("--x2", type=float, default=1.0)
@click.option("--y2", type=float, default=0.0)
@click.option("--color-start", "color_start", default="white", show_default=True)
@click.option("--color-end", "color_end", default="black", show_default=True)
@click.option("--name", default=None)
@click.pass_context
def gradient_linear(
    ctx: click.Context,
    x1: float, y1: float, x2: float, y2: float,
    color_start: str, color_end: str, name: str | None,
) -> None:
    """Add a two-stop linear gradient."""
    stops = [
        {"offset": 0.0, "color": color_start, "opacity": 1.0},
        {"offset": 1.0, "color": color_end, "opacity": 1.0},
    ]
    sess, proj = _require_project(ctx)
    result = gradient_ops.add_linear_gradient(proj, stops, x1=x1, y1=y1, x2=x2, y2=y2, name=name)
    _save_project(sess, proj)
    emit_result(
        f"Linear gradient [{color_start} → {color_end}] at index {result['index']}",
        {"ok": True, **result},
    )


@gradient_group.command("radial")
@click.option("--cx", type=float, default=0.5)
@click.option("--cy", type=float, default=0.5)
@click.option("--r", type=float, default=0.5)
@click.option("--color-start", "color_start", default="white")
@click.option("--color-end", "color_end", default="black")
@click.option("--name", default=None)
@click.pass_context
def gradient_radial(
    ctx: click.Context,
    cx: float, cy: float, r: float,
    color_start: str, color_end: str, name: str | None,
) -> None:
    """Add a two-stop radial gradient."""
    stops = [
        {"offset": 0.0, "color": color_start, "opacity": 1.0},
        {"offset": 1.0, "color": color_end, "opacity": 1.0},
    ]
    sess, proj = _require_project(ctx)
    result = gradient_ops.add_radial_gradient(proj, stops, cx=cx, cy=cy, r=r, name=name)
    _save_project(sess, proj)
    emit_result(
        f"Radial gradient [{color_start} → {color_end}] at index {result['index']}",
        {"ok": True, **result},
    )


@gradient_group.command("apply")
@click.argument("gradient_index", type=int)
@click.argument("element_id")
@click.option("--target", default="fill", show_default=True, help="'fill' or 'stroke'.")
@click.pass_context
def gradient_apply(
    ctx: click.Context, gradient_index: int, element_id: str, target: str,
) -> None:
    """Apply a gradient to an element's fill or stroke."""
    sess, proj = _require_project(ctx)
    try:
        result = gradient_ops.apply_gradient(proj, gradient_index, element_id, target)
        _save_project(sess, proj)
        emit_result(
            f"Applied gradient {gradient_index} to {element_id!r} {target}",
            {"ok": True, **result},
        )
    except (IndexError, KeyError, ValueError) as exc:
        emit_error(str(exc))


@gradient_group.command("list")
@click.pass_context
def gradient_list(ctx: click.Context) -> None:
    """List all gradients in the current project."""
    sess, proj = _require_project(ctx)
    result = gradient_ops.list_gradients(proj)
    emit_result(
        f"{result['gradient_count']} gradient(s)",
        result,
    )


# ---------------------------------------------------------------------------
# element subgroup (legacy — kept for backward compatibility)


@inkscape_cli.group("element")
def element_group() -> None:
    """SVG element manipulation commands."""


@element_group.command("list")
@click.pass_context
def element_list(ctx: click.Context) -> None:
    """List elements tracked in the session project."""
    sess = _get_session(ctx)
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    fmt_out = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for elem in proj.elements:
        fmt_out.record(
            id=elem.element_id,
            tag=elem.tag,
            fill=elem.fill,
            stroke=elem.stroke,
            label=elem.label,
        )
    fmt_out.flush()
    if not proj.elements:
        emit("(no elements tracked)")


@element_group.command("move")
@click.argument("element_id")
@click.argument("dx", type=float)
@click.argument("dy", type=float)
def element_move(element_id: str, dx: float, dy: float) -> None:
    """Translate an element by (dx, dy)."""
    result = elem_ops.move_element(element_id, dx, dy)
    emit_result(
        f"Move '#{element_id}' by ({dx}, {dy}) — actions built.",
        {"ok": True, "element_id": element_id, "actions": result["actions"]},
    )


@element_group.command("scale")
@click.argument("element_id")
@click.argument("sx", type=float)
@click.argument("sy", type=float)
def element_scale(element_id: str, sx: float, sy: float) -> None:
    """Scale an element by (sx, sy)."""
    result = elem_ops.scale_element(element_id, sx, sy)
    emit_result(
        f"Scale '#{element_id}' by ({sx}, {sy}) — actions built.",
        {"ok": True, "element_id": element_id, "actions": result["actions"]},
    )


@element_group.command("rotate")
@click.argument("element_id")
@click.argument("angle", type=float)
@click.option("--cx", default=0.0, type=float, help="Rotation centre X.")
@click.option("--cy", default=0.0, type=float, help="Rotation centre Y.")
def element_rotate(element_id: str, angle: float, cx: float, cy: float) -> None:
    """Rotate an element by the given angle."""
    result = elem_ops.rotate_element(element_id, angle, cx, cy)
    emit_result(
        f"Rotate '#{element_id}' by {angle}° — actions built.",
        {"ok": True, "element_id": element_id, "actions": result["actions"]},
    )


@element_group.command("fill")
@click.argument("element_id")
@click.argument("color")
def element_fill(element_id: str, color: str) -> None:
    """Set the fill colour of an element."""
    elem_ops.set_fill(element_id, color)
    emit_result(
        f"Fill '#{element_id}' → {color}",
        {"ok": True, "element_id": element_id, "color": color},
    )


@element_group.command("stroke")
@click.argument("element_id")
@click.argument("color")
@click.option("--width", default=1.0, type=float, help="Stroke width in user units.")
def element_stroke(element_id: str, color: str, width: float) -> None:
    """Set the stroke colour and width of an element."""
    elem_ops.set_stroke(element_id, color, width)
    emit_result(
        f"Stroke '#{element_id}' → {color} w={width}",
        {"ok": True, "element_id": element_id, "color": color, "width": width},
    )


@element_group.command("delete")
@click.argument("element_id")
@click.pass_context
def element_delete(ctx: click.Context, element_id: str) -> None:
    """Delete an element and remove it from the session."""
    result = elem_ops.delete_element(element_id)
    sess = _get_session(ctx)
    proj = sess.project
    if proj:
        proj.remove_element(element_id)
        _save_project(sess, proj)
    emit_result(
        f"Delete '#{element_id}' — actions built.",
        {"ok": True, "element_id": element_id, "actions": result["actions"]},
    )


# ---------------------------------------------------------------------------
# text subgroup


@inkscape_cli.group("text")
def text_group() -> None:
    """SVG text element commands."""


@text_group.command("add")
@click.argument("x", type=float)
@click.argument("y", type=float)
@click.argument("content")
@click.option("--font", "font_family", default="sans-serif", help="Font family.")
@click.option("--size", "font_size", default=12.0, type=float, help="Font size in px.")
@click.option("--color", default="#000000", help="Text fill colour.")
def text_add(
    x: float, y: float, content: str,
    font_family: str, font_size: float, color: str,
) -> None:
    """Add a text element to the SVG."""
    result = text_ops.add_text(x, y, content, font_family, font_size, color)
    emit_result(
        f"Text '{content[:30]}' at ({x},{y}) — actions built.",
        {"ok": True, **result},
    )


@text_group.command("edit")
@click.argument("element_id")
@click.argument("new_content")
def text_edit(element_id: str, new_content: str) -> None:
    """Replace the text in an existing text element."""
    result = text_ops.edit_text(element_id, new_content)
    emit_result(
        f"Edit text '#{element_id}' — actions built.",
        {"ok": True, **result},
    )


@text_group.command("font")
@click.argument("element_id")
@click.argument("family")
@click.argument("size", type=float)
@click.option("--weight", default="normal", help="Font weight (normal/bold/etc.).")
def text_font(element_id: str, family: str, size: float, weight: str) -> None:
    """Set the font on a text element."""
    result = text_ops.set_font(element_id, family, size, weight)
    emit_result(
        f"Font on '#{element_id}' → {family} {size}px {weight}",
        {"ok": True, **result},
    )


# ---------------------------------------------------------------------------
# session subgroup


@inkscape_cli.group("session")
def session_group() -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Display the contents of the active session."""
    sess = _get_session(ctx)
    proj = sess.project
    payload: dict = {
        "session": sess.name,
        "harness": sess.harness,
        "project": proj.to_dict() if proj else None,
    }
    emit_result(
        f"Session '{sess.name}' — document: {'yes' if proj else 'none'}",
        payload,
    )


@session_group.command("list")
def session_list() -> None:
    """List all Inkscape sessions."""
    names = InkscapeSession.list_sessions()
    fmt = OutputFormatter()
    for name in names:
        fmt.record(session=name)
    fmt.flush()
    if not names:
        emit("(no sessions found)")


@session_group.command("delete")
@click.argument("name")
def session_delete(name: str) -> None:
    """Delete a named session."""
    sess = InkscapeSession(name)
    removed = sess.delete()
    if removed:
        emit_result(
            f"Session '{name}' deleted.",
            {"ok": True, "session": name},
        )
    else:
        emit_error(f"Session '{name}' not found.")


# ---------------------------------------------------------------------------
# repl


@inkscape_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Launch the interactive Inkscape console."""
    from .console import InkscapeConsole
    InkscapeConsole(session_name=ctx.obj["session_name"]).cmdloop()


# ---------------------------------------------------------------------------
# Entry point


def main() -> None:
    inkscape_cli()
