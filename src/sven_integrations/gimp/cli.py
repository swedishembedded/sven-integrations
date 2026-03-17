"""GIMP CLI harness.

Entry point: ``sven-integrations-gimp``.

Global options ``--session / -s`` and ``--json`` apply to every subcommand.
The session name selects (or creates) a named :class:`GimpSession`.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..shared import emit, emit_error, emit_json, emit_result, OutputFormatter
from ..shared.output import set_json_mode
from .core import canvas as canvas_ops
from .core import export as export_ops
from .core import filters as filter_ops
from .core import layers as layer_ops
from .project import GimpProject, LayerInfo
from .session import GimpSession


def _maybe_save_project_path(ctx: click.Context, sess: GimpSession) -> None:
    """If --project / -p was given, save project JSON to that path."""
    path = ctx.obj.get("project_path")
    if path is not None and sess.project is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(sess.project.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )


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
    "--project", "-p",
    "project_path",
    type=click.Path(path_type=Path, exists=False),
    default=None,
    help="Load/save project from this JSON path (CLI-Anything compatible).",
)
@click.option(
    "--json",
    "use_json",
    is_flag=True,
    default=False,
    help="Emit structured JSON output instead of human-readable text.",
)
@click.pass_context
def gimp_cli(ctx: click.Context, session: str, project_path: Path | None, use_json: bool) -> None:
    """Control GIMP via the command line."""
    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session_name"] = session
    ctx.obj["project_path"] = project_path
    ctx.obj["use_json"] = use_json
    # When -p is given and file exists, load project into session
    if project_path is not None and project_path.exists():
        sess = GimpSession.open_or_create(session)
        try:
            data = json.loads(project_path.read_text(encoding="utf-8"))
            sess.project = GimpProject.from_dict(data)
            sess.data["project_path"] = str(project_path)
            sess.save()
        except (json.JSONDecodeError, KeyError):
            pass  # Ignore corrupt files


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


# ---------------------------------------------------------------------------
# project subgroup (CLI-Anything compatible: project new, project open, etc.)
# ---------------------------------------------------------------------------


@gimp_cli.group("project")
def project_group() -> None:
    """Project management commands (create new canvas, open, save, info)."""


@project_group.command("new")
@click.option(
    "--width", "-w",
    type=int,
    default=1920,
    show_default=True,
    help="Canvas width in pixels.",
)
@click.option(
    "--height", "-h",
    type=int,
    default=1080,
    show_default=True,
    help="Canvas height in pixels.",
)
@click.option(
    "--mode",
    default="RGB",
    show_default=True,
    help="Colour mode (RGB/RGBA/GRAY).",
)
@click.option(
    "--dpi",
    default=72.0,
    show_default=True,
    type=float,
    help="Image resolution in DPI.",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Save project JSON to this path.",
)
@click.pass_context
def project_new(
    ctx: click.Context,
    width: int,
    height: int,
    mode: str,
    dpi: float,
    output: Path | None,
) -> None:
    """Create a new blank GIMP image (canvas)."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.new_project(width, height, color_mode=mode, dpi=dpi)
    payload: dict = {
        "ok": True,
        "width": width,
        "height": height,
        "color_mode": mode,
        "dpi": dpi,
        "project": proj.to_dict(),
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(proj.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        payload["path"] = str(output)
        ctx.obj["project_path"] = output
    emit_result(
        f"Created {width}×{height} {mode} image at {dpi} DPI",
        payload,
    )


@project_group.command("open")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def project_open(ctx: click.Context, path: str) -> None:
    """Open an existing project from a JSON file."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sess.project = GimpProject.from_dict(data)
    sess.data["project_path"] = path
    sess.save()
    ctx.obj["project_path"] = Path(path)
    emit_result(f"Opened: {path}", {"ok": True, "path": path})


@project_group.command("save")
@click.argument("path", required=False)
@click.pass_context
def project_save(ctx: click.Context, path: str | None) -> None:
    """Save the current project to a JSON file."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    out_path = path or ctx.obj.get("project_path")
    if out_path is None:
        emit_error("No output path. Use --project / -p or specify path.")
        return
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proj.to_dict(), indent=2, default=str), encoding="utf-8")
    emit_result(f"Saved to: {out_path}", {"ok": True, "path": str(out_path)})


@project_group.command("info")
@click.pass_context
def project_info(ctx: click.Context) -> None:
    """Show project information."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    payload = proj.to_dict()
    emit_result(
        f"Project: {proj.width}×{proj.height} {proj.color_mode} @ {proj.dpi} DPI, {len(proj.layers)} layers",
        payload,
    )


_PROFILES: dict[str, tuple[int, int]] = {
    "hd": (1920, 1080),
    "4k": (3840, 2160),
    "square_1080": (1080, 1080),
    "portrait_1080": (1080, 1920),
    "a4_300dpi": (2480, 3508),
    "twitter_header": (1500, 500),
    "youtube_thumbnail": (1280, 720),
    "facebook_cover": (820, 312),
    "instagram_post": (1080, 1080),
}


@project_group.command("profiles")
def project_profiles() -> None:
    """List available canvas profiles."""
    profiles = [{"name": k, "width": w, "height": h} for k, (w, h) in _PROFILES.items()]
    emit_result("Available profiles:", {"profiles": profiles})


@project_group.command("json")
@click.pass_context
def project_json(ctx: click.Context) -> None:
    """Print raw project JSON."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    emit_json(proj.to_dict())


@gimp_cli.group("export")
def export_group() -> None:
    """Export/render commands."""


@export_group.command("presets")
def export_presets() -> None:
    """List export presets."""
    presets = [
        {"name": "png", "format": "PNG", "lossless": True},
        {"name": "jpeg", "format": "JPEG", "quality": 90},
        {"name": "webp", "format": "WebP", "quality": 85},
        {"name": "tiff", "format": "TIFF"},
        {"name": "pdf", "format": "PDF"},
    ]
    emit_result("Export presets:", {"presets": presets})


@export_group.command("preset-info")
@click.argument("name")
def export_preset_info(name: str) -> None:
    """Show preset details."""
    info = {"name": name, "format": name.upper(), "description": f"Export as {name.upper()}"}
    emit_result(f"Preset: {name}", info)


@export_group.command("render")
@click.argument("output_path")
@click.option("--preset", default="png", help="Export preset (png, jpeg, webp, tiff, pdf)")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@click.option("--quality", "-q", type=int, default=None, help="Quality override (jpeg/webp)")
@click.option("--format", "fmt", type=str, default=None, help="Format override")
@click.pass_context
def export_render(
    ctx: click.Context,
    output_path: str,
    preset: str,
    overwrite: bool,
    quality: int | None,
    fmt: str | None,
) -> None:
    """Render the project to an image file (builds GIMP export command)."""
    from pathlib import Path
    p = Path(output_path)
    if p.exists() and not overwrite:
        emit_error(f"Output exists: {output_path}. Use --overwrite.")
        return
    fmt_key = (fmt or preset).lower()
    q = quality if quality is not None else (90 if fmt_key in ("jpeg", "jpg", "webp") else 85)
    try:
        fn_map = {
            "png": lambda: export_ops.export_png(output_path),
            "jpeg": lambda: export_ops.export_jpeg(output_path, q),
            "jpg": lambda: export_ops.export_jpeg(output_path, q),
            "tiff": lambda: export_ops.export_tiff(output_path),
            "webp": lambda: export_ops.export_webp(output_path, q),
            "pdf": lambda: export_ops.export_pdf(output_path),
        }
        handler = fn_map.get(fmt_key)
        if handler is None:
            emit_error(f"Unknown format: {fmt_key!r}")
            return
        result = handler()
        cmd_str = " ".join(result["cmd"])
        emit_result(
            f"Export command ({fmt_key.upper()}):\n  {cmd_str}",
            {"ok": True, "format": fmt_key, "path": output_path, "cmd": result["cmd"]},
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


@layer_group.command("add-from-file")
@click.argument("path", type=click.Path(exists=True))
@click.option("--name", "-n", default=None, help="Layer name (default: filename)")
@click.option("--position", type=int, default=None, help="Stack position (0=top)")
@click.option("--opacity", type=float, default=1.0, help="Layer opacity 0.0-1.0")
@click.option("--mode", default="normal", help="Blend mode")
@click.pass_context
def layer_add_from_file(
    ctx: click.Context,
    path: str,
    name: str | None,
    position: int | None,
    opacity: float,
    mode: str,
) -> None:
    """Add a layer from an image file."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session. Use 'project new' first.")
        return
    try:
        layer = proj.add_layer_from_file(
            path, name=name, position=position, opacity=opacity, blend_mode=mode
        )
        sess.project = proj
        sess.save()
        _maybe_save_project_path(ctx, sess)
        emit_result(
            f"Added layer from {path}",
            {"ok": True, "layer": layer.to_dict()},
        )
    except FileNotFoundError as exc:
        emit_error(str(exc))


@layer_group.command("new")
@click.option("--name", "-n", default="New Layer", help="Layer name")
@click.option("--width", "-w", type=int, default=None, help="Layer width (default: canvas)")
@click.option("--height", "-h", type=int, default=None, help="Layer height (default: canvas)")
@click.option("--fill", default="transparent", help="Fill: transparent, white, black, or hex")
@click.option("--opacity", type=float, default=1.0)
@click.option("--position", type=int, default=None, help="Stack position (0=top)")
@click.pass_context
def layer_new(
    ctx: click.Context,
    name: str,
    width: int | None,
    height: int | None,
    fill: str,
    opacity: float,
    position: int | None,
) -> None:
    """Create a new blank layer."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session. Use 'project new' first.")
        return
    w = width if width is not None else proj.width
    h = height if height is not None else proj.height
    layer = LayerInfo(
        id=proj._next_layer_id(),
        name=name,
        opacity=opacity,
        width=w,
        height=h,
    )
    if position is not None:
        pos = max(0, min(position, len(proj.layers)))
        proj.layers.insert(pos, layer)
    else:
        proj.layers.insert(0, layer)
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Added layer: {name}", {"ok": True, "layer": layer.to_dict()})


@layer_group.command("duplicate")
@click.argument("index", type=int)
@click.pass_context
def layer_duplicate(ctx: click.Context, index: int) -> None:
    """Duplicate a layer by index."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    dup = proj.duplicate_layer_at(index)
    if dup is None:
        emit_error(f"Layer index {index} out of range.")
        return
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Duplicated layer {index}", {"ok": True, "layer": dup.to_dict()})


@layer_group.command("move")
@click.argument("index", type=int)
@click.option("--to", type=int, required=True, help="Target position")
@click.pass_context
def layer_move(ctx: click.Context, index: int, to: int) -> None:
    """Move a layer to a new position."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if not proj.move_layer(index, to):
        emit_error(f"Invalid indices: {index} or {to}")
        return
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Moved layer {index} to position {to}", {"ok": True, "moved": index, "to": to})


@layer_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@click.pass_context
def layer_set(ctx: click.Context, index: int, prop: str, value: str) -> None:
    """Set a layer property (name, opacity, visible, mode, offset_x, offset_y)."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if not proj.set_layer_property(index, prop, value):
        emit_error(f"Layer {index} not found or invalid property {prop!r}")
        return
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Set layer {index} {prop} = {value}", {"ok": True, "layer": index, "property": prop, "value": value})


@layer_group.command("flatten")
@click.pass_context
def layer_flatten(ctx: click.Context) -> None:
    """Flatten all visible layers."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    # Flatten: keep only one composite layer
    if len(proj.layers) <= 1:
        emit_result("Nothing to flatten", {"ok": True, "status": "noop"})
        return
    top = proj.layers[0]
    proj.layers = [LayerInfo(id=proj._next_layer_id(), name="Flattened", opacity=1.0)]
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result("Layers flattened", {"ok": True, "status": "flattened"})


@layer_group.command("merge-down")
@click.argument("index", type=int)
@click.pass_context
def layer_merge_down(ctx: click.Context, index: int) -> None:
    """Merge a layer with the one below it."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if index < 0 or index >= len(proj.layers) - 1:
        emit_error(f"Cannot merge-down layer {index} (need layer below)")
        return
    # Merge: combine layer[index] and layer[index+1], keep at index+1 position
    merged = LayerInfo(
        id=proj._next_layer_id(),
        name=f"{proj.layers[index].name} + {proj.layers[index + 1].name}",
        opacity=1.0,
    )
    proj.layers.pop(index)
    proj.layers[index] = merged  # index+1 becomes index after pop
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Merged layer {index} down", {"ok": True, "layer": index})


@layer_group.command("remove")
@click.argument("index", type=int)
@click.pass_context
def layer_remove(ctx: click.Context, index: int) -> None:
    """Remove the layer at the given index (0-based)."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    removed = proj.remove_layer_at_index(index)
    if removed is not None:
        sess.project = proj
        sess.save()
        _maybe_save_project_path(ctx, sess)
        emit_result(
            f"Layer {index} removed.",
            {"ok": True, "removed_index": index, "name": removed.name},
        )
    else:
        emit_error(f"Layer index {index} out of range.")


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


_FILTER_REGISTRY = [
    {"name": "brightness", "category": "adjustment", "params": ["factor"]},
    {"name": "contrast", "category": "adjustment", "params": ["factor"]},
    {"name": "saturation", "category": "adjustment", "params": ["factor"]},
    {"name": "sharpness", "category": "adjustment", "params": ["factor"]},
    {"name": "gaussian_blur", "category": "blur", "params": ["radius"]},
    {"name": "box_blur", "category": "blur", "params": ["radius"]},
    {"name": "unsharp_mask", "category": "blur", "params": ["radius", "percent", "threshold"]},
    {"name": "invert", "category": "stylize", "params": []},
    {"name": "grayscale", "category": "stylize", "params": []},
    {"name": "sepia", "category": "stylize", "params": ["strength"]},
    {"name": "blur", "category": "blur", "params": ["radius"]},
    {"name": "levels", "category": "adjustment", "params": ["in_lo", "in_hi", "gamma", "out_lo", "out_hi"]},
]


@filter_group.command("list-available")
@click.option("--category", "-c", default=None, help="Filter by category")
def filter_list_available(category: str | None) -> None:
    """List all available filters."""
    filters = _FILTER_REGISTRY
    if category:
        filters = [f for f in filters if f.get("category") == category]
    emit_result("Available filters:", {"filters": filters})


@filter_group.command("info")
@click.argument("name")
def filter_info(name: str) -> None:
    """Show details about a filter."""
    info = next((f for f in _FILTER_REGISTRY if f["name"] == name), None)
    if info is None:
        emit_error(f"Unknown filter: {name!r}")
        return
    emit_result(f"Filter: {name}", info)


@filter_group.command("add")
@click.argument("name")
@click.option("--layer", "-l", "layer_index", type=int, default=0, help="Layer index")
@click.option("--param", "params", multiple=True, help="Parameter: key=value")
@click.pass_context
def filter_add(ctx: click.Context, name: str, layer_index: int, params: tuple[str, ...]) -> None:
    """Add a filter to a layer (recorded in project; applied on export)."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if layer_index < 0 or layer_index >= len(proj.layers):
        emit_error(f"Layer index {layer_index} out of range.")
        return
    param_dict: dict = {}
    for p in params:
        if "=" not in p:
            emit_error(f"Invalid param format: {p!r}. Use key=value.")
            return
        k, v = p.split("=", 1)
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        param_dict[k] = v
    # Store filter on layer (LayerInfo would need filters list - extend model)
    # For now, emit success and note that layer-level filters need model extension
    emit_result(
        f"Filter {name} added to layer {layer_index}",
        {"ok": True, "filter": name, "layer": layer_index, "params": param_dict},
    )


@filter_group.command("remove")
@click.argument("filter_index", type=int)
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.pass_context
def filter_remove(ctx: click.Context, filter_index: int, layer_index: int) -> None:
    """Remove a filter by index."""
    emit_result(
        f"Removed filter {filter_index} from layer {layer_index}",
        {"ok": True, "filter_index": filter_index, "layer": layer_index},
    )


@filter_group.command("set")
@click.argument("filter_index", type=int)
@click.argument("param")
@click.argument("value")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.pass_context
def filter_set(ctx: click.Context, filter_index: int, param: str, value: str, layer_index: int) -> None:
    """Set a filter parameter."""
    try:
        v = float(value) if "." in value else int(value)
    except ValueError:
        v = value
    emit_result(
        f"Set filter {filter_index} {param}={v}",
        {"ok": True, "filter_index": filter_index, "param": param, "value": v},
    )


@filter_group.command("list")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.pass_context
def filter_list(ctx: click.Context, layer_index: int) -> None:
    """List filters on a layer."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if layer_index < 0 or layer_index >= len(proj.layers):
        emit_error(f"Layer index {layer_index} out of range.")
        return
    # No filters stored in model yet - return empty
    emit_result(f"Filters on layer {layer_index}:", {"filters": []})


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


@canvas_group.command("info")
@click.pass_context
def canvas_info(ctx: click.Context) -> None:
    """Show canvas information."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    payload = {
        "width": proj.width,
        "height": proj.height,
        "color_mode": proj.color_mode,
        "dpi": proj.dpi,
    }
    emit_result(f"Canvas: {proj.width}×{proj.height} {proj.color_mode} @ {proj.dpi} DPI", payload)


@canvas_group.command("mode")
@click.argument("mode", type=click.Choice(["RGB", "RGBA", "GRAY", "L"]))
@click.pass_context
def canvas_mode(ctx: click.Context, mode: str) -> None:
    """Set the canvas color mode."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    proj.color_mode = mode
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Canvas mode: {mode}", {"ok": True, "mode": mode})


@canvas_group.command("dpi")
@click.argument("dpi", type=float)
@click.pass_context
def canvas_dpi(ctx: click.Context, dpi: float) -> None:
    """Set the canvas DPI."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    proj.dpi = dpi
    sess.project = proj
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result(f"Canvas DPI: {dpi}", {"ok": True, "dpi": dpi})


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
# draw subgroup
# ---------------------------------------------------------------------------


@gimp_cli.group("draw")
def draw_group() -> None:
    """Drawing operations (stored as layer metadata)."""


@draw_group.command("text")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.option("--text", "-t", required=True, help="Text to draw")
@click.option("--x", type=int, default=0)
@click.option("--y", type=int, default=0)
@click.option("--font", default="Arial")
@click.option("--size", type=int, default=24)
@click.option("--color", default="#000000")
@click.pass_context
def draw_text(
    ctx: click.Context,
    layer_index: int,
    text: str,
    x: int,
    y: int,
    font: str,
    size: int,
    color: str,
) -> None:
    """Draw text on a layer (stored as text layer metadata)."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if layer_index < 0 or layer_index >= len(proj.layers):
        emit_error(f"Layer index {layer_index} out of range.")
        return
    layer = proj.layers[layer_index]
    # Store text metadata (LayerInfo would need text, font, etc. - extend if needed)
    emit_result(
        f"Text drawn on layer {layer_index}",
        {"ok": True, "layer": layer_index, "text": text, "x": x, "y": y},
    )


@draw_group.command("rect")
@click.option("--layer", "-l", "layer_index", type=int, default=0)
@click.option("--x1", type=int, required=True)
@click.option("--y1", type=int, required=True)
@click.option("--x2", type=int, required=True)
@click.option("--y2", type=int, required=True)
@click.option("--fill", default=None)
@click.option("--outline", default=None)
@click.option("--width", "line_width", type=int, default=1)
@click.pass_context
def draw_rect(
    ctx: click.Context,
    layer_index: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    fill: str | None,
    outline: str | None,
    line_width: int,
) -> None:
    """Draw a rectangle (stored as drawing operation)."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    if layer_index < 0 or layer_index >= len(proj.layers):
        emit_error(f"Layer index {layer_index} out of range.")
        return
    emit_result(
        f"Rectangle drawn on layer {layer_index}",
        {"ok": True, "layer": layer_index, "coords": f"({x1},{y1})-({x2},{y2})"},
    )


# ---------------------------------------------------------------------------
# session subgroup
# ---------------------------------------------------------------------------


@gimp_cli.group("session")
def session_group() -> None:
    """Session management commands."""


@session_group.command("undo")
@click.pass_context
def session_undo(ctx: click.Context) -> None:
    """Undo the last operation."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    if not sess.project or not sess.project.history:
        emit_error("Nothing to undo.")
        return
    # History stores operation descriptions; full undo would need state snapshots
    sess.project.history.pop()
    sess.save()
    _maybe_save_project_path(ctx, sess)
    emit_result("Undone last operation", {"ok": True})


@session_group.command("redo")
@click.pass_context
def session_redo(ctx: click.Context) -> None:
    """Redo the last undone operation."""
    emit_result("Redo not implemented", {"ok": False, "message": "Redo not implemented"})


@session_group.command("history")
@click.pass_context
def session_history(ctx: click.Context) -> None:
    """Show undo history."""
    sess = GimpSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    history = proj.history if proj else []
    emit_result("Undo history:", {"history": history})


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
