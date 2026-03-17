"""Blender CLI harness.

Entry point: ``sven-integrations-blender``.

All commands share ``--session / -s`` and ``--json`` global options.
"""

from __future__ import annotations

import json as _json

import click

from ..shared import OutputFormatter, cli_main, emit, emit_error, emit_result
from ..shared.output import set_json_mode
from .core import animation as anim_ops
from .core import lighting as light_ops
from .core import materials as mat_ops
from .core import modifiers as mod_ops
from .core import objects as obj_ops
from .project import BlenderProject
from .session import BlenderSession

# ---------------------------------------------------------------------------
# Root group


@click.group("blender")
@click.option(
    "--session", "-s",
    default="default",
    show_default=True,
    help="Session name (workspace identifier).",
)
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option(
    "--json",
    "use_json",
    is_flag=True,
    default=False,
    help="Emit structured JSON output.",
)
@click.pass_context
def blender_cli(
    ctx: click.Context, session: str, project_path: str | None, use_json: bool
) -> None:
    """Control Blender from the command line."""
    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session_name"] = session
    ctx.obj["use_json"] = use_json
    if project_path is not None:
        sess = BlenderSession.open_or_create(session)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# open / render (top-level commands)


@blender_cli.command("open")
@click.argument("path")
@click.pass_context
def cmd_open(ctx: click.Context, path: str) -> None:
    """Record a .blend file path in the active session."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    sess.set_blend_file(path)
    emit_result(
        f"Blend file '{path}' recorded in session '{sess.name}'.",
        {"ok": True, "path": path, "session": sess.name},
    )


@blender_cli.command("render")
@click.option("--frame", type=int, default=None, help="Frame number to render.")
@click.option("--output", "-o", required=True, help="Absolute output file path (e.g. /tmp/render.png).")
@click.pass_context
def cmd_render(ctx: click.Context, frame: int | None, output: str) -> None:
    """Render the scene (or a specific frame)."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    blend = sess.project.blend_file if sess.project else None

    from .backend import BlenderBackend, BlenderError
    backend = BlenderBackend()
    try:
        stdout = backend.render(output, frame=frame, blend_file=blend)
        emit_result(
            f"Rendered {'frame ' + str(frame) if frame else 'active frame'} → {output}",
            {"ok": True, "output": output, "frame": frame, "stdout": stdout},
        )
    except BlenderError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# object subgroup


@blender_cli.group("object")
def object_group() -> None:
    """Scene object commands."""


@object_group.command("add")
@click.argument("mesh_type")
@click.option("--location", "-l", nargs=3, type=float, default=(0, 0, 0), help="X Y Z")
@click.pass_context
def object_add(ctx: click.Context, mesh_type: str, location: tuple[float, float, float]) -> None:
    """Add a primitive mesh object."""
    try:
        result = obj_ops.add_mesh(mesh_type, location)
    except ValueError as exc:
        emit_error(str(exc))
        return
    emit_result(
        f"Add {mesh_type} at {location} — {len(result['statements'])} statements.",
        {"ok": True, **result},
    )


@object_group.command("delete")
@click.argument("name")
@click.pass_context
def object_delete(ctx: click.Context, name: str) -> None:
    """Delete an object from the scene."""
    result = obj_ops.delete_object(name)
    emit_result(
        f"Delete '{name}' script ready.",
        {"ok": True, **result},
    )


@object_group.command("list")
@click.pass_context
def object_list(ctx: click.Context) -> None:
    """List objects tracked in the session project."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for obj in proj.objects:
        fmt.record(
            name=obj.name,
            type=obj.type,
            location=list(obj.location),
            material=obj.material,
        )
    fmt.flush()
    if not proj.objects:
        emit("(no objects in session)")


@object_group.command("move")
@click.argument("name")
@click.argument("x", type=float)
@click.argument("y", type=float)
@click.argument("z", type=float)
@click.pass_context
def object_move(ctx: click.Context, name: str, x: float, y: float, z: float) -> None:
    """Move a tracked session object to new coordinates."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    obj = proj.find_object(name) if proj else None
    if obj is None:
        emit_error(f"Object '{name}' not found in session.")
        return
    obj.location = (x, y, z)
    sess.project = proj
    sess.save()
    emit_result(
        f"Object '{name}' moved to ({x}, {y}, {z}).",
        {"ok": True, "name": name, "location": [x, y, z]},
    )


# ---------------------------------------------------------------------------
# material subgroup


@blender_cli.group("material")
def material_group() -> None:
    """Material management commands."""


@material_group.command("create")
@click.argument("name")
@click.option("--color", nargs=4, type=float, default=(0.8, 0.8, 0.8, 1.0), metavar="R G B A")
def material_create(name: str, color: tuple[float, float, float, float]) -> None:
    """Create a new Principled BSDF material."""
    mat_ops.create_material(name, color)
    emit_result(
        f"Material '{name}' script ready.",
        {"ok": True, "name": name, "color": list(color)},
    )


@material_group.command("assign")
@click.argument("object_name")
@click.argument("material_name")
def material_assign(object_name: str, material_name: str) -> None:
    """Assign a material to an object."""
    mat_ops.assign_material(object_name, material_name)
    emit_result(
        f"Assign '{material_name}' → '{object_name}' script ready.",
        {"ok": True, "object": object_name, "material": material_name},
    )


@material_group.command("list")
def material_list() -> None:
    """Build a script that lists all materials."""
    result = mat_ops.list_materials()
    emit_result(
        "List-materials script ready.",
        {"ok": True, "statements": result["statements"]},
    )


# ---------------------------------------------------------------------------
# scene subgroup


@blender_cli.group("scene")
def scene_group() -> None:
    """Scene management commands."""


@scene_group.command("new")
@click.option("--name", default="Scene", show_default=True, help="Scene name.")
@click.option("--output", "-o", "output_path", default=None, help="Write project JSON to this file.")
@click.pass_context
def scene_new(ctx: click.Context, name: str, output_path: str | None) -> None:
    """Create a new empty Blender scene project in the session."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = BlenderProject(scene_name=name)
    sess.project = proj
    sess.save()
    if output_path is not None:
        import json as _json_mod
        from pathlib import Path
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json_mod.dumps(proj.to_dict(), indent=2), encoding="utf-8")
    emit_result(
        f"Blender scene {name!r} created.",
        {"ok": True, "scene_name": name},
    )


@scene_group.command("info")
@click.pass_context
def scene_info(ctx: click.Context) -> None:
    """Show scene details from the session."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    payload = proj.to_dict()
    emit_result(
        f"Scene '{proj.scene_name}': frames {proj.frame_start}–{proj.frame_end} @ {proj.fps} fps, "
        f"{len(proj.objects)} objects.",
        payload,
    )


@scene_group.command("frame-range")
@click.argument("start", type=int)
@click.argument("end", type=int)
@click.pass_context
def scene_frame_range(ctx: click.Context, start: int, end: int) -> None:
    """Set the scene frame range and persist in the session."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    proj.frame_start = start
    proj.frame_end = end
    sess.project = proj
    sess.save()
    emit_result(
        f"Frame range → {start}–{end}.",
        {"ok": True, "frame_start": start, "frame_end": end},
    )


@scene_group.command("fps")
@click.argument("value", type=int)
@click.pass_context
def scene_fps(ctx: click.Context, value: int) -> None:
    """Set the scene FPS and persist in the session."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    proj.fps = value
    sess.project = proj
    sess.save()
    emit_result(
        f"FPS → {value}.",
        {"ok": True, "fps": value},
    )


# ---------------------------------------------------------------------------
# session subgroup


@blender_cli.group("session")
def session_group() -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Display the contents of the active session."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
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
    """List all Blender sessions."""
    names = BlenderSession.list_sessions()
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
    sess = BlenderSession(name)
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


@blender_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Launch the interactive Blender console."""
    from .console import BlenderConsole
    BlenderConsole(session_name=ctx.obj["session_name"]).cmdloop()


# ---------------------------------------------------------------------------
# modifier subgroup


@blender_cli.group("modifier")
def modifier_group() -> None:
    """Mesh modifier commands."""


@modifier_group.command("list-available")
@click.option("--category", default=None, help="Filter by category (e.g. generate, deform).")
def modifier_list_available(category: str | None) -> None:
    """List modifiers available in the registry."""
    items = mod_ops.list_available(category)
    fmt = OutputFormatter()
    for item in items:
        fmt.record(**{k: v for k, v in item.items() if k != "params"}, params=",".join(item["params"]))
    fmt.flush()
    if not items:
        emit("(no modifiers found)")


@modifier_group.command("info")
@click.argument("name")
def modifier_info(name: str) -> None:
    """Show full details for a modifier type."""
    try:
        info = mod_ops.get_modifier_info(name)
    except KeyError as exc:
        emit_error(str(exc))
        return
    emit_result(f"Modifier {name.upper()}: {info['description']}", info)


@modifier_group.command("add")
@click.argument("modifier_type")
@click.option("--object-index", "-i", type=int, default=0, show_default=True)
@click.option("--name", "-n", default=None, help="Modifier name override.")
@click.option(
    "--param", "-p",
    "params_raw",
    multiple=True,
    metavar="KEY=VALUE",
    help="Modifier parameter as KEY=VALUE (can repeat).",
)
@click.pass_context
def modifier_add(
    ctx: click.Context,
    modifier_type: str,
    object_index: int,
    name: str | None,
    params_raw: tuple[str, ...],
) -> None:
    """Add a modifier of TYPE to an object."""
    params: dict = {}
    for kv in params_raw:
        if "=" not in kv:
            emit_error(f"Invalid param {kv!r}: expected KEY=VALUE.")
            return
        k, v = kv.split("=", 1)
        try:
            params[k] = _json.loads(v)
        except _json.JSONDecodeError:
            params[k] = v
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        result = mod_ops.add_modifier(proj, modifier_type, object_index, name, params)
    except (KeyError, ValueError) as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(
        f"Added {modifier_type.upper()} modifier '{result['name']}' to object {object_index}.",
        {"ok": True, **result},
    )


@modifier_group.command("remove")
@click.argument("modifier_index", type=int)
@click.option("--object-index", "-i", type=int, default=0, show_default=True)
@click.pass_context
def modifier_remove(ctx: click.Context, modifier_index: int, object_index: int) -> None:
    """Remove a modifier by its id."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        result = mod_ops.remove_modifier(proj, modifier_index, object_index)
    except KeyError as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(
        f"Removed modifier id={modifier_index} from object {object_index}.",
        {"ok": True, **result},
    )


@modifier_group.command("set")
@click.argument("modifier_index", type=int)
@click.argument("param")
@click.argument("value")
@click.option("--object-index", "-i", type=int, default=0, show_default=True)
@click.pass_context
def modifier_set(
    ctx: click.Context,
    modifier_index: int,
    param: str,
    value: str,
    object_index: int,
) -> None:
    """Set PARAM to VALUE on a modifier."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        parsed_value = _json.loads(value)
    except _json.JSONDecodeError:
        parsed_value = value
    try:
        result = mod_ops.set_modifier_param(proj, modifier_index, param, parsed_value, object_index)
    except KeyError as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(
        f"Set {param}={parsed_value!r} on modifier id={modifier_index}.",
        {"ok": True, **result},
    )


@modifier_group.command("list")
@click.option("--object-index", "-i", type=int, default=0, show_default=True)
@click.pass_context
def modifier_list(ctx: click.Context, object_index: int) -> None:
    """List modifiers on an object."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    result = mod_ops.list_modifiers(proj, object_index)
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for mod in result["modifiers"]:
        fmt.record(**mod)
    fmt.flush()
    if not result["modifiers"]:
        emit(f"(no modifiers on object {object_index})")


# ---------------------------------------------------------------------------
# camera subgroup


@blender_cli.group("camera")
def camera_group() -> None:
    """Camera management commands."""


@camera_group.command("add")
@click.option("--name", default="Camera", show_default=True)
@click.option("--location", nargs=3, type=float, default=(0.0, -10.0, 5.0), metavar="X Y Z")
@click.option("--rotation", nargs=3, type=float, default=(1.1, 0.0, 0.0), metavar="X Y Z")
@click.option("--type", "camera_type", default="PERSP", show_default=True,
              help="Camera type: PERSP, ORTHO, PANO.")
@click.option("--focal-length", type=float, default=50.0, show_default=True)
@click.option("--active", is_flag=True, default=False, help="Set as active scene camera.")
@click.pass_context
def camera_add(
    ctx: click.Context,
    name: str,
    location: tuple[float, float, float],
    rotation: tuple[float, float, float],
    camera_type: str,
    focal_length: float,
    active: bool,
) -> None:
    """Add a camera to the scene."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        result = light_ops.add_camera(
            proj,
            name=name,
            location=location,
            rotation=rotation,
            camera_type=camera_type,
            focal_length=focal_length,
            set_active=active,
        )
    except ValueError as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(
        f"Added camera '{name}' (type={camera_type}, focal={focal_length}mm).",
        {"ok": True, **result},
    )


@camera_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@click.pass_context
def camera_set(ctx: click.Context, index: int, prop: str, value: str) -> None:
    """Set PROP to VALUE on the camera at INDEX."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        parsed = _json.loads(value)
    except _json.JSONDecodeError:
        parsed = value
    try:
        result = light_ops.set_camera(proj, index, prop, parsed)
    except (IndexError, KeyError) as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(f"Camera[{index}].{prop} = {parsed!r}.", {"ok": True, **result})


@camera_group.command("set-active")
@click.argument("index", type=int)
@click.pass_context
def camera_set_active(ctx: click.Context, index: int) -> None:
    """Make the camera at INDEX the active scene camera."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        result = light_ops.set_active_camera(proj, index)
    except IndexError as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(f"Camera {index} is now active.", {"ok": True, **result})


@camera_group.command("list")
@click.pass_context
def camera_list(ctx: click.Context) -> None:
    """List all cameras in the session project."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    result = light_ops.list_cameras(proj)
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for cam in result["cameras"]:
        fmt.record(**cam)
    fmt.flush()
    if not result["cameras"]:
        emit("(no cameras in session)")


# ---------------------------------------------------------------------------
# light subgroup


@blender_cli.group("light")
def light_group() -> None:
    """Light management commands."""


@light_group.command("add")
@click.argument("light_type")
@click.option("--name", default=None)
@click.option("--location", nargs=3, type=float, default=(0.0, 0.0, 5.0), metavar="X Y Z")
@click.option("--color", nargs=3, type=float, default=(1.0, 1.0, 1.0), metavar="R G B")
@click.option("--power", type=float, default=1000.0, show_default=True)
@click.pass_context
def light_add(
    ctx: click.Context,
    light_type: str,
    name: str | None,
    location: tuple[float, float, float],
    color: tuple[float, float, float],
    power: float,
) -> None:
    """Add a light of TYPE to the scene."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        result = light_ops.add_light(
            proj,
            light_type=light_type,
            name=name,
            location=location,
            color=color,
            power=power,
        )
    except ValueError as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(
        f"Added {light_type.upper()} light '{result['name']}' at {list(location)}.",
        {"ok": True, **result},
    )


@light_group.command("set")
@click.argument("index", type=int)
@click.argument("prop")
@click.argument("value")
@click.pass_context
def light_set(ctx: click.Context, index: int, prop: str, value: str) -> None:
    """Set PROP to VALUE on the light at INDEX."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    try:
        parsed = _json.loads(value)
    except _json.JSONDecodeError:
        parsed = value
    try:
        result = light_ops.set_light(proj, index, prop, parsed)
    except (IndexError, KeyError) as exc:
        emit_error(str(exc))
        return
    sess.project = proj
    sess.save()
    emit_result(f"Light[{index}].{prop} = {parsed!r}.", {"ok": True, **result})


@light_group.command("list")
@click.pass_context
def light_list(ctx: click.Context) -> None:
    """List all lights in the session project."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    result = light_ops.list_lights(proj)
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for light in result["lights"]:
        fmt.record(**light)
    fmt.flush()
    if not result["lights"]:
        emit("(no lights in session)")


# ---------------------------------------------------------------------------
# animation subgroup


@blender_cli.group("animation")
def animation_group() -> None:
    """Animation keyframe commands."""


@animation_group.command("keyframe")
@click.argument("object_index", type=int)
@click.argument("frame", type=int)
@click.argument("prop")
@click.argument("value")
@click.option("--interpolation", default="BEZIER", show_default=True,
              help="Interpolation mode: BEZIER, LINEAR, CONSTANT.")
@click.pass_context
def animation_keyframe(
    ctx: click.Context,
    object_index: int,
    frame: int,
    prop: str,
    value: str,
    interpolation: str,
) -> None:
    """Add or update a keyframe on an object property."""
    try:
        parsed = _json.loads(value)
    except _json.JSONDecodeError:
        parsed = value
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    result = anim_ops.add_keyframe(proj, object_index, frame, prop, parsed, interpolation)
    sess.project = proj
    sess.save()
    action = "Updated" if result["updated"] else "Added"
    emit_result(
        f"{action} keyframe: object[{object_index}].{prop} = {parsed!r} @ frame {frame}.",
        {"ok": True, **result},
    )


@animation_group.command("remove-keyframe")
@click.argument("object_index", type=int)
@click.argument("frame", type=int)
@click.option("--prop", default=None, help="Property name; omit to remove all at frame.")
@click.pass_context
def animation_remove_keyframe(
    ctx: click.Context,
    object_index: int,
    frame: int,
    prop: str | None,
) -> None:
    """Remove keyframe(s) from an object at a specific frame."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    result = anim_ops.remove_keyframe(proj, object_index, frame, prop)
    sess.project = proj
    sess.save()
    emit_result(
        f"Removed {result['removed_count']} keyframe(s) from object[{object_index}] @ frame {frame}.",
        {"ok": True, **result},
    )


@animation_group.command("frame-range")
@click.argument("start", type=int)
@click.argument("end", type=int)
@click.pass_context
def animation_frame_range(ctx: click.Context, start: int, end: int) -> None:
    """Set the animation frame range (delegates to scene frame-range)."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    proj.frame_start = start
    proj.frame_end = end
    sess.project = proj
    sess.save()
    emit_result(
        f"Frame range → {start}–{end}.",
        {"ok": True, "frame_start": start, "frame_end": end},
    )


@animation_group.command("fps")
@click.argument("fps", type=int)
@click.pass_context
def animation_fps(ctx: click.Context, fps: int) -> None:
    """Set the scene FPS."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    proj.fps = fps
    sess.project = proj
    sess.save()
    emit_result(f"FPS → {fps}.", {"ok": True, "fps": fps})


@animation_group.command("list-keyframes")
@click.argument("object_index", type=int)
@click.option("--prop", default=None, help="Filter by property name.")
@click.pass_context
def animation_list_keyframes(
    ctx: click.Context, object_index: int, prop: str | None
) -> None:
    """List keyframes for an object."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project
    if proj is None:
        emit_error("No project in session.")
        return
    result = anim_ops.list_keyframes(proj, object_index, prop)
    fmt = OutputFormatter(json_mode=ctx.obj.get("use_json", False))
    for kf in result["keyframes"]:
        fmt.record(**kf)
    fmt.flush()
    if not result["keyframes"]:
        emit(f"(no keyframes for object {object_index})")


@animation_group.command("current-frame")
@click.argument("frame", type=int)
@click.pass_context
def animation_current_frame(ctx: click.Context, frame: int) -> None:
    """Set the current frame marker in the project."""
    sess = BlenderSession.open_or_create(ctx.obj["session_name"])
    proj = sess.project or BlenderProject()
    result = anim_ops.set_current_frame(proj, frame)
    sess.project = proj
    sess.save()
    emit_result(f"Current frame → {frame}.", {"ok": True, **result})


# ---------------------------------------------------------------------------
# Entry point


def main() -> None:
    cli_main(blender_cli)
