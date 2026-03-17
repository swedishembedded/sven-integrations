"""Zoom CLI — sven-integrations-zoom entry point."""

from __future__ import annotations

from typing import Optional

import click

from ..shared import emit, emit_error, emit_json, emit_result
from .backend import ZoomApiError
from .core import auth as auth_mod
from .core import meetings as meet_mod
from .core import participants as part_mod
from .core import recordings as rec_mod
from .project import ZoomMeetingConfig
from .session import ZoomSession

# ---------------------------------------------------------------------------
# Shared helpers


def _get_session(name: str) -> ZoomSession:
    return ZoomSession.open_or_create(name)  # type: ignore[return-value]


def _require_token(sess: ZoomSession) -> str:
    if not sess.is_authenticated():
        emit_error("Not authenticated. Run 'zoom auth login' first.")
    return sess.oauth_token  # type: ignore[return-value]


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
def zoom_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """Zoom CLI — manage meetings and recordings from the command line."""
    from ..shared.output import set_json_mode

    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    if project_path is not None:
        sess = _get_session(session)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# auth group


@zoom_cli.group("auth")
def auth_grp() -> None:
    """Authentication commands."""


@auth_grp.command("login")
@click.option("--client-id", required=True, envvar="ZOOM_CLIENT_ID", help="OAuth client ID.")
@click.option("--client-secret", required=True, envvar="ZOOM_CLIENT_SECRET", help="OAuth client secret.")
@click.option("--code", default=None, help="Auth code (skip browser flow).")
@click.option("--redirect-uri", default="http://localhost:4199/callback", help="OAuth redirect URI.")
@click.pass_context
def auth_login(
    ctx: click.Context,
    client_id: str,
    client_secret: str,
    code: Optional[str],
    redirect_uri: str,
) -> None:
    """Authenticate with Zoom via OAuth."""
    sess = _get_session(ctx.obj["session"])

    if code:
        try:
            token_data = auth_mod.exchange_code(client_id, client_secret, code, redirect_uri)
        except ZoomApiError as exc:
            emit_error(str(exc))
        sess.set_token(
            token_data["access_token"],
            float(token_data.get("expires_in", 3600)),
            refresh_token=token_data.get("refresh_token", ""),
        )
        emit_result("Authenticated successfully.", {"status": "ok"})
    else:
        url = auth_mod.build_oauth_url(client_id, redirect_uri)
        emit(f"\nOpen this URL in your browser to authorise:\n\n  {url}\n")
        emit("Then re-run with --code=<code> once you have the authorisation code.")


@auth_grp.command("status")
@click.pass_context
def auth_status(ctx: click.Context) -> None:
    """Show authentication status."""
    sess = _get_session(ctx.obj["session"])
    emit_json(
        {
            "authenticated": sess.is_authenticated(),
            "token_expiry": sess.token_expiry,
        }
    )


@auth_grp.command("logout")
@click.pass_context
def auth_logout(ctx: click.Context) -> None:
    """Revoke and clear stored tokens."""
    sess = _get_session(ctx.obj["session"])
    token = sess.oauth_token
    if token:
        try:
            auth_mod.revoke_token(token)
        except ZoomApiError:
            pass  # best-effort revocation
    sess.clear_auth()
    emit_result("Logged out.", {"status": "ok"})


# ---------------------------------------------------------------------------
# meeting group


@zoom_cli.group("meeting")
def meeting_grp() -> None:
    """Meeting management commands."""


@meeting_grp.command("create")
@click.option("--topic", required=True, help="Meeting topic.")
@click.option("--duration", default=60, type=int, help="Duration in minutes.")
@click.option("--timezone", default="UTC", help="IANA timezone.")
@click.option("--passcode", default="", help="Meeting passcode.")
@click.option("--no-waiting-room", is_flag=True, default=False)
@click.option("--record", is_flag=True, default=False, help="Enable cloud recording.")
@click.pass_context
def meeting_create(
    ctx: click.Context,
    topic: str,
    duration: int,
    timezone: str,
    passcode: str,
    no_waiting_room: bool,
    record: bool,
) -> None:
    """Create a new scheduled meeting."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    cfg = ZoomMeetingConfig(
        topic=topic,
        host_email="me",
        duration_minutes=duration,
        timezone=timezone,
        passcode=passcode,
        waiting_room=not no_waiting_room,
        recording_enabled=record,
    )
    try:
        result = meet_mod.create_meeting(token, "me", cfg)
    except (ZoomApiError, ValueError) as exc:
        emit_error(str(exc))
    emit_result(
        f"Meeting created: {result.get('id')}",
        result,
    )


@meeting_grp.command("list")
@click.pass_context
def meeting_list(ctx: click.Context) -> None:
    """List upcoming scheduled meetings."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        meetings = meet_mod.list_meetings(token, "me")
    except ZoomApiError as exc:
        emit_error(str(exc))
    emit_json(meetings)


@meeting_grp.command("get")
@click.option("--id", "meeting_id", required=True, help="Meeting ID.")
@click.pass_context
def meeting_get(ctx: click.Context, meeting_id: str) -> None:
    """Get meeting details."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        info = meet_mod.get_meeting(token, meeting_id)
    except ZoomApiError as exc:
        emit_error(str(exc))
    emit_json(info)


@meeting_grp.command("delete")
@click.option("--id", "meeting_id", required=True, help="Meeting ID.")
@click.pass_context
def meeting_delete(ctx: click.Context, meeting_id: str) -> None:
    """Delete a meeting."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        meet_mod.delete_meeting(token, meeting_id)
    except ZoomApiError as exc:
        emit_error(str(exc))
    emit_result(f"Meeting {meeting_id} deleted.", {"status": "ok", "meeting_id": meeting_id})


@meeting_grp.command("url")
@click.option("--id", "meeting_id", required=True, help="Meeting ID.")
@click.option("--passcode", default=None, help="Passcode for the URL.")
@click.option("--host", is_flag=True, default=False, help="Return host start URL.")
@click.pass_context
def meeting_url(ctx: click.Context, meeting_id: str, passcode: Optional[str], host: bool) -> None:
    """Return the join or start URL for a meeting."""
    if host:
        url = meet_mod.start_meeting_url(meeting_id, passcode)
    else:
        url = meet_mod.join_meeting_url(meeting_id, passcode)
    emit_result(url, {"url": url, "meeting_id": meeting_id})


# ---------------------------------------------------------------------------
# recording group


@zoom_cli.group("recording")
def recording_grp() -> None:
    """Recording management commands."""


@recording_grp.command("list")
@click.option("--from", "from_date", required=True, help="Start date (YYYY-MM-DD).")
@click.option("--to", "to_date", required=True, help="End date (YYYY-MM-DD).")
@click.pass_context
def recording_list(ctx: click.Context, from_date: str, to_date: str) -> None:
    """List cloud recordings in a date range."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        recordings = rec_mod.list_recordings(token, "me", from_date, to_date)
    except ZoomApiError as exc:
        emit_error(str(exc))
    emit_json(recordings)


@recording_grp.command("download")
@click.option("--meeting-id", required=True, help="Meeting ID to download from.")
@click.option("--output", "-o", required=True, help="Output file path.")
@click.pass_context
def recording_download(ctx: click.Context, meeting_id: str, output: str) -> None:
    """Download the first recording file from a meeting."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        info = rec_mod.get_recording_info(token, meeting_id)
        files = info.get("recording_files", [])
        if not files:
            emit_error("No recording files found for this meeting.")
        download_url = files[0]["download_url"]
        path = rec_mod.download_recording(token, download_url, output)
    except ZoomApiError as exc:
        emit_error(str(exc))
    emit_result(f"Downloaded to {path}", {"status": "ok", "path": str(path)})


# ---------------------------------------------------------------------------
# participant group


@zoom_cli.group("participant")
def participant_grp() -> None:
    """Meeting registrant and participant commands."""


@participant_grp.command("add")
@click.argument("meeting_id")
@click.option("--email", required=True, help="Registrant email.")
@click.option("--first-name", "first_name", required=True, help="First name.")
@click.option("--last-name", "last_name", required=True, help="Last name.")
@click.pass_context
def participant_add(
    ctx: click.Context,
    meeting_id: str,
    email: str,
    first_name: str,
    last_name: str,
) -> None:
    """Register a single attendee for MEETING_ID."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        result = part_mod.add_registrant(token, meeting_id, email, first_name, last_name)
    except RuntimeError as exc:
        emit_error(str(exc))
    emit_result(f"Registered {email}", result)


@participant_grp.command("batch")
@click.argument("meeting_id")
@click.argument("csv_file", type=click.Path(exists=True))
@click.pass_context
def participant_batch(ctx: click.Context, meeting_id: str, csv_file: str) -> None:
    """Batch-register attendees from a CSV file (email,first_name,last_name)."""
    import csv as csv_mod
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    registrants: list[dict[str, str]] = []
    try:
        with open(csv_file, newline="", encoding="utf-8") as fh:
            reader = csv_mod.DictReader(fh)
            for row in reader:
                registrants.append({
                    "email": row.get("email", ""),
                    "first_name": row.get("first_name", ""),
                    "last_name": row.get("last_name", ""),
                })
    except OSError as exc:
        emit_error(f"Cannot read CSV: {exc}")
    try:
        result = part_mod.add_batch_registrants(token, meeting_id, registrants)
    except RuntimeError as exc:
        emit_error(str(exc))
    emit_result(
        f"Batch registered {len(result.get('added', []))} of {result.get('total', 0)}",
        result,
    )


@participant_grp.command("list")
@click.argument("meeting_id")
@click.option("--status", default="approved",
              type=click.Choice(["pending", "approved", "denied"]),
              help="Filter registrants by status.")
@click.pass_context
def participant_list(ctx: click.Context, meeting_id: str, status: str) -> None:
    """List registrants for MEETING_ID."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        items = part_mod.list_registrants(token, meeting_id, status)
    except RuntimeError as exc:
        emit_error(str(exc))
    emit_json(items)


@participant_grp.command("remove")
@click.argument("meeting_id")
@click.argument("registrant_id")
@click.pass_context
def participant_remove(ctx: click.Context, meeting_id: str, registrant_id: str) -> None:
    """Cancel/remove registrant REGISTRANT_ID from MEETING_ID."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        result = part_mod.remove_registrant(token, meeting_id, registrant_id)
    except RuntimeError as exc:
        emit_error(str(exc))
    emit_result(f"Removed registrant {registrant_id}", result)


@participant_grp.command("attended")
@click.argument("meeting_id")
@click.pass_context
def participant_attended(ctx: click.Context, meeting_id: str) -> None:
    """List participants who attended a past meeting (by meeting UUID)."""
    sess = _get_session(ctx.obj["session"])
    token = _require_token(sess)
    try:
        items = part_mod.list_past_participants(token, meeting_id)
    except RuntimeError as exc:
        emit_error(str(exc))
    emit_json(items)


# ---------------------------------------------------------------------------
# session group


@zoom_cli.group("session")
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
    emit_json(ZoomSession.list_sessions())


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


@zoom_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL session."""
    from .console import ZoomConsole

    console = ZoomConsole(session_name=ctx.obj["session"])
    console.cmdloop()


# ---------------------------------------------------------------------------
# Entry point


def main() -> None:
    zoom_cli()


if __name__ == "__main__":
    main()
