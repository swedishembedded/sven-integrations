"""GIMP CLI harness.

Entry point: ``sven-integrations-gimp``.

Global options ``--session / -s`` and ``--json`` apply to every subcommand.
The session name selects (or creates) a named :class:`GimpSession`.
"""

from __future__ import annotations

import click

from ..shared import emit, emit_error, emit_json, emit_result, OutputFormatter
from ..shared.output import set_json_mode
from .core import canvas as canvas_ops
from .core import export as export_ops
from .core import filters as filter_ops
from .core import layers as layer_ops
from .project import LayerInfo
from .session import GimpSession

# ---------------------------------------------------------------------------
# Root group


@click.group("gimp")
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
    help="Emit structured JSON output instead of human-readable text.",
)
@click.pass_context
def gimp_cli(ctx: click.Context, session: str, use_json: bool) -> None:
    """Control GIMP via the command line."""
    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session_name"] = session
    ctx.obj["use_json"] = use_json


# ---------------------------------------------------------------------------
# new / open / export (top-level commands)


@gimp_cli.command("new")
@click.argument("width", type=int)
@click.argument("height", type=int)
@click.option("--mode", default="RGB", show_default=True, help="Colour mode (RGB/RGBA/GRAY).")
@click.option("--dpi", default=72.0, show_default=True, type=float, help="Image resolution in DPI.")
@click.pass_context
def cmd_new(ctx: click.Context, width: int, height: int, mode: str, dpi: float) -> None:
    """Create a new blank GIMP image."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.new_project(width, height, color_mode=mode, dpi=dpi)
    emit_result(
        f"Created {width}×{height} {mode} image at {dpi} DPI",
        {"ok": True, "width": width, "height": height, "color_mode": mode, "dpi": dpi},
    )


@gimp_cli.command("open")
@click.argument("path")
@click.pass_context
def cmd_open(ctx: click.Context, path: str) -> None:
    """Open an existing image file and record it in the session."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    sess.data["open_path"] = path
    sess.save()
    emit_result(
        f"Recorded '{path}' in session '{sess.name}'.",
        {"ok": True, "path": path, "session": sess.name},
    )


@gimp_cli.command("export")
@click.argument("path")
@click.option(
    "--format", "fmt",
    default="png",
    show_default=True,
    help="Export format: png / jpeg / tiff / webp / pdf.",
)
@click.option("--quality", default=90, show_default=True, type=int, help="Quality (jpeg/webp).")
@click.pass_context
def cmd_export(ctx: click.Context, path: str, fmt: str, quality: int) -> None:
    """Build an export command and display it."""
    try:
        fn_map = {
            "png": lambda: export_ops.export_png(path),
            "jpeg": lambda: export_ops.export_jpeg(path, quality),
            "jpg": lambda: export_ops.export_jpeg(path, quality),
            "tiff": lambda: export_ops.export_tiff(path),
            "webp": lambda: export_ops.export_webp(path, quality),
            "pdf": lambda: export_ops.export_pdf(path),
        }
        handler = fn_map.get(fmt.lower())
        if handler is None:
            emit_error(f"Unknown format: {fmt!r}")
            return
        result = handler()
        cmd_str = " ".join(result["cmd"])
        emit_result(
            f"Export command ({fmt.upper()}):\n  {cmd_str}",
            {"ok": True, "format": fmt, "path": path, "cmd": result["cmd"]},
        )
    except export_ops.ExportError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# layer subgroup


@gimp_cli.group("layer")
def layer_group() -> None:
    """Layer management commands."""


@layer_group.command("add")
@click.argument("name")
@click.argument("width", type=int)
@click.argument("height", type=int)
@click.option("--mode", default="LAYER-MODE-NORMAL-LEGACY", help="Layer blend mode constant.")
@click.pass_context
def layer_add(ctx: click.Context, name: str, width: int, height: int, mode: str) -> None:
    """Add a new layer to the active image."""
    result = layer_ops.create_layer(name, width, height, mode)
    emit_result(
        f"Layer '{name}' ({width}×{height}) — script built.",
        {"ok": True, **result},
    )


@layer_group.command("remove")
@click.argument("layer_id", type=int)
@click.pass_context
def layer_remove(ctx: click.Context, layer_id: int) -> None:
    """Remove the layer with the given ID from the session project."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    removed = proj.remove_layer(layer_id)
    if removed:
        sess.project = proj
        sess.save()
        emit_result(
            f"Layer {layer_id} removed.",
            {"ok": True, "layer_id": layer_id},
        )
    else:
        emit_error(f"Layer {layer_id} not found in session project.")


@layer_group.command("list")
@click.pass_context
def layer_list(ctx: click.Context) -> None:
    """List all layers in the session project."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for lyr in proj.layers:
        fmt.record(
            id=lyr.id,
            name=lyr.name,
            opacity=lyr.opacity,
            visible=lyr.visible,
            blend_mode=lyr.blend_mode,
        )
    fmt.flush()


@layer_group.command("opacity")
@click.argument("layer_id", type=int)
@click.argument("value", type=float)
@click.pass_context
def layer_opacity(ctx: click.Context, layer_id: int, value: float) -> None:
    """Set the opacity of a layer (0.0–1.0)."""
    try:
        result = layer_ops.set_layer_opacity(layer_id, value)
    except ValueError as exc:
        emit_error(str(exc))
        return
    emit_result(
        f"Layer {layer_id} opacity → {value:.0%}",
        {"ok": True, "layer_id": layer_id, "opacity": value},
    )


# ---------------------------------------------------------------------------
# filter subgroup


@gimp_cli.group("filter")
def filter_group() -> None:
    """Image filter commands."""


@filter_group.command("blur")
@click.argument("radius", type=float)
def filter_blur(radius: float) -> None:
    """Apply Gaussian blur."""
    result = filter_ops.apply_blur(radius)
    emit_result(
        f"Blur (r={radius}) script ready.",
        {"ok": True, **result},
    )


@filter_group.command("sharpen")
@click.argument("amount", type=float)
def filter_sharpen(amount: float) -> None:
    """Apply sharpen filter."""
    result = filter_ops.apply_sharpen(amount)
    emit_result(
        f"Sharpen (amount={amount}) script ready.",
        {"ok": True, **result},
    )


@filter_group.command("levels")
@click.argument("in_lo", type=int)
@click.argument("in_hi", type=int)
@click.argument("gamma", type=float)
@click.argument("out_lo", type=int)
@click.argument("out_hi", type=int)
def filter_levels(
    in_lo: int, in_hi: int, gamma: float, out_lo: int, out_hi: int
) -> None:
    """Adjust tonal levels."""
    result = filter_ops.apply_levels((in_lo, in_hi, gamma), (out_lo, out_hi))
    emit_result(
        f"Levels adjusted (in={in_lo}–{in_hi} γ={gamma}, out={out_lo}–{out_hi}).",
        {"ok": True, **result},
    )


@filter_group.command("curves")
@click.argument("channel")
@click.argument("points", nargs=-1, type=int)
def filter_curves(channel: str, points: tuple[int, ...]) -> None:
    """Apply a spline curve.  POINTS are interleaved input/output pairs."""
    if len(points) % 2 != 0:
        emit_error("Points must come in input/output pairs (even count).")
        return
    control = [(points[i], points[i + 1]) for i in range(0, len(points), 2)]
    result = filter_ops.apply_curves(channel, control)
    emit_result(
        f"Curves applied to {channel} with {len(control)} control points.",
        {"ok": True, **result},
    )


# ---------------------------------------------------------------------------
# canvas subgroup


@gimp_cli.group("canvas")
def canvas_group() -> None:
    """Canvas geometry commands."""


@canvas_group.command("crop")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.argument("width", type=int)
@click.argument("height", type=int)
def canvas_crop(x: int, y: int, width: int, height: int) -> None:
    """Crop the canvas."""
    result = canvas_ops.crop(x, y, width, height)
    emit_result(
        f"Crop to {width}×{height} at ({x},{y}).",
        {"ok": True, **result},
    )


@canvas_group.command("resize")
@click.argument("width", type=int)
@click.argument("height", type=int)
@click.option("--offset-x", default=0, type=int)
@click.option("--offset-y", default=0, type=int)
def canvas_resize(width: int, height: int, offset_x: int, offset_y: int) -> None:
    """Resize the canvas without scaling content."""
    result = canvas_ops.resize_canvas(width, height, offset_x, offset_y)
    emit_result(
        f"Canvas resized to {width}×{height}.",
        {"ok": True, **result},
    )


@canvas_group.command("scale")
@click.argument("width", type=int)
@click.argument("height", type=int)
@click.option("--interp", default="INTERPOLATION-LINEAR", help="Interpolation method.")
def canvas_scale(width: int, height: int, interp: str) -> None:
    """Scale the image to new dimensions."""
    result = canvas_ops.scale_image(width, height, interp)
    emit_result(
        f"Image scaled to {width}×{height}.",
        {"ok": True, **result},
    )


@canvas_group.command("rotate")
@click.argument("angle", type=float)
@click.option("--auto-crop", is_flag=True, default=False, help="Trim to rotated bounds.")
def canvas_rotate(angle: float, auto_crop: bool) -> None:
    """Rotate the active drawable."""
    result = canvas_ops.rotate(angle, auto_crop)
    emit_result(
        f"Rotated {angle}°.",
        {"ok": True, **result},
    )


# ---------------------------------------------------------------------------
# session subgroup


@gimp_cli.group("session")
def session_group() -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Display the contents of the active session."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    payload: dict = {
        "session": sess.name,
        "harness": sess.harness,
        "project": proj.to_dict() if proj else None,
    }
    emit_result(
        f"Session '{sess.name}' — project: {'yes' if proj else 'none'}",
        payload,
    )


@session_group.command("list")
def session_list() -> None:
    """List all GIMP sessions."""
    names = GimpSession.list_sessions()
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
    sess = GimpSession(name)
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


@gimp_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Launch the interactive GIMP console."""
    from .console import GimpConsole
    GimpConsole(session_name=ctx.obj["session_name"]).cmdloop()


# ---------------------------------------------------------------------------
# Entry point


def main() -> None:
    gimp_cli()
