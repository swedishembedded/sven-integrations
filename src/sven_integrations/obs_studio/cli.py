"""OBS Studio CLI — command-line interface for OBS via obs-websocket."""

from __future__ import annotations

import click

from ..shared import emit_error, emit_result
from .backend import ObsBackend, ObsConnectionError, ObsRequestError
from .core import audio as audio_mod
from .core import filters as filter_mod
from .core import output as output_mod
from .core import recording as rec_mod
from .core import scenes as scene_mod
from .core import sources as src_mod
from .core import transitions as trans_mod
from .project import ObsSetup
from .session import ObsSession

_backend = ObsBackend()


def _get_session(name: str) -> ObsSession:
    return ObsSession.open_or_create(name)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Root group

@click.group()
@click.option("--session", "-s", "session_name", default="default",
              help="Session name for persisting state.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Emit machine-readable JSON output.")
@click.pass_context
def obs_cli(ctx: click.Context, session_name: str, project_path: str | None, use_json: bool) -> None:
    """OBS Studio integration — control OBS via obs-websocket."""
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


@obs_cli.group("project")
def project_group() -> None:
    """Project management commands."""


@project_group.command("new")
@click.option("--name", default="Untitled", show_default=True, help="Project name.")
@click.option("--output", "-o", "output_path", default=None, help="Write project JSON to this file.")
@click.pass_context
def project_new(ctx: click.Context, name: str, output_path: str | None) -> None:
    """Create a new empty OBS project in the session."""
    import json as _json_mod
    from pathlib import Path
    sess = _get_session(ctx.obj.get("session_name", "default"))
    sess.data["project_name"] = name
    sess.save()
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json_mod.dumps({"name": name, "scenes": [], "sources": []}, indent=2), encoding="utf-8")
    emit_result(
        f"OBS project {name!r} created.",
        {"ok": True, "name": name},
    )


# ---------------------------------------------------------------------------
# connect

@obs_cli.command("connect")
@click.option("--host", default="localhost", help="WebSocket host")
@click.option("--port", default=4455, type=int, help="WebSocket port")
@click.option("--password", default="", help="WebSocket password")
@click.pass_context
def cmd_connect(ctx: click.Context, host: str, port: int, password: str) -> None:
    """Connect to OBS WebSocket."""
    try:
        if not _backend.is_connected():
            _backend.connect(host, port, password)
        session = _get_session(ctx.obj.get("session_name", "default"))
        session.set_connection(host, port, password)
        session.save()
        version = _backend.get_version()
        emit_result(
            f"Connected to OBS {version} at {host}:{port}",
            {"connected": True, "version": version, "host": host, "port": port},
        )
    except ObsConnectionError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# scene group

@obs_cli.group("scene")
def scene_group() -> None:
    """Scene management commands."""


@scene_group.command("list")
def scene_list() -> None:
    """List all scenes."""
    try:
        names = scene_mod.list_scenes(_backend)
        emit_result(f"{len(names)} scene(s)", names)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@scene_group.command("switch")
@click.argument("name")
def scene_switch(name: str) -> None:
    """Switch to the scene named NAME."""
    try:
        scene_mod.switch_scene(_backend, name)
        emit_result(f"Switched to {name!r}", {"scene": name})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@scene_group.command("create")
@click.argument("name")
def scene_create(name: str) -> None:
    """Create a new scene named NAME."""
    try:
        scene_mod.create_scene(_backend, name)
        emit_result(f"Scene {name!r} created", {"scene": name})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@scene_group.command("remove")
@click.argument("name")
def scene_remove(name: str) -> None:
    """Remove the scene named NAME."""
    try:
        scene_mod.remove_scene(_backend, name)
        emit_result(f"Scene {name!r} removed", {"removed": name})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@scene_group.command("current")
def scene_current() -> None:
    """Show the currently active scene."""
    try:
        name = scene_mod.get_current_scene(_backend)
        emit_result(f"Current scene: {name!r}", {"current_scene": name})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# source group

@obs_cli.group("source")
def source_group() -> None:
    """Source management commands."""


@source_group.command("list")
@click.argument("scene")
def source_list(scene: str) -> None:
    """List sources in SCENE."""
    try:
        items = src_mod.list_sources(_backend, scene)
        emit_result(f"{len(items)} source(s) in {scene!r}", items)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@source_group.command("add")
@click.argument("scene")
@click.argument("name")
@click.argument("kind")
@click.pass_context
def source_add(ctx: click.Context, scene: str, name: str, kind: str) -> None:
    """Add a source of KIND named NAME to SCENE."""
    try:
        item = src_mod.add_source(_backend, scene, name, kind)
        emit_result(f"Source {name!r} added to {scene!r}", item)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@source_group.command("remove")
@click.argument("scene")
@click.argument("name")
def source_remove(scene: str, name: str) -> None:
    """Remove source NAME from SCENE."""
    try:
        src_mod.remove_source(_backend, scene, name)
        emit_result(f"Source {name!r} removed from {scene!r}", {"removed": name})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@source_group.command("volume")
@click.argument("name")
@click.argument("db", type=float)
def source_volume(name: str, db: float) -> None:
    """Set volume of source NAME to DB decibels."""
    try:
        src_mod.set_source_volume(_backend, name, db)
        emit_result(f"Volume of {name!r} → {db} dB", {"source": name, "volume_db": db})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@source_group.command("mute")
@click.argument("name")
@click.option("--off", "unmute", is_flag=True, default=False, help="Unmute instead")
def source_mute(name: str, unmute: bool) -> None:
    """Mute (or unmute with --off) source NAME."""
    try:
        if unmute:
            src_mod.unmute_source(_backend, name)
            emit_result(f"Source {name!r} unmuted", {"source": name, "muted": False})
        else:
            src_mod.mute_source(_backend, name)
            emit_result(f"Source {name!r} muted", {"source": name, "muted": True})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@source_group.command("visible")
@click.argument("scene")
@click.argument("name")
@click.argument("state", type=click.Choice(["on", "off"]))
def source_visible(scene: str, name: str, state: str) -> None:
    """Set visibility of source NAME in SCENE to on or off."""
    try:
        flag = state == "on"
        src_mod.set_source_visible(_backend, scene, name, flag)
        emit_result(
            f"Source {name!r} {'shown' if flag else 'hidden'}",
            {"source": name, "visible": flag},
        )
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# record group

@obs_cli.group("record")
def record_group() -> None:
    """Recording management commands."""


@record_group.command("start")
def record_start() -> None:
    """Start recording."""
    try:
        rec_mod.start_recording(_backend)
        emit_result("Recording started", {"recording": True})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@record_group.command("stop")
def record_stop() -> None:
    """Stop recording."""
    try:
        info = rec_mod.stop_recording(_backend)
        emit_result("Recording stopped", info)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@record_group.command("status")
def record_status() -> None:
    """Show recording status."""
    try:
        info = rec_mod.get_recording_status(_backend)
        emit_result("Recording status", info)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# stream group

@obs_cli.group("stream")
def stream_group() -> None:
    """Streaming management commands."""


@stream_group.command("start")
def stream_start() -> None:
    """Start streaming."""
    try:
        rec_mod.start_streaming(_backend)
        emit_result("Streaming started", {"streaming": True})
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@stream_group.command("stop")
def stream_stop() -> None:
    """Stop streaming."""
    try:
        info = rec_mod.stop_streaming(_backend)
        emit_result("Streaming stopped", info)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


@stream_group.command("status")
def stream_status() -> None:
    """Show streaming status."""
    try:
        info = rec_mod.get_streaming_status(_backend)
        emit_result("Streaming status", info)
    except (ObsConnectionError, ObsRequestError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# session group

@obs_cli.group("session")
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
    """List all saved OBS sessions."""
    names = ObsSession.list_sessions()
    emit_result(f"{len(names)} session(s)", names)


@session_group.command("delete")
@click.argument("name")
def session_delete(name: str) -> None:
    """Delete the named session."""
    s = ObsSession(name)
    if s.delete():
        emit_result(f"Session {name!r} deleted", {"deleted": name})
    else:
        emit_error(f"Session {name!r} not found")


# ---------------------------------------------------------------------------
# repl

@obs_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL session."""
    from .console import ObsConsole
    name = ctx.obj.get("session_name", "default")
    session = _get_session(name)
    console = ObsConsole(session=session, backend=_backend)
    console.cmdloop()


# ---------------------------------------------------------------------------
# audio group

@obs_cli.group("audio")
def audio_group() -> None:
    """Audio source management commands."""


def _load_obs_setup(session_name: str) -> ObsSetup:
    sess = _get_session(session_name)
    raw = sess.data.get("setup")
    if raw:
        return ObsSetup.from_dict(raw)
    return ObsSetup(profile_name="default", scene_collection_name="default")


def _save_obs_setup(session_name: str, setup: ObsSetup) -> None:
    sess = _get_session(session_name)
    sess.data["setup"] = setup.to_dict()
    sess.save()


@audio_group.command("add")
@click.option("--name", required=True, help="Source name.")
@click.option("--type", "audio_type", default="input",
              type=click.Choice(["input", "output"]), help="Audio type.")
@click.option("--device", default=None, help="Device identifier.")
@click.option("--volume", default=1.0, type=float, help="Volume multiplier (0–3).")
@click.pass_context
def audio_add(
    ctx: click.Context,
    name: str,
    audio_type: str,
    device: str | None,
    volume: float,
) -> None:
    """Add an audio source."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = audio_mod.add_audio_source(setup, name, audio_type, device, volume)
    except ValueError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Added audio source {name!r}", result)


@audio_group.command("remove")
@click.argument("index", type=int)
@click.pass_context
def audio_remove(ctx: click.Context, index: int) -> None:
    """Remove the audio source at INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        removed = audio_mod.remove_audio_source(setup, index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Removed audio source {index}", removed)


@audio_group.command("volume")
@click.argument("index", type=int)
@click.argument("level", type=float)
@click.pass_context
def audio_volume(ctx: click.Context, index: int, level: float) -> None:
    """Set the volume multiplier for audio source at INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = audio_mod.set_volume(setup, index, level)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Volume set to {level}", result)


@audio_group.command("mute")
@click.argument("index", type=int)
@click.pass_context
def audio_mute(ctx: click.Context, index: int) -> None:
    """Mute audio source at INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = audio_mod.mute_source(setup, index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Source {index} muted", result)


@audio_group.command("unmute")
@click.argument("index", type=int)
@click.pass_context
def audio_unmute(ctx: click.Context, index: int) -> None:
    """Unmute audio source at INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = audio_mod.unmute_source(setup, index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Source {index} unmuted", result)


@audio_group.command("monitor")
@click.argument("index", type=int)
@click.argument("monitor_type", type=click.Choice(["none", "monitor_only", "monitor_and_output"]))
@click.pass_context
def audio_monitor(ctx: click.Context, index: int, monitor_type: str) -> None:
    """Set monitor type for audio source at INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = audio_mod.set_monitor(setup, index, monitor_type)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Monitor type → {monitor_type}", result)


@audio_group.command("list")
@click.pass_context
def audio_list(ctx: click.Context) -> None:
    """List all audio sources."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    info = audio_mod.list_audio(setup)
    emit_result(f"{info['count']} audio source(s)", info)


# ---------------------------------------------------------------------------
# filter group

@obs_cli.group("filter")
def filter_group() -> None:
    """Source filter management commands."""


@filter_group.command("add")
@click.argument("filter_type")
@click.option("--source", required=True, help="Source name to attach filter to.")
@click.option("--name", default=None, help="Filter name.")
@click.option("--param", "-p", multiple=True, help="key=value parameter.")
@click.pass_context
def filter_add(
    ctx: click.Context,
    filter_type: str,
    source: str,
    name: str | None,
    param: tuple[str, ...],
) -> None:
    """Add a filter of FILTER_TYPE to --source."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
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
        result = filter_mod.add_filter(setup, filter_type, source, name, params)
    except (ValueError, KeyError) as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Filter {filter_type!r} added to {source!r}", result)


@filter_group.command("remove")
@click.argument("source")
@click.argument("filter_index", type=int)
@click.pass_context
def filter_remove(ctx: click.Context, source: str, filter_index: int) -> None:
    """Remove filter at FILTER_INDEX from SOURCE."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        removed = filter_mod.remove_filter(setup, source, filter_index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Removed filter {filter_index} from {source!r}", removed)


@filter_group.command("set")
@click.argument("source")
@click.argument("filter_index", type=int)
@click.argument("param_name")
@click.argument("value")
@click.pass_context
def filter_set(
    ctx: click.Context,
    source: str,
    filter_index: int,
    param_name: str,
    value: str,
) -> None:
    """Set a parameter on an existing filter."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        parsed: object
        try:
            parsed = int(value) if "." not in value else float(value)
        except ValueError:
            parsed = value
        result = filter_mod.set_filter_param(setup, source, filter_index, param_name, parsed)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Filter param {param_name} = {value}", result)


@filter_group.command("list")
@click.argument("source")
@click.pass_context
def filter_list(ctx: click.Context, source: str) -> None:
    """List filters on SOURCE."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    info = filter_mod.list_filters(setup, source)
    emit_result(f"{info['count']} filter(s) on {source!r}", info)


@filter_group.command("available")
@click.option("--category", default=None, help="Filter by category (video/audio).")
def filter_available(category: str | None) -> None:
    """List all available filter types."""
    items = filter_mod.list_available_filters(category)
    emit_result(f"{len(items)} available filter(s)", items)


# ---------------------------------------------------------------------------
# output group

@obs_cli.group("output")
def output_group() -> None:
    """Output configuration commands."""


@output_group.command("streaming")
@click.option("--service", default="custom", help="Streaming service name.")
@click.option("--server", required=True, help="RTMP server URL.")
@click.option("--key", required=True, help="Stream key.")
@click.pass_context
def output_streaming(ctx: click.Context, service: str, server: str, key: str) -> None:
    """Configure streaming destination."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    result = output_mod.set_streaming(setup, service, server, key)
    _save_obs_setup(session_name, setup)
    emit_result("Streaming config saved", result)


@output_group.command("recording")
@click.option("--path", required=True, help="Output directory path.")
@click.option("--format", "fmt", default="mkv",
              type=click.Choice(["mkv", "mp4", "flv", "mov"]), help="Container format.")
@click.option("--quality", default="high",
              type=click.Choice(["high", "medium", "low", "lossless"]), help="Quality preset.")
@click.pass_context
def output_recording(ctx: click.Context, path: str, fmt: str, quality: str) -> None:
    """Configure recording output."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = output_mod.set_recording(setup, path, fmt, quality)
    except ValueError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result("Recording config saved", result)


@output_group.command("settings")
@click.option("--width", default=1920, type=int)
@click.option("--height", default=1080, type=int)
@click.option("--fps", default=30, type=int)
@click.option("--video-bitrate", "video_bitrate", default=6000, type=int,
              help="Video bitrate kbps.")
@click.option("--audio-bitrate", "audio_bitrate", default=160, type=int,
              help="Audio bitrate kbps.")
@click.option("--encoder", default="x264")
@click.option("--preset", default="veryfast",
              help="Encoder preset name (or use --preset from built-ins).")
@click.pass_context
def output_settings(
    ctx: click.Context,
    width: int,
    height: int,
    fps: int,
    video_bitrate: int,
    audio_bitrate: int,
    encoder: str,
    preset: str,
) -> None:
    """Set encoding output settings."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    result = output_mod.set_output_settings(
        setup, width, height, fps, video_bitrate, audio_bitrate, encoder, preset
    )
    _save_obs_setup(session_name, setup)
    emit_result("Output settings saved", result)


@output_group.command("info")
@click.pass_context
def output_info(ctx: click.Context) -> None:
    """Show current output configuration."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    info = output_mod.get_output_info(setup)
    emit_result("Output configuration", info)


@output_group.command("presets")
def output_presets() -> None:
    """List all built-in encoding presets."""
    presets = output_mod.list_presets()
    emit_result(f"{len(presets)} preset(s)", presets)


# ---------------------------------------------------------------------------
# transition group

@obs_cli.group("transition")
def transition_group() -> None:
    """Scene transition management commands."""


@transition_group.command("add")
@click.argument("transition_type",
                type=click.Choice(trans_mod.TRANSITION_TYPES))
@click.option("--name", default=None, help="Transition name.")
@click.option("--duration", "duration_ms", default=300, type=int,
              help="Duration in milliseconds.")
@click.pass_context
def transition_add(
    ctx: click.Context,
    transition_type: str,
    name: str | None,
    duration_ms: int,
) -> None:
    """Add a new scene transition."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = trans_mod.add_transition(setup, transition_type, name, duration_ms)
    except ValueError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Transition {transition_type!r} added", result)


@transition_group.command("remove")
@click.argument("index", type=int)
@click.pass_context
def transition_remove(ctx: click.Context, index: int) -> None:
    """Remove the transition at INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        removed = trans_mod.remove_transition(setup, index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Removed transition {index}", removed)


@transition_group.command("set-active")
@click.argument("index", type=int)
@click.pass_context
def transition_set_active(ctx: click.Context, index: int) -> None:
    """Set the active transition to INDEX."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = trans_mod.set_active_transition(setup, index)
    except IndexError as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Active transition → {index}", result)


@transition_group.command("duration")
@click.argument("index", type=int)
@click.argument("ms", type=int)
@click.pass_context
def transition_duration(ctx: click.Context, index: int, ms: int) -> None:
    """Set the duration of transition at INDEX to MS milliseconds."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    try:
        result = trans_mod.set_duration(setup, index, ms)
    except (IndexError, ValueError) as exc:
        emit_error(str(exc))
    _save_obs_setup(session_name, setup)
    emit_result(f"Duration → {ms}ms", result)


@transition_group.command("list")
@click.pass_context
def transition_list(ctx: click.Context) -> None:
    """List all scene transitions."""
    session_name = ctx.obj.get("session_name", "default")
    setup = _load_obs_setup(session_name)
    info = trans_mod.list_transitions(setup)
    emit_result(f"{info['count']} transition(s)", info)


# ---------------------------------------------------------------------------
# Entry point

def main() -> None:
    obs_cli()


if __name__ == "__main__":
    main()
