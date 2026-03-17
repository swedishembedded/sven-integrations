"""Kdenlive CLI — sven-integrations-kdenlive entry point."""

from __future__ import annotations

from typing import Optional

import click

from ..shared import (
    cli_main,
    emit_error,
    emit_json,
    emit_result,
)
from .backend import KdenliveBackend, KdenliveError
from .core import bin as bin_mod
from .core import effects as eff_mod
from .core import guides as guide_mod
from .core import render as render_mod
from .core import timeline as tl_mod
from .core import transitions as trans_mod
from .project import KdenliveProject, TimelineClip, new_clip_id
from .session import KdenliveSession

# ---------------------------------------------------------------------------
# Shared state


def _get_session(name: str) -> KdenliveSession:
    sess = KdenliveSession.open_or_create(name)
    return sess  # type: ignore[return-value]


def _load_project(sess: KdenliveSession) -> KdenliveProject:
    if sess.data.get("project"):
        return KdenliveProject.from_dict(sess.data["project"])
    return KdenliveProject()


def _save_project(sess: KdenliveSession, proj: KdenliveProject) -> None:
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
def kdenlive_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """Kdenlive CLI — control Kdenlive video editing via the command line."""
    from ..shared.output import set_json_mode

    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    if project_path is not None:
        sess = _get_session(session)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# project group


@kdenlive_cli.group("project")
def project_group() -> None:
    """Project management commands."""


@project_group.command("new")
@click.option("--name", default="Untitled", show_default=True, help="Project name.")
@click.option("--profile", default="hdv_720_25p", show_default=True, help="MLT profile name.")
@click.option("--output", "-o", "output_path", default=None, help="Write project JSON to this file.")
@click.pass_context
def project_new(ctx: click.Context, name: str, profile: str, output_path: str | None) -> None:
    """Create a new empty Kdenlive project in the session."""
    import json as _json_mod
    from pathlib import Path
    sess = _get_session(ctx.obj["session"])
    proj = KdenliveProject(profile_name=profile)
    _save_project(sess, proj)
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json_mod.dumps({"name": name, "profile": profile, **proj.to_dict()}, indent=2), encoding="utf-8")
    emit_result(
        f"Kdenlive project {name!r} created.",
        {"ok": True, "name": name, "profile": profile},
    )


# ---------------------------------------------------------------------------
# open / save


@kdenlive_cli.command("open")
@click.argument("path")
@click.pass_context
def cmd_open(ctx: click.Context, path: str) -> None:
    """Open a Kdenlive project file."""
    sess = _get_session(ctx.obj["session"])
    backend = KdenliveBackend()
    backend.connect_dbus()
    try:
        backend.open_project(path)
    except KdenliveError as exc:
        emit_error(str(exc))
    proj = _load_project(sess)
    proj.project_path = path
    _save_project(sess, proj)
    emit_result(f"Opened project: {path}", {"status": "ok", "path": path})


@kdenlive_cli.command("save")
@click.option("--path", "save_path", default=None, help="Override save path.")
@click.pass_context
def cmd_save(ctx: click.Context, save_path: Optional[str]) -> None:
    """Save the current project."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    target = save_path or proj.project_path
    if not target:
        emit_error("No project path set; use --path to specify one.")
    tl_mod.save_project_to_xml(proj, target)  # type: ignore[arg-type]
    proj.project_path = target
    _save_project(sess, proj)
    emit_result(f"Saved to: {target}", {"status": "ok", "path": target})


# ---------------------------------------------------------------------------
# track group


@kdenlive_cli.group("track")
def track_grp() -> None:
    """Track management commands."""


@track_grp.command("add-video")
@click.argument("name")
@click.option("--index", "-i", default=None, type=int, help="Insert at position.")
@click.pass_context
def track_add_video(ctx: click.Context, name: str, index: Optional[int]) -> None:
    """Add a video track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    track = tl_mod.add_video_track(proj, name, index)
    _save_project(sess, proj)
    emit_result(
        f"Added video track '{name}' ({track.track_id})",
        {"track_id": track.track_id, "name": name, "kind": "video"},
    )


@track_grp.command("add-audio")
@click.argument("name")
@click.option("--index", "-i", default=None, type=int, help="Insert at position.")
@click.pass_context
def track_add_audio(ctx: click.Context, name: str, index: Optional[int]) -> None:
    """Add an audio track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    track = tl_mod.add_audio_track(proj, name, index)
    _save_project(sess, proj)
    emit_result(
        f"Added audio track '{name}' ({track.track_id})",
        {"track_id": track.track_id, "name": name, "kind": "audio"},
    )


@track_grp.command("remove")
@click.argument("track_id")
@click.pass_context
def track_remove(ctx: click.Context, track_id: str) -> None:
    """Remove a track by ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not tl_mod.remove_track(proj, track_id):
        emit_error(f"Track '{track_id}' not found.")
    _save_project(sess, proj)
    emit_result(f"Removed track {track_id}", {"status": "ok", "track_id": track_id})


@track_grp.command("mute")
@click.argument("track_id")
@click.option("--off", "unmute", is_flag=True, default=False, help="Unmute instead.")
@click.pass_context
def track_mute(ctx: click.Context, track_id: str, unmute: bool) -> None:
    """Mute (or unmute) a track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    tl_mod.mute_track(proj, track_id, not unmute)
    _save_project(sess, proj)
    state = "unmuted" if unmute else "muted"
    emit_result(f"Track {track_id} {state}", {"track_id": track_id, "muted": not unmute})


@track_grp.command("lock")
@click.argument("track_id")
@click.option("--off", "unlock", is_flag=True, default=False, help="Unlock instead.")
@click.pass_context
def track_lock(ctx: click.Context, track_id: str, unlock: bool) -> None:
    """Lock (or unlock) a track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    tl_mod.lock_track(proj, track_id, not unlock)
    _save_project(sess, proj)
    state = "unlocked" if unlock else "locked"
    emit_result(f"Track {track_id} {state}", {"track_id": track_id, "locked": not unlock})


@track_grp.command("list")
@click.pass_context
def track_list(ctx: click.Context) -> None:
    """List all tracks."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    tracks = [
        {"track_id": t.track_id, "name": t.name, "kind": t.kind, "muted": t.muted, "locked": t.locked}
        for t in proj.tracks
    ]
    emit_json(tracks)


# ---------------------------------------------------------------------------
# clip group


@kdenlive_cli.group("clip")
def clip_grp() -> None:
    """Clip management commands."""


@clip_grp.command("add")
@click.argument("track_id")
@click.argument("bin_id")
@click.option("--in", "in_point", type=float, default=0.0)
@click.option("--out", "out_point", type=float, required=True)
@click.option("--pos", "position", type=float, required=True)
@click.pass_context
def clip_add(
    ctx: click.Context,
    track_id: str,
    bin_id: str,
    in_point: float,
    out_point: float,
    position: float,
) -> None:
    """Add a clip to a track."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    clip = TimelineClip(
        clip_id=new_clip_id(),
        bin_id=bin_id,
        in_point=in_point,
        out_point=out_point,
        position=position,
    )
    if not proj.add_clip(track_id, clip):
        emit_error(f"Track '{track_id}' not found.")
    _save_project(sess, proj)
    emit_result(
        f"Added clip {clip.clip_id} to {track_id}",
        clip.to_dict(),
    )


@clip_grp.command("move")
@click.argument("clip_id")
@click.argument("position", type=float)
@click.pass_context
def clip_move(ctx: click.Context, clip_id: str, position: float) -> None:
    """Move a clip to a new timeline position (seconds)."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not tl_mod.move_clip(proj, clip_id, position):
        emit_error(f"Clip '{clip_id}' not found.")
    _save_project(sess, proj)
    emit_result(f"Moved {clip_id} to {position}s", {"clip_id": clip_id, "position": position})


@clip_grp.command("trim")
@click.argument("clip_id")
@click.option("--in", "in_point", type=float, required=True)
@click.option("--out", "out_point", type=float, required=True)
@click.pass_context
def clip_trim(ctx: click.Context, clip_id: str, in_point: float, out_point: float) -> None:
    """Trim a clip's source in/out points."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not tl_mod.trim_clip(proj, clip_id, in_point, out_point):
        emit_error(f"Clip '{clip_id}' not found.")
    _save_project(sess, proj)
    emit_result(
        f"Trimmed {clip_id}: {in_point}s–{out_point}s",
        {"clip_id": clip_id, "in_point": in_point, "out_point": out_point},
    )


@clip_grp.command("split")
@click.argument("clip_id")
@click.argument("split_pos", type=float)
@click.pass_context
def clip_split(ctx: click.Context, clip_id: str, split_pos: float) -> None:
    """Split a clip at a timeline position (seconds)."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    result = tl_mod.split_clip_at(proj, clip_id, split_pos)
    if result is None:
        emit_error(f"Clip '{clip_id}' not found or split_pos out of range.")
    _save_project(sess, proj)
    left, right = result  # type: ignore[misc]
    emit_result(
        f"Split {clip_id} at {split_pos}s",
        {"left": left.to_dict(), "right": right.to_dict()},
    )


@clip_grp.command("remove")
@click.argument("clip_id")
@click.pass_context
def clip_remove(ctx: click.Context, clip_id: str) -> None:
    """Remove a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not tl_mod.remove_clip(proj, clip_id):
        emit_error(f"Clip '{clip_id}' not found.")
    _save_project(sess, proj)
    emit_result(f"Removed clip {clip_id}", {"status": "ok", "clip_id": clip_id})


# ---------------------------------------------------------------------------
# effect group


@kdenlive_cli.group("effect")
def effect_grp() -> None:
    """Effect management commands."""


@effect_grp.command("add")
@click.argument("clip_id")
@click.argument("effect_name")
@click.option("--param", "-p", multiple=True, help="key=value parameter.")
@click.pass_context
def effect_add(ctx: click.Context, clip_id: str, effect_name: str, param: tuple[str, ...]) -> None:
    """Add an effect to a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    params: dict[str, str | float | int] = {}
    for p in param:
        if "=" not in p:
            emit_error(f"Invalid param format '{p}'; use key=value.")
        k, v_str = p.split("=", 1)
        try:
            v: str | float | int = int(v_str) if "." not in v_str else float(v_str)
        except ValueError:
            v = v_str
        params[k] = v
    eff = eff_mod.add_effect(proj, clip_id, effect_name, params)
    _save_project(sess, proj)
    emit_result(f"Added effect '{effect_name}' to {clip_id}", eff)


@effect_grp.command("remove")
@click.argument("clip_id")
@click.argument("effect_id")
@click.pass_context
def effect_remove(ctx: click.Context, clip_id: str, effect_id: str) -> None:
    """Remove an effect from a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if not eff_mod.remove_effect(proj, clip_id, effect_id):
        emit_error(f"Effect '{effect_id}' not found on clip '{clip_id}'.")
    _save_project(sess, proj)
    emit_result(f"Removed {effect_id}", {"status": "ok"})


@effect_grp.command("list")
@click.argument("clip_id")
@click.pass_context
def effect_list(ctx: click.Context, clip_id: str) -> None:
    """List effects on a clip."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    effects = eff_mod.list_effects(proj, clip_id)
    emit_json(effects)


# ---------------------------------------------------------------------------
# render command


@kdenlive_cli.command("render")
@click.option("--output", "-o", required=True, help="Output file path.")
@click.option("--profile", "-p", default=None, help="Render profile name.")
@click.option("--start", "start_s", type=float, default=None, help="Start time (seconds).")
@click.option("--end", "end_s", type=float, default=None, help="End time (seconds).")
@click.pass_context
def cmd_render(
    ctx: click.Context,
    output: str,
    profile: Optional[str],
    start_s: Optional[float],
    end_s: Optional[float],
) -> None:
    """Render the project to a file."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    if start_s is not None and end_s is not None:
        render_mod.set_render_range(start_s, end_s)
    try:
        result = render_mod.render_to_file(
            output,
            profile=profile,
            mlt_path=proj.project_path,
        )
    except render_mod.RenderError as exc:
        emit_error(str(exc))
    emit_result(f"Rendered to {output}", result)


# ---------------------------------------------------------------------------
# session group


@kdenlive_cli.group("session")
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
    sessions = KdenliveSession.list_sessions()
    emit_json(sessions)


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
# bin group


@kdenlive_cli.group("bin")
def bin_grp() -> None:
    """Project bin (media library) management commands."""


@bin_grp.command("import")
@click.argument("source")
@click.option("--name", default=None, help="Override clip name.")
@click.option("--duration", type=float, default=None, help="Duration in seconds.")
@click.option("--type", "clip_type", default="video",
              type=click.Choice(["video", "audio", "image", "color", "title"]))
@click.pass_context
def bin_import(
    ctx: click.Context,
    source: str,
    name: Optional[str],
    duration: Optional[float],
    clip_type: str,
) -> None:
    """Import SOURCE into the project bin."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        clip = bin_mod.import_clip(proj, source, name, duration, clip_type)
    except ValueError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Imported {clip['clip_id']}: {clip['name']}", clip)


@bin_grp.command("remove")
@click.argument("clip_id")
@click.pass_context
def bin_remove(ctx: click.Context, clip_id: str) -> None:
    """Remove clip CLIP_ID from the bin."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        removed = bin_mod.remove_clip(proj, clip_id)
    except KeyError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Removed {clip_id}", removed)


@bin_grp.command("list")
@click.pass_context
def bin_list(ctx: click.Context) -> None:
    """List all clips in the bin."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    info = bin_mod.list_clips(proj)
    emit_json(info["clips"])


@bin_grp.command("get")
@click.argument("clip_id")
@click.pass_context
def bin_get(ctx: click.Context, clip_id: str) -> None:
    """Show details for clip CLIP_ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        clip = bin_mod.get_clip(proj, clip_id)
    except KeyError as exc:
        emit_error(str(exc))
    emit_json(clip)


# ---------------------------------------------------------------------------
# guide group


@kdenlive_cli.group("guide")
def guide_grp() -> None:
    """Timeline guide (chapter marker) management commands."""


@guide_grp.command("add")
@click.argument("position", type=float)
@click.option("--label", default="", help="Guide label text.")
@click.option("--type", "guide_type", default="chapter",
              type=click.Choice(["chapter", "section", "comment"]))
@click.option("--comment", default="", help="Extended comment.")
@click.pass_context
def guide_add(
    ctx: click.Context,
    position: float,
    label: str,
    guide_type: str,
    comment: str,
) -> None:
    """Add a guide at POSITION seconds."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    guide = guide_mod.add_guide(proj, position, label, guide_type, comment)
    _save_project(sess, proj)
    emit_result(f"Guide {guide['guide_id']} added at {position}s", guide)


@guide_grp.command("remove")
@click.argument("guide_id", type=int)
@click.pass_context
def guide_remove(ctx: click.Context, guide_id: int) -> None:
    """Remove guide GUIDE_ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        removed = guide_mod.remove_guide(proj, guide_id)
    except KeyError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Removed guide {guide_id}", removed)


@guide_grp.command("list")
@click.pass_context
def guide_list(ctx: click.Context) -> None:
    """List all timeline guides sorted by position."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    info = guide_mod.list_guides(proj)
    emit_json(info["guides"])


# ---------------------------------------------------------------------------
# transition group


@kdenlive_cli.group("transition")
def kdenlive_transition_grp() -> None:
    """Timeline transition management commands."""


@kdenlive_transition_grp.command("add")
@click.argument("trans_type", metavar="TYPE")
@click.argument("track_a")
@click.argument("track_b")
@click.option("--position", type=float, required=True, help="Position in seconds.")
@click.option("--duration", type=float, default=1.0, help="Duration in seconds.")
@click.option("--param", "-p", multiple=True, help="key=value parameter.")
@click.pass_context
def kdenlive_transition_add(
    ctx: click.Context,
    trans_type: str,
    track_a: str,
    track_b: str,
    position: float,
    duration: float,
    param: tuple[str, ...],
) -> None:
    """Add a transition of TYPE between TRACK_A and TRACK_B."""
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
        result = trans_mod.add_transition(proj, trans_type, track_a, track_b, position, duration, params)
    except ValueError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Transition {result['transition_id']} added", result)


@kdenlive_transition_grp.command("remove")
@click.argument("transition_id", type=int)
@click.pass_context
def kdenlive_transition_remove(ctx: click.Context, transition_id: int) -> None:
    """Remove transition TRANSITION_ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        removed = trans_mod.remove_transition(proj, transition_id)
    except KeyError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Removed transition {transition_id}", removed)


@kdenlive_transition_grp.command("set")
@click.argument("transition_id", type=int)
@click.argument("param_name")
@click.argument("value")
@click.pass_context
def kdenlive_transition_set(
    ctx: click.Context,
    transition_id: int,
    param_name: str,
    value: str,
) -> None:
    """Set a parameter on transition TRANSITION_ID."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        parsed: object
        try:
            parsed = int(value) if "." not in value else float(value)
        except ValueError:
            parsed = value
        result = trans_mod.set_transition(proj, transition_id, param_name, parsed)
    except KeyError as exc:
        emit_error(str(exc))
    _save_project(sess, proj)
    emit_result(f"Transition {transition_id}: {param_name} = {value}", result)


@kdenlive_transition_grp.command("list")
@click.pass_context
def kdenlive_transition_list(ctx: click.Context) -> None:
    """List all timeline transitions."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    info = trans_mod.list_transitions(proj)
    emit_json(info["transitions"])


# ---------------------------------------------------------------------------
# export group


@kdenlive_cli.group("export")
def export_grp() -> None:
    """Export commands."""


@export_grp.command("xml")
@click.option("--output", "-o", required=True, help="Output XML path.")
@click.pass_context
def export_xml(ctx: click.Context, output: str) -> None:
    """Export the project to an MLT XML file."""
    sess = _get_session(ctx.obj["session"])
    proj = _load_project(sess)
    try:
        tl_mod.save_project_to_xml(proj, output)
    except Exception as exc:
        emit_error(str(exc))
    emit_result(f"Exported to {output}", {"status": "ok", "path": output})


@export_grp.command("presets")
def export_presets() -> None:
    """List available render presets."""
    profiles = ["dvd_pal", "hdv_1080_25p", "atsc_1080p_25", "atsc_720p_25",
                "webm_720p", "mp4_h264_aac", "dnxhd_1080i", "prores_422"]
    emit_json(profiles)


# ---------------------------------------------------------------------------
# repl command


@kdenlive_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL session."""
    from .console import KdenliveConsole

    console = KdenliveConsole(session_name=ctx.obj["session"])
    console.cmdloop()


# ---------------------------------------------------------------------------
# Entry point


def main() -> None:
    cli_main(kdenlive_cli)


if __name__ == "__main__":
    main()
