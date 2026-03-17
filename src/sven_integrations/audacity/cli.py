"""Audacity CLI — command-line interface for controlling Audacity via mod-script-pipe."""

from __future__ import annotations

import click

from ..shared import emit, emit_error, emit_result
from .backend import AudacityBackend, AudacityConnectionError
from .core import clips as clip_mod
from .core import effects as fx_mod
from .core import export as exp_mod
from .core import labels as label_mod
from .core import media as media_mod
from .core import selection as sel_mod
from .core import tracks as track_mod
from .project import AudioProject
from .session import AudacitySession

# ---------------------------------------------------------------------------
# Module-level singletons shared across command invocations in one process
_backend = AudacityBackend()


def _get_session(name: str) -> AudacitySession:
    s = AudacitySession.open_or_create(name)
    return s  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Root group

@click.group()
@click.option("--session", "-s", "session_name", default="default",
              help="Session name to load/save state into.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Emit machine-readable JSON output.")
@click.pass_context
def audacity_cli(
    ctx: click.Context, session_name: str, project_path: str | None, use_json: bool
) -> None:
    """Audacity integration — control a running Audacity instance via mod-script-pipe."""
    from ..shared.output import set_json_mode
    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session_name"] = session_name
    if project_path is not None:
        sess = _get_session(session_name)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# project group


@audacity_cli.group("project")
def project_group() -> None:
    """Project management commands."""


@project_group.command("new")
@click.option("--name", default="Untitled", show_default=True, help="Project name.")
@click.option("--output", "-o", "output_path", default=None, help="Write project JSON to this file.")
@click.pass_context
def project_new(ctx: click.Context, name: str, output_path: str | None) -> None:
    """Create a new empty audio project in the session."""
    import json as _json_mod
    from pathlib import Path
    sess = AudacitySession.open_or_create(ctx.obj.get("session_name", "default"))
    proj = AudioProject(name=name)
    sess.data["project"] = {"name": proj.name, "sample_rate": proj.sample_rate, "channels": proj.channels}
    sess.save()
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json_mod.dumps(sess.data, indent=2), encoding="utf-8")
    emit_result(
        f"Audio project {name!r} created.",
        {"ok": True, "name": name},
    )


# ---------------------------------------------------------------------------
# connect

@audacity_cli.command("connect")
@click.pass_context
def cmd_connect(ctx: click.Context) -> None:
    """Verify the mod-script-pipe connection to Audacity."""
    try:
        if not _backend.is_connected():
            _backend.connect()
        if _backend.ping():
            emit_result(
                "Connected to Audacity",
                {"status": "connected", "pipe": f"/tmp/audacity_script_pipe.to.{__import__('os').getuid()}"},
            )
        else:
            emit_error("Audacity did not respond to ping")
    except AudacityConnectionError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# track group

@audacity_cli.group("track")
def track_group() -> None:
    """Track management commands."""


@track_group.command("new")
@click.argument("kind", type=click.Choice(["mono", "stereo", "label"]))
@click.option("--name", "-n", default="", help="Track name")
@click.pass_context
def track_new(ctx: click.Context, kind: str, name: str) -> None:
    """Create a new track of the given kind."""
    try:
        label = name or f"{kind.capitalize()} Track"
        if kind == "mono":
            track_mod.new_mono_track(_backend, label)
        elif kind == "stereo":
            track_mod.new_stereo_track(_backend, label)
        else:
            track_mod.new_label_track(_backend, label)
        emit_result(f"Created {kind} track: {label}", {"kind": kind, "name": label})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@track_group.command("delete")
@click.argument("index", type=int)
@click.pass_context
def track_delete(ctx: click.Context, index: int) -> None:
    """Delete the track at INDEX (0-based)."""
    try:
        track_mod.delete_track(_backend, index)
        emit_result(f"Deleted track {index}", {"deleted_index": index})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@track_group.command("mute")
@click.argument("index", type=int)
def track_mute(index: int) -> None:
    """Toggle mute on the track at INDEX."""
    try:
        track_mod.mute_track(_backend, index)
        emit_result(f"Mute toggled on track {index}", {"track": index, "action": "mute"})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@track_group.command("solo")
@click.argument("index", type=int)
def track_solo(index: int) -> None:
    """Toggle solo on the track at INDEX."""
    try:
        track_mod.solo_track(_backend, index)
        emit_result(f"Solo toggled on track {index}", {"track": index, "action": "solo"})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@track_group.command("gain")
@click.argument("index", type=int)
@click.argument("db", type=float)
def track_gain(index: int, db: float) -> None:
    """Set gain on track INDEX to DB decibels."""
    try:
        track_mod.set_gain(_backend, index, db)
        emit_result(f"Track {index} gain → {db} dB", {"track": index, "gain_db": db})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@track_group.command("pan")
@click.argument("index", type=int)
@click.argument("value", type=float)
def track_pan(index: int, value: float) -> None:
    """Set pan on track INDEX to VALUE (-1 left, 0 centre, 1 right)."""
    try:
        track_mod.set_pan(_backend, index, value)
        emit_result(f"Track {index} pan → {value}", {"track": index, "pan": value})
    except (AudacityConnectionError, ValueError) as exc:
        emit_error(str(exc))


@track_group.command("list")
@click.pass_context
def track_list(ctx: click.Context) -> None:
    """List tracks in the session project."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit("No project loaded in session")
        return
    tracks = [t.to_dict() for t in proj.tracks]
    emit_result(f"{len(tracks)} track(s)", tracks)


# ---------------------------------------------------------------------------
# select group

@audacity_cli.group("select")
def select_group() -> None:
    """Selection management commands."""


@select_group.command("all")
def select_all() -> None:
    """Select all audio in all tracks."""
    try:
        sel_mod.select_all(_backend)
        emit_result("Selected all", {"selection": "all"})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@select_group.command("none")
def select_none() -> None:
    """Clear the current selection."""
    try:
        sel_mod.select_none(_backend)
        emit_result("Selection cleared", {"selection": "none"})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@select_group.command("time")
@click.argument("start", type=float)
@click.argument("end", type=float)
def select_time(start: float, end: float) -> None:
    """Select the time range from START to END seconds."""
    try:
        sel_mod.select_time(_backend, start, end)
        emit_result(f"Time {start}s – {end}s selected", {"start": start, "end": end})
    except (AudacityConnectionError, ValueError) as exc:
        emit_error(str(exc))


@select_group.command("region")
@click.argument("start", type=float)
@click.argument("end", type=float)
@click.argument("first_track", type=int)
@click.argument("last_track", type=int)
def select_region(start: float, end: float, first_track: int, last_track: int) -> None:
    """Select a region spanning time and tracks."""
    try:
        sel_mod.select_region(_backend, start, end, first_track, last_track)
        emit_result(
            f"Region {start}s–{end}s, tracks {first_track}–{last_track}",
            {"start": start, "end": end, "first_track": first_track, "last_track": last_track},
        )
    except (AudacityConnectionError, ValueError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# effect group

@audacity_cli.group("effect")
def effect_group() -> None:
    """Audio effect commands."""


@effect_group.command("normalize")
@click.option("--peak", "-p", type=float, default=-1.0, help="Peak level in dB")
def effect_normalize(peak: float) -> None:
    """Apply Normalize to the selection."""
    try:
        fx_mod.apply_normalize(_backend, peak)
        emit_result(f"Normalized to {peak} dB", {"effect": "normalize", "peak_db": peak})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@effect_group.command("amplify")
@click.argument("db", type=float)
def effect_amplify(db: float) -> None:
    """Amplify/cut the selection by DB decibels."""
    try:
        fx_mod.apply_amplify(_backend, db)
        emit_result(f"Amplified by {db} dB", {"effect": "amplify", "gain_db": db})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@effect_group.command("fade-in")
def effect_fade_in() -> None:
    """Apply fade-in to the selection."""
    try:
        fx_mod.apply_fade_in(_backend)
        emit_result("Fade-in applied", {"effect": "fade_in"})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@effect_group.command("fade-out")
def effect_fade_out() -> None:
    """Apply fade-out to the selection."""
    try:
        fx_mod.apply_fade_out(_backend)
        emit_result("Fade-out applied", {"effect": "fade_out"})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@effect_group.command("eq")
@click.option("--point", "-p", "points", multiple=True,
              help="Frequency=gain control point, e.g. 1000=3.5")
def effect_eq(points: tuple[str, ...]) -> None:
    """Apply Filter Curve EQ.  Pass one or more --point freq=gain pairs."""
    curve: list[tuple[float, float]] = []
    for pt in points:
        try:
            freq_s, gain_s = pt.split("=")
            curve.append((float(freq_s), float(gain_s)))
        except ValueError:
            emit_error(f"Invalid point format: {pt!r}  (expected freq=gain)")
    try:
        fx_mod.apply_eq(_backend, curve)
        emit_result("EQ applied", {"effect": "eq", "points": len(curve)})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@effect_group.command("compress")
@click.option("--threshold", type=float, default=-12.0)
@click.option("--noise-floor", type=float, default=-40.0)
@click.option("--ratio", type=float, default=2.0)
@click.option("--attack", type=float, default=0.2)
@click.option("--release", type=float, default=1.0)
def effect_compress(
    threshold: float, noise_floor: float, ratio: float, attack: float, release: float
) -> None:
    """Apply the Compressor effect."""
    try:
        fx_mod.apply_compressor(_backend, threshold, noise_floor, ratio, attack, release)
        emit_result(
            "Compressor applied",
            {"effect": "compress", "threshold": threshold, "ratio": ratio},
        )
    except AudacityConnectionError as exc:
        emit_error(str(exc))


@effect_group.command("reverb")
@click.option("--room-size", type=float, default=75.0)
@click.option("--reverberance", type=float, default=50.0)
@click.option("--damping", type=float, default=50.0)
@click.option("--tone-low", type=float, default=100.0)
@click.option("--tone-high", type=float, default=100.0)
@click.option("--wet-gain", type=float, default=-1.0)
@click.option("--stereo-width", type=float, default=100.0)
def effect_reverb(
    room_size: float, reverberance: float, damping: float,
    tone_low: float, tone_high: float, wet_gain: float, stereo_width: float,
) -> None:
    """Apply the Reverb effect."""
    try:
        fx_mod.apply_reverb(
            _backend, room_size, reverberance, damping,
            tone_low, tone_high, wet_gain, stereo_width,
        )
        emit_result("Reverb applied", {"effect": "reverb", "room_size": room_size})
    except AudacityConnectionError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# export

@audacity_cli.command("export")
@click.option("--format", "fmt",
              type=click.Choice(["wav", "mp3", "flac", "ogg", "aiff"]),
              default="wav", help="Output format")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--quality", "-q", type=float, default=None,
              help="Quality or compression level (format-dependent)")
def cmd_export(fmt: str, output: str, quality: float | None) -> None:
    """Export the current project to an audio file."""
    try:
        if fmt == "wav":
            exp_mod.export_wav(_backend, output, int(quality) if quality else 16)
        elif fmt == "mp3":
            exp_mod.export_mp3(_backend, output, int(quality) if quality else 2)
        elif fmt == "flac":
            exp_mod.export_flac(_backend, output, int(quality) if quality else 5)
        elif fmt == "ogg":
            exp_mod.export_ogg(_backend, output, quality if quality else 5.0)
        elif fmt == "aiff":
            exp_mod.export_aiff(_backend, output)
        emit_result(f"Exported {fmt.upper()} → {output}", {"format": fmt, "path": output})
    except (AudacityConnectionError, ValueError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# session group

@audacity_cli.group("session")
def session_group() -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Display the current session state."""
    name = ctx.obj.get("session_name", "default")
    session = _get_session(name)
    emit_result(f"Session: {name}", session.status())


@session_group.command("list")
def session_list() -> None:
    """List all saved Audacity sessions."""
    names = AudacitySession.list_sessions()
    emit_result(f"{len(names)} session(s)", names)


@session_group.command("delete")
@click.argument("name")
def session_delete(name: str) -> None:
    """Delete the named session."""
    s = AudacitySession(name)
    if s.delete():
        emit_result(f"Session {name!r} deleted", {"deleted": name})
    else:
        emit_error(f"Session {name!r} not found")


# ---------------------------------------------------------------------------
# repl

@audacity_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL session."""
    from .console import AudacityConsole
    name = ctx.obj.get("session_name", "default")
    session = _get_session(name)
    console = AudacityConsole(session=session, backend=_backend)
    console.cmdloop()


# ---------------------------------------------------------------------------
# clip group

@audacity_cli.group("clip")
def clip_group() -> None:
    """Clip management commands."""


@clip_group.command("add")
@click.argument("track_index", type=int)
@click.argument("source")
@click.option("--name", "-n", default=None, help="Clip display name")
@click.option("--start", "start_seconds", type=float, default=0.0,
              help="Timeline start position in seconds")
@click.option("--end", "end_seconds", type=float, default=None,
              help="Timeline end position in seconds (probed from file when omitted)")
@click.option("--trim-in", "trim_in", type=float, default=0.0,
              help="Source trim-in offset in seconds")
@click.option("--trim-out", "trim_out", type=float, default=0.0,
              help="Source trim-out offset in seconds")
@click.option("--volume", type=float, default=1.0, help="Clip volume multiplier")
@click.pass_context
def clip_add(
    ctx: click.Context,
    track_index: int,
    source: str,
    name: str | None,
    start_seconds: float,
    end_seconds: float | None,
    trim_in: float,
    trim_out: float,
    volume: float,
) -> None:
    """Add a clip from SOURCE to TRACK_INDEX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = clip_mod.add_clip(
            proj, track_index, source, name, start_seconds, end_seconds,
            trim_in, trim_out, volume,
        )
        session.save()
        emit_result(f"Clip added to track {track_index}", result)
    except (IndexError, FileNotFoundError, ValueError) as exc:
        emit_error(str(exc))


@clip_group.command("remove")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.pass_context
def clip_remove(ctx: click.Context, track_index: int, clip_index: int) -> None:
    """Remove CLIP_INDEX from TRACK_INDEX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = clip_mod.remove_clip(proj, track_index, clip_index)
        session.save()
        emit_result(f"Clip {clip_index} removed from track {track_index}", result)
    except IndexError as exc:
        emit_error(str(exc))


@clip_group.command("trim")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--in", "trim_in", type=float, default=0.0, help="Trim-in offset in seconds")
@click.option("--out", "trim_out", type=float, default=0.0, help="Trim-out offset in seconds")
@click.pass_context
def clip_trim(
    ctx: click.Context,
    track_index: int,
    clip_index: int,
    trim_in: float,
    trim_out: float,
) -> None:
    """Set trim-in/out on CLIP_INDEX of TRACK_INDEX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = clip_mod.trim_clip(proj, track_index, clip_index, trim_in, trim_out)
        session.save()
        emit_result(f"Clip {clip_index} trimmed", result)
    except IndexError as exc:
        emit_error(str(exc))


@clip_group.command("split")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.option("--at", "split_at", type=float, required=True,
              help="Timeline position in seconds at which to split")
@click.pass_context
def clip_split(
    ctx: click.Context,
    track_index: int,
    clip_index: int,
    split_at: float,
) -> None:
    """Split CLIP_INDEX on TRACK_INDEX at the given timeline position."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = clip_mod.split_clip(proj, track_index, clip_index, split_at)
        session.save()
        emit_result(f"Clip {clip_index} split at {split_at}s", result)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))


@clip_group.command("move")
@click.argument("track_index", type=int)
@click.argument("clip_index", type=int)
@click.argument("new_start", type=float)
@click.pass_context
def clip_move(
    ctx: click.Context,
    track_index: int,
    clip_index: int,
    new_start: float,
) -> None:
    """Move CLIP_INDEX on TRACK_INDEX to NEW_START seconds."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = clip_mod.move_clip(proj, track_index, clip_index, new_start)
        session.save()
        emit_result(f"Clip {clip_index} moved to {new_start}s", result)
    except IndexError as exc:
        emit_error(str(exc))


@clip_group.command("list")
@click.argument("track_index", type=int)
@click.pass_context
def clip_list(ctx: click.Context, track_index: int) -> None:
    """List all clips on TRACK_INDEX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = clip_mod.list_clips(proj, track_index)
        emit_result(f"{result['count']} clip(s) on track {track_index}", result)
    except IndexError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# label group

@audacity_cli.group("label")
def label_group() -> None:
    """Label management commands."""


@label_group.command("add")
@click.argument("start", type=float)
@click.option("--end", type=float, default=None, help="End time for a region label")
@click.option("--text", "-t", default="", help="Label text")
@click.pass_context
def label_add(
    ctx: click.Context,
    start: float,
    end: float | None,
    text: str,
) -> None:
    """Add a label at START seconds (optionally spanning to --end)."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    result = label_mod.add_label(proj, start, end, text)
    session.save()
    emit_result("Label added", result)


@label_group.command("remove")
@click.argument("label_id")
@click.pass_context
def label_remove(ctx: click.Context, label_id: str) -> None:
    """Remove the label with LABEL_ID."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    try:
        result = label_mod.remove_label(proj, label_id)
        session.save()
        emit_result(f"Label {label_id!r} removed", result)
    except KeyError as exc:
        emit_error(str(exc))


@label_group.command("list")
@click.pass_context
def label_list(ctx: click.Context) -> None:
    """List all labels in the session project."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    result = label_mod.list_labels(proj)
    emit_result(f"{result['count']} label(s)", result)


# ---------------------------------------------------------------------------
# media group

@audacity_cli.group("media")
def media_group() -> None:
    """Media probing commands."""


@media_group.command("probe")
@click.argument("path")
def media_probe(path: str) -> None:
    """Probe the audio file at PATH and display its properties."""
    try:
        info = media_mod.probe_media(path)
        d = info.to_dict()
        if d.get("duration_seconds") is not None:
            d["duration_formatted"] = media_mod.format_duration(d["duration_seconds"])
        d["file_size_human"] = media_mod.format_file_size(d["file_size_bytes"])
        emit_result(f"Probed {path}", d)
    except (FileNotFoundError, ValueError) as exc:
        emit_error(str(exc))


@media_group.command("check")
@click.pass_context
def media_check(ctx: click.Context) -> None:
    """Check that all clip sources in the session project exist on disk."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    proj = session.get_project()
    if proj is None:
        emit_error("No project in session")
        return
    result = media_mod.check_project_media(proj)
    status = "OK" if result["ok"] else f"{len(result['missing'])} missing file(s)"
    emit_result(status, result)


# ---------------------------------------------------------------------------
# Entry point

def main() -> None:
    audacity_cli()


if __name__ == "__main__":
    main()
