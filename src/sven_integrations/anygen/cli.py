"""CLI entry point for the AnyGen harness."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import click

from ..shared import cli_main, emit, emit_error, emit_json, emit_result
from .backend import AnygenBackend, AnygenError
from .core.verify import VerifyError, verify_file
from .project import VALID_OPERATIONS, AnygenTask, HistoryEntry
from .session import AnygenSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session(ctx: click.Context) -> AnygenSession:
    name: str = ctx.obj.get("session", "default")
    return AnygenSession.open_or_create(name)


def _make_backend(session: AnygenSession) -> AnygenBackend:
    return AnygenBackend(
        api_key=session.get_api_key(),
        base_url=session.get_api_base_url(),
    )


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group("anygen")
@click.option("--session", "-s", default="default", help="Session name.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False, help="JSON output.")
@click.pass_context
def anygen_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """AnyGen AI content-generation CLI (PPTX, DOCX, PDF, images, data)."""
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    ctx.obj["json"] = use_json
    from ..shared.output import set_json_mode

    set_json_mode(use_json)
    if project_path is not None:
        sess = _get_session(ctx)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@anygen_cli.group("config")
def config_group() -> None:
    """Manage AnyGen configuration (api_key, api_base_url, …)."""


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a configuration value.\n\nExample: config set api_key sk-ag-…"""
    session = _get_session(ctx)
    session.set_config(key, value)
    session.save()
    masked = value[:6] + "…" if len(value) > 8 else value
    emit_result(
        f"Set {key} = {masked!r}",
        {"status": "ok", "key": key},
    )


@config_group.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Get a configuration value."""
    session = _get_session(ctx)
    val = session.get_config(key)
    if val is None:
        emit_error(f"Config key {key!r} is not set.")
    if ctx.obj.get("json"):
        emit_json({"key": key, "value": val})
    else:
        emit(val or "")


@config_group.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """List all configuration values."""
    session = _get_session(ctx)
    cfg = session.all_config()
    masked = {
        k: (v[:6] + "…" + v[-4:] if k.lower().endswith(("key", "secret", "token")) and len(v) > 12 else v)
        for k, v in cfg.items()
    }
    if ctx.obj.get("json"):
        emit_json(masked)
    else:
        if not masked:
            emit("  (no configuration set)")
        for k, v in masked.items():
            emit(f"  {k} = {v}")


# ---------------------------------------------------------------------------
# task
# ---------------------------------------------------------------------------


@anygen_cli.group("task")
def task_group() -> None:
    """Create, monitor, and download AnyGen generation tasks."""


@task_group.command("run")
@click.option(
    "--operation", "-op",
    required=True,
    type=click.Choice(sorted(VALID_OPERATIONS)),
    help="Content type: slide (PPTX), doc (DOCX), pdf, image (PNG), data (JSON).",
)
@click.option("--prompt", "-p", required=True, help="Natural-language generation prompt.")
@click.option(
    "--output", "-o",
    default=".",
    show_default=True,
    help="Output directory (a filename is derived from the task_id).",
)
@click.option(
    "--timeout",
    default=300,
    type=float,
    show_default=True,
    help="Maximum seconds to wait for completion.",
)
@click.pass_context
def task_run(
    ctx: click.Context,
    operation: str,
    prompt: str,
    output: str,
    timeout: float,
) -> None:
    """Full workflow: create → poll → download.

    The output file is written to OUTPUT (a directory or explicit path).
    """
    session = _get_session(ctx)
    be = _make_backend(session)
    be.timeout = timeout

    local_id = str(uuid.uuid4())
    task = AnygenTask(local_id=local_id, operation=operation, prompt=prompt)

    # Submit to API
    try:
        remote_id = be.create_task(operation=operation, prompt=prompt)
    except AnygenError as exc:
        emit_error(str(exc))
        return

    task.task_id = remote_id
    task.submitted = True
    task.status = "queued"
    session.upsert_task(task)
    session.push_history(
        HistoryEntry(
            action="create",
            task_id=remote_id,
            details={"operation": operation, "prompt": prompt[:80]},
        )
    )
    session.save()
    emit(f"  created  {remote_id}")

    # Poll until done
    def _progress(data: dict[str, Any]) -> None:
        emit(f"  status   {data.get('status', '?')}")

    try:
        status_data = be.poll_until_done(remote_id, progress_cb=_progress)
    except AnygenError as exc:
        task.status = "failed"
        task.error = str(exc)
        session.upsert_task(task)
        session.save()
        emit_error(str(exc))
        return

    remote_status = status_data.get("status", "unknown")
    task.output_url = status_data.get("output_url") or status_data.get("download_url")

    if remote_status != "completed":
        task.status = "failed"
        task.error = status_data.get("error") or remote_status
        session.upsert_task(task)
        session.save()
        emit_error(f"Task {remote_id} ended with status {remote_status!r}: {task.error}")
        return

    # Download
    dest = Path(output)
    try:
        out_path = be.download(remote_id, dest, operation)
    except AnygenError as exc:
        emit_error(str(exc))
        return

    task.status = "completed"
    task.completed_at = time.time()
    task.output_path = str(out_path)
    session.upsert_task(task)
    session.save()

    emit_result(
        f"  done     {out_path}",
        {
            "status": "completed",
            "task_id": remote_id,
            "operation": operation,
            "output": str(out_path),
        },
    )


@task_group.command("create")
@click.option(
    "--operation", "-op",
    required=True,
    type=click.Choice(sorted(VALID_OPERATIONS)),
)
@click.option("--prompt", "-p", required=True)
@click.pass_context
def task_create(ctx: click.Context, operation: str, prompt: str) -> None:
    """Submit a task to the API; returns task_id for later status/download."""
    session = _get_session(ctx)
    be = _make_backend(session)
    local_id = str(uuid.uuid4())

    try:
        remote_id = be.create_task(operation=operation, prompt=prompt)
    except AnygenError as exc:
        emit_error(str(exc))
        return

    task = AnygenTask(
        local_id=local_id,
        operation=operation,
        prompt=prompt,
        task_id=remote_id,
        submitted=True,
        status="queued",
    )
    session.upsert_task(task)
    session.push_history(
        HistoryEntry(
            action="create",
            task_id=remote_id,
            details={"operation": operation, "prompt": prompt[:80]},
        )
    )
    session.save()

    emit_result(
        f"  task_id  {remote_id}  [{operation}]",
        {"status": "queued", "task_id": remote_id, "operation": operation},
    )


@task_group.command("status")
@click.argument("task_id")
@click.pass_context
def task_status(ctx: click.Context, task_id: str) -> None:
    """Check the current status of a task."""
    session = _get_session(ctx)
    be = _make_backend(session)

    local_task = session.find_task(task_id)
    remote_id = local_task.task_id if (local_task and local_task.task_id) else task_id

    try:
        data = be.get_status(remote_id)
    except AnygenError as exc:
        emit_error(str(exc))
        return

    # Sync local state
    if local_task:
        local_task.status = data.get("status", local_task.status)
        local_task.output_url = (
            data.get("output_url") or data.get("download_url") or local_task.output_url
        )
        if data.get("error"):
            local_task.error = data["error"]
        session.upsert_task(local_task)
        session.save()

    if ctx.obj.get("json"):
        emit_json(data)
    else:
        emit(f"  task_id  {remote_id}")
        emit(f"  status   {data.get('status', 'unknown')}")
        if data.get("error"):
            emit(f"  error    {data['error']}")
        if data.get("output_url"):
            emit(f"  url      {data['output_url']}")
        if data.get("progress") is not None:
            emit(f"  progress {data['progress']}%")


@task_group.command("download")
@click.argument("task_id")
@click.option(
    "--output", "-o",
    required=True,
    help="Destination: a directory (auto-named) or an explicit file path.",
)
@click.pass_context
def task_download(ctx: click.Context, task_id: str, output: str) -> None:
    """Download the output of a completed task."""
    session = _get_session(ctx)
    be = _make_backend(session)

    local_task = session.find_task(task_id)
    remote_id = local_task.task_id if (local_task and local_task.task_id) else task_id
    operation = local_task.operation if local_task else "data"

    dest = Path(output)
    try:
        out_path = be.download(remote_id, dest, operation)
    except AnygenError as exc:
        emit_error(str(exc))
        return

    if local_task:
        local_task.output_path = str(out_path)
        local_task.status = "completed"
        local_task.completed_at = time.time()
        session.upsert_task(local_task)
        session.save()

    emit_result(
        f"  downloaded  {out_path}",
        {"status": "downloaded", "task_id": remote_id, "output": str(out_path)},
    )


@task_group.command("list")
@click.pass_context
def task_list(ctx: click.Context) -> None:
    """List all tasks tracked in the current session."""
    session = _get_session(ctx)
    tasks = session.load_tasks()

    if ctx.obj.get("json"):
        emit_json([t.to_dict() for t in tasks])
        return

    if not tasks:
        emit("  (no tasks)")
        return

    for t in tasks:
        sym = "✓" if t.status == "completed" else ("✗" if t.status == "failed" else "·")
        tid = t.task_id or t.local_id
        out = f"  → {t.output_path}" if t.output_path else ""
        emit(f"  {sym} {tid[:24]}  [{t.operation:5}]  {t.status}{out}")


@task_group.command("prepare")
@click.option(
    "--operation", "-op",
    required=True,
    type=click.Choice(sorted(VALID_OPERATIONS)),
)
@click.option("--prompt", "-p", required=True)
@click.pass_context
def task_prepare(ctx: click.Context, operation: str, prompt: str) -> None:
    """Save a task locally without submitting it (multi-turn preparation).

    Use this to stage a task and refine it before committing with 'task create'.
    """
    session = _get_session(ctx)
    local_id = str(uuid.uuid4())
    task = AnygenTask(
        local_id=local_id,
        operation=operation,
        prompt=prompt,
        status="pending",
        submitted=False,
    )
    session.upsert_task(task)
    session.push_history(
        HistoryEntry(
            action="prepare",
            task_id=local_id,
            details={"operation": operation, "prompt": prompt[:80]},
        )
    )
    session.save()

    emit_result(
        f"  prepared  {local_id}  [{operation}]",
        {"status": "pending", "local_id": local_id, "operation": operation, "prompt": prompt},
    )


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------


@anygen_cli.group("file")
def file_group() -> None:
    """File inspection utilities."""


@file_group.command("verify")
@click.argument("path")
@click.pass_context
def file_verify(ctx: click.Context, path: str) -> None:
    """Check the integrity of a generated file (PPTX, DOCX, PDF, PNG, SVG, …)."""
    try:
        result = verify_file(path)
    except VerifyError as exc:
        emit_error(str(exc))
        return

    emit_result(
        f"  ok  {result['path']}  ({result['type']}, {result['size']} bytes)  {result['details']}",
        result,
    )


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------


@anygen_cli.group("session")
def session_group() -> None:
    """Session management."""


@session_group.command("undo")
@click.pass_context
def session_undo(ctx: click.Context) -> None:
    """Undo the last recorded action."""
    session = _get_session(ctx)
    entry = session.undo()
    session.save()
    if entry is None:
        emit("  (nothing to undo)")
        return
    emit_result(
        f"  undone  {entry.action}  task={entry.task_id}",
        {"status": "undone", "action": entry.action, "task_id": entry.task_id},
    )


@session_group.command("redo")
@click.pass_context
def session_redo(ctx: click.Context) -> None:
    """Redo the last undone action."""
    session = _get_session(ctx)
    entry = session.redo()
    session.save()
    if entry is None:
        emit("  (nothing to redo)")
        return
    emit_result(
        f"  redone  {entry.action}  task={entry.task_id}",
        {"status": "redone", "action": entry.action, "task_id": entry.task_id},
    )


@session_group.command("history")
@click.pass_context
def session_history(ctx: click.Context) -> None:
    """Show action history for the current session."""
    session = _get_session(ctx)
    history = session.load_history()
    items = [e.to_dict() for e in history]

    if ctx.obj.get("json"):
        emit_json(items)
        return

    if not items:
        emit("  (no history)")
        return

    for i, e in enumerate(history, 1):
        ts = time.strftime("%H:%M:%S", time.localtime(e.timestamp))
        tid = (e.task_id or "-")[:24]
        emit(f"  {i:3}. [{ts}] {e.action:10}  {tid}")


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Show current session summary."""
    session = _get_session(ctx)
    tasks = session.load_tasks()
    history = session.load_history()
    emit_result(
        f"  session={session.name!r}  tasks={len(tasks)}  history={len(history)}",
        {
            "name": session.name,
            "harness": session.harness,
            "task_count": len(tasks),
            "history_count": len(history),
        },
    )


@session_group.command("list")
def session_list_cmd() -> None:
    """List all saved sessions."""
    for name in AnygenSession.list_sessions():
        emit(f"  {name}")


@session_group.command("delete")
@click.pass_context
def session_delete(ctx: click.Context) -> None:
    """Delete the current session and all its data."""
    session = _get_session(ctx)
    session.delete()
    emit_result(
        f"  deleted session {session.name!r}",
        {"status": "deleted", "name": session.name},
    )


# ---------------------------------------------------------------------------
# repl
# ---------------------------------------------------------------------------


@anygen_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL."""
    from .console import AnygenConsole

    AnygenConsole(session_name=ctx.obj.get("session", "default")).cmdloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cli_main(anygen_cli)


if __name__ == "__main__":
    main()
