"""Shotcut CLI — sven-integrations-shotcut entry point."""

from __future__ import annotations

import click

from ..shared import cli_main, emit_error, emit_json, emit_result
from .backend import ShotcutBackend, ShotcutError
from .core import compositing as comp_mod
from .core import media as media_mod
from .core import timeline as tl_mod
from .core import transitions as trans_mod
from .project import MltClip, MltTrack, ShotcutProject, new_clip_id, new_track_id
from .session import ShotcutSession

# ---------------------------------------------------------------------------
# Shared helpers


def _get_session(name: str) -> ShotcutSession:
    return ShotcutSession.open_or_create(name)  # type: ignore[return-value]


def _load_project(sess: ShotcutSession) -> ShotcutProject:
    if sess.data.get("project"):
        return ShotcutProject.from_dict(sess.data["project"])
    return ShotcutProject()


def _save_project(sess: ShotcutSession, proj: ShotcutProject) -> None:
    sess.data["project"] = proj.to_dict()
    sess.save()


# ---------------------------------------------------------------------------
# Root group


@click.group()
@click.option("--session", "-s", default="default", help="Session name.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False, help="Emit JSON output.")
@click.pass_context
def shotcut_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """Shotcut CLI — build and render MLT projects from the command line."""
    from ..shared.output import set_json_mode

    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    if project_path is not None:
        sess = _get_session(session)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# open


@shotcut_cli.command("open")
@click.argument("mlt_path")
@click.pass_context
def cmd_open(ctx: click.Context, mlt_path: str) -> None:
    """Open an MLT project file."""
    sess = _get_session(ctx.obj["session"])
    backend = ShotcutBackend()
    if not backend.validate_mlt(mlt_path):
        emit_error(f"Invalid or missing MLT file: {mlt_path}")
    proj = tl_mod.mlt_to_project(mlt_path)
    _save_project(sess, proj)
    emit_result(
        f"Opened: {mlt_path} ({len(proj.tracks)} tracks)",
        {"status": "ok", "path": mlt_path, "tracks": len(proj.tracks)},
    )


# ---------------------------------------------------------------------------
# render


@shotcut_cli.command("render")
@click.option("--output", "-o", required=True, help="Output file path.")
@click.option("--preset", "-p", default="youtube", help="Export preset name.")
@click.pass_context
def cmd_render(ctx: click.Context, output: str, preset: str) -> None:
    """Render the active MLT project."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not proj.mlt_path:
        emit_error("No MLT file loaded; use 'open' first.")
    backend = ShotcutBackend()
    try:
        backend.render_mlt(proj.mlt_path, output, profile=proj.profile_name)  # type: ignore[arg-type]
    except ShotcutError as exc:
        emit_error(str(exc))
    emit_result(f"Rendered to {output}", {"status": "ok", "output": output})


# ---------------------------------------------------------------------------
# track group


@shotcut_cli.group("track")
def track_grp() -> None:
    """Track management commands."""


@track_grp.command("add")
@click.argument("name")
@click.option("--hide", default=0, type=int, help="Hide: 0=visible, 1=no video, 2=no audio.")
@click.pass_context
def track_add(ctx: click.Context, name: str, hide: int) -> None:
    """Add a new track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    track = MltTrack(track_id=new_track_id(), name=name, hide=hide)
    proj.add_track(track)
    _save_project(sess, proj)
    emit_result(f"Added track '{name}'", {"track_id": track.track_id, "name": name})


@track_grp.command("remove")
@click.argument("track_id")
@click.pass_context
def track_remove(ctx: click.Context, track_id: str) -> None:
    """Remove a track by ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not proj.remove_track(track_id):
        emit_error(f"Track '{track_id}' not found.")
    _save_project(sess, proj)
    emit_result(f"Removed track {track_id}", {"status": "ok"})


@track_grp.command("list")
@click.pass_context
def track_list(ctx: click.Context) -> None:
    """List all tracks."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    emit_json([t.to_dict() for t in proj.tracks])


@track_grp.command("mute")
@click.argument("track_id")
@click.option("--audio", "audio_only", is_flag=True, default=False, help="Mute audio only.")
@click.pass_context
def track_mute(ctx: click.Context, track_id: str, audio_only: bool) -> None:
    """Hide a track (1=no video, 2=no audio)."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    for t in proj.tracks:
        if t.track_id == track_id:
            t.hide = 2 if audio_only else 1
            _save_project(sess, proj)
            emit_result(f"Track {track_id} muted", {"track_id": track_id, "hide": t.hide})
            return
    emit_error(f"Track '{track_id}' not found.")


# ---------------------------------------------------------------------------
# clip group


@shotcut_cli.group("clip")
def clip_grp() -> None:
    """Clip management commands."""


@clip_grp.command("add")
@click.argument("track_id")
@click.argument("resource")
@click.option("--in", "in_f", type=int, default=0)
@click.option("--out", "out_f", type=int, required=True)
@click.option("--pos", "position", type=int, default=0)
@click.pass_context
def clip_add(
    ctx: click.Context,
    track_id: str,
    resource: str,
    in_f: int,
    out_f: int,
    position: int,
) -> None:
    """Add a clip to a track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = MltClip(
        clip_id=new_clip_id(),
        resource=resource,
        in_point=in_f,
        out_point=out_f,
        position=position,
    )
    if not proj.add_clip_to_track(track_id, clip):
        emit_error(f"Track '{track_id}' not found.")
    _save_project(sess, proj)
    emit_result(f"Added clip {clip.clip_id}", clip.to_dict())


@clip_grp.command("remove")
@click.argument("clip_id")
@click.pass_context
def clip_remove(ctx: click.Context, clip_id: str) -> None:
    """Remove a clip by ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    for track in proj.tracks:
        for i, c in enumerate(track.clips):
            if c.clip_id == clip_id:
                del track.clips[i]
                _save_project(sess, proj)
                emit_result(f"Removed {clip_id}", {"status": "ok"})
                return
    emit_error(f"Clip '{clip_id}' not found.")


@clip_grp.command("trim")
@click.argument("clip_id")
@click.option("--in", "in_f", type=int, required=True)
@click.option("--out", "out_f", type=int, required=True)
@click.pass_context
def clip_trim(ctx: click.Context, clip_id: str, in_f: int, out_f: int) -> None:
    """Trim a clip's in/out points."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = proj.find_clip(clip_id)
    if clip is None:
        emit_error(f"Clip '{clip_id}' not found.")
    clip.in_point = in_f  # type: ignore[union-attr]
    clip.out_point = out_f  # type: ignore[union-attr]
    _save_project(sess, proj)
    emit_result(f"Trimmed {clip_id}", {"in_point": in_f, "out_point": out_f})


@clip_grp.command("move")
@click.argument("clip_id")
@click.argument("position", type=int)
@click.pass_context
def clip_move(ctx: click.Context, clip_id: str, position: int) -> None:
    """Move a clip to a new position (frames)."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = proj.find_clip(clip_id)
    if clip is None:
        emit_error(f"Clip '{clip_id}' not found.")
    clip.position = position  # type: ignore[union-attr]
    _save_project(sess, proj)
    emit_result(f"Moved {clip_id} to frame {position}", {"position": position})


# ---------------------------------------------------------------------------
# filter group


@shotcut_cli.group("filter")
def filter_grp() -> None:
    """Filter management commands."""


@filter_grp.command("add")
@click.argument("clip_id")
@click.argument("filter_name")
@click.option("--param", "-p", multiple=True, help="key=value parameter.")
@click.pass_context
def filter_add(ctx: click.Context, clip_id: str, filter_name: str, param: tuple[str, ...]) -> None:
    """Add a filter to a clip (stored by name)."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = proj.find_clip(clip_id)
    if clip is None:
        emit_error(f"Clip '{clip_id}' not found.")
    clip.filters.append(filter_name)  # type: ignore[union-attr]
    _save_project(sess, proj)
    emit_result(f"Added filter '{filter_name}' to {clip_id}", {"status": "ok"})


@filter_grp.command("remove")
@click.argument("clip_id")
@click.argument("filter_name")
@click.pass_context
def filter_remove(ctx: click.Context, clip_id: str, filter_name: str) -> None:
    """Remove a named filter from a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = proj.find_clip(clip_id)
    if clip is None:
        emit_error(f"Clip '{clip_id}' not found.")
    try:
        clip.filters.remove(filter_name)  # type: ignore[union-attr]
    except ValueError:
        emit_error(f"Filter '{filter_name}' not found on {clip_id}.")
    _save_project(sess, proj)
    emit_result(f"Removed filter '{filter_name}'", {"status": "ok"})


@filter_grp.command("list")
@click.argument("clip_id")
@click.pass_context
def filter_list(ctx: click.Context, clip_id: str) -> None:
    """List filters on a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = proj.find_clip(clip_id)
    if clip is None:
        emit_error(f"Clip '{clip_id}' not found.")
    emit_json(clip.filters)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# preview command


@shotcut_cli.command("preview")
@click.option("--frame", type=int, required=True, help="Frame number to extract.")
@click.option("--output-png", required=True, help="Output PNG path.")
@click.pass_context
def cmd_preview(ctx: click.Context, frame: int, output_png: str) -> None:
    """Extract a preview frame as a PNG image."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not proj.mlt_path:
        emit_error("No MLT file loaded; use 'open' first.")
    backend = ShotcutBackend()
    try:
        backend.preview_frame(proj.mlt_path, frame, output_png)  # type: ignore[arg-type]
    except ShotcutError as exc:
        emit_error(str(exc))
    emit_result(f"Frame {frame} extracted to {output_png}", {"status": "ok", "frame": frame})


# ---------------------------------------------------------------------------
# composite group


@shotcut_cli.group("composite")
def composite_grp() -> None:
    """Track compositing — blend modes, opacity, and PIP commands."""


@composite_grp.command("blend-modes")
def composite_blend_modes() -> None:
    """List all available Cairo blend modes."""
    modes = comp_mod.list_blend_modes()
    emit_result(f"{len(modes)} blend mode(s)", modes)


@composite_grp.command("set-blend")
@click.argument("track_index", type=int)
@click.argument("mode")
@click.pass_context
def composite_set_blend(ctx: click.Context, track_index: int, mode: str) -> None:
    """Set the blend mode for TRACK_INDEX."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        result = comp_mod.set_track_blend_mode(proj, track_index, mode)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Track {track_index} blend mode → {mode!r}", result)


@composite_grp.command("get-blend")
@click.argument("track_index", type=int)
@click.pass_context
def composite_get_blend(ctx: click.Context, track_index: int) -> None:
    """Get the blend mode for TRACK_INDEX."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        result = comp_mod.get_track_blend_mode(proj, track_index)
    except IndexError as exc:
        emit_error(str(exc))
    emit_result(f"Track {track_index} blend mode", result)


@composite_grp.command("set-opacity")
@click.argument("track_index", type=int)
@click.argument("opacity", type=float)
@click.pass_context
def composite_set_opacity(ctx: click.Context, track_index: int, opacity: float) -> None:
    """Set the opacity (0.0–1.0) for TRACK_INDEX."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        result = comp_mod.set_track_opacity(proj, track_index, opacity)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Track {track_index} opacity → {opacity}", result)


@composite_grp.command("pip")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--x", default=0.0, type=float, help="Normalised X position (0–1).")
@click.option("--y", default=0.0, type=float, help="Normalised Y position (0–1).")
@click.option("--width", default=0.25, type=float, help="Normalised width (0–1).")
@click.option("--height", default=0.25, type=float, help="Normalised height (0–1).")
@click.option("--opacity", default=1.0, type=float, help="Opacity (0–1).")
@click.pass_context
def composite_pip(
    ctx: click.Context,
    track_index: int,
    clip_index: int,
    x: float,
    y: float,
    width: float,
    height: float,
    opacity: float,
) -> None:
    """Set PIP position and size for a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        result = comp_mod.pip_position(proj, track_index, clip_index, x, y, width, height, opacity)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"PIP set on track {track_index} clip {clip_index}", result)


# ---------------------------------------------------------------------------
# media group


@shotcut_cli.group("media")
def media_grp() -> None:
    """Media probing and resource checking commands."""


@media_grp.command("probe")
@click.argument("path")
def media_probe(path: str) -> None:
    """Probe media file at PATH and show metadata."""
    result = media_mod.probe_media(path)
    emit_result(f"Probed: {path}", result.to_dict())


@media_grp.command("list")
@click.pass_context
def media_list(ctx: click.Context) -> None:
    """List all unique media resources in the project."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    info = media_mod.list_media(proj)
    emit_result(f"{info['count']} resource(s)", info)


@media_grp.command("check")
@click.pass_context
def media_check(ctx: click.Context) -> None:
    """Check that all project media files exist on disk."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    info = media_mod.check_media_files(proj)
    status = "OK" if info["ok"] else f"{len(info['missing'])} file(s) missing"
    emit_result(status, info)


@media_grp.command("thumbnail")
@click.argument("path")
@click.option("--output", "-o", required=True, help="Output image path.")
@click.option("--time", "time_s", default=1.0, type=float, help="Seek time in seconds.")
@click.option("--width", default=320, type=int)
@click.option("--height", default=180, type=int)
def media_thumbnail(path: str, output: str, time_s: float, width: int, height: int) -> None:
    """Extract a thumbnail frame from a media file."""
    result = media_mod.generate_thumbnail(path, output, time_s, width, height)
    if result["ok"]:
        emit_result(f"Thumbnail saved to {output}", result)
    else:
        emit_error(result.get("error", "Unknown error"))


# ---------------------------------------------------------------------------
# transition group (Shotcut)


@shotcut_cli.group("transition")
def shotcut_transition_grp() -> None:
    """MLT transition management commands."""


@shotcut_transition_grp.command("available")
@click.option("--category", default=None, help="Filter by category (dissolve/wipe).")
def trans_available(category: str | None) -> None:
    """List all available transition types."""
    items = trans_mod.list_available_transitions(category)
    emit_result(f"{len(items)} transition(s)", items)


@shotcut_transition_grp.command("info")
@click.argument("name")
def trans_info(name: str) -> None:
    """Show details for transition NAME."""
    from .core.transitions import TRANSITION_REGISTRY
    spec = TRANSITION_REGISTRY.get(name)
    if spec is None:
        emit_error(f"Unknown transition: {name!r}")
    emit_result(f"Transition: {name}", {**{"name": name}, **spec})


@shotcut_transition_grp.command("add")
@click.argument("name")
@click.option("--track-a", "track_a", type=int, default=0, help="Lower track index.")
@click.option("--track-b", "track_b", type=int, default=1, help="Upper track index.")
@click.option("--in", "in_frame", type=int, required=True, help="Start frame.")
@click.option("--out", "out_frame", type=int, required=True, help="End frame.")
@click.option("--param", "-p", multiple=True, help="key=value parameter.")
@click.pass_context
def trans_add(
    ctx: click.Context,
    name: str,
    track_a: int,
    track_b: int,
    in_frame: int,
    out_frame: int,
    param: tuple[str, ...],
) -> None:
    """Add transition NAME between two tracks."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    params: dict[str, object] = {}
    for p in param:
        if "=" not in p:
            emit_error(f"Invalid param {p!r}; use key=value")
        k, v_str = p.split("=", 1)
        try:
            params[k] = int(v_str) if "." not in v_str else float(v_str)
        except ValueError:
            params[k] = v_str
    try:
        result = trans_mod.add_transition(proj, name, track_a, track_b, in_frame, out_frame, params)
    except (ValueError, IndexError) as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Added transition {name!r}", result)


@shotcut_transition_grp.command("remove")
@click.argument("index", type=int)
@click.pass_context
def trans_remove(ctx: click.Context, index: int) -> None:
    """Remove transition at INDEX."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        removed = trans_mod.remove_transition(proj, index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Removed transition {index}", removed)


@shotcut_transition_grp.command("set")
@click.argument("index", type=int)
@click.argument("param_name")
@click.argument("value")
@click.pass_context
def trans_set(ctx: click.Context, index: int, param_name: str, value: str) -> None:
    """Set a parameter on transition at INDEX."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        parsed: object
        try:
            parsed = int(value) if "." not in value else float(value)
        except ValueError:
            parsed = value
        result = trans_mod.set_transition_param(proj, index, param_name, parsed)
    except IndexError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Transition {index}: {param_name} = {value}", result)


@shotcut_transition_grp.command("list")
@click.pass_context
def trans_list(ctx: click.Context) -> None:
    """List all transitions on the project."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    info = trans_mod.list_transitions(proj)
    emit_json(info["transitions"])


# ---------------------------------------------------------------------------
# session group


@shotcut_cli.group("session")
def session_grp() -> None:
    """Session management commands."""


@session_grp.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Show active session data."""
    sess = _get_session(ctx.obj["session"])
    emit_json({"name": sess.name, "harness": sess.harness, "data": sess.data})


@session_grp.command("list")
def session_list() -> None:
    """List all saved sessions."""
    emit_json(ShotcutSession.list_sessions())


@session_grp.command("delete")
@click.pass_context
def session_delete(ctx: click.Context) -> None:
    """Delete the current session."""
    sess = _get_session(ctx.obj["session"])
    deleted = sess.delete()
    emit_result(
        f"Session '{sess.name}' deleted." if deleted else "Session not found.",
        {"deleted": deleted, "name": sess.name},
    )


# ---------------------------------------------------------------------------
# repl command


@shotcut_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL session."""
    from .console import ShotcutConsole

    console = ShotcutConsole(session_name=ctx.obj["session"])
    console.cmdloop()


# ---------------------------------------------------------------------------
# Entry point


def main() -> None:
    cli_main(shotcut_cli)


if __name__ == "__main__":
    main()
