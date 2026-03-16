"""CLI entry point for the AnyGen harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from ..shared import emit, emit_error, emit_json, emit_result
from .backend import AnygenBackend
from .core.export import (
    export_results_csv,
    export_results_json,
    export_results_markdown,
)
from .core.task import create_task, format_result, validate_task
from .project import AnygenProject
from .session import AnygenSession


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _get_session(ctx: click.Context) -> AnygenSession:
    name: str = ctx.obj.get("session", "default")
    return AnygenSession.open_or_create(name)


def _load_project(session: AnygenSession) -> AnygenProject:
    raw = session.data.get("project")
    return AnygenProject.from_dict(raw) if raw else AnygenProject()


def _save_project(session: AnygenSession, project: AnygenProject) -> None:
    session.data["project"] = project.to_dict()
    session.save()


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("anygen")
@click.option("--session", "-s", default="default", help="Session name.")
@click.option("--json", "use_json", is_flag=True, default=False, help="JSON output.")
@click.pass_context
def anygen_cli(ctx: click.Context, session: str, use_json: bool) -> None:
    """AnyGen LLM generation harness for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    ctx.obj["json"] = use_json
    from ..shared.output import set_json_mode
    set_json_mode(use_json)


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@anygen_cli.command("generate")
@click.argument("prompt")
@click.option("--model", default="gpt-4o-mini")
@click.option(
    "--provider",
    default="openai",
    type=click.Choice(["openai", "anthropic", "ollama", "local"]),
)
@click.option("--temperature", default=0.7, type=float)
@click.option("--max-tokens", default=1024, type=int)
@click.pass_context
def cmd_generate(
    ctx: click.Context,
    prompt: str,
    model: str,
    provider: str,
    temperature: float,
    max_tokens: int,
) -> None:
    """Run a single generation task."""
    session = _get_session(ctx)
    task = create_task(
        prompt=prompt,
        model=model,
        provider=provider,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    errors = validate_task(task)
    if errors:
        emit_error("; ".join(errors))
    project = _load_project(session)
    project.add_task(task)
    be = AnygenBackend()
    result = be.generate(task, api_key=session.get_api_key(provider))
    project.results.append(result)
    _save_project(session, project)
    if ctx.obj.get("json"):
        emit_json(result.to_dict())
    else:
        emit(format_result(result))


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------


@anygen_cli.command("batch")
@click.option("--file", "prompts_file", required=True, type=click.Path(exists=True))
@click.option("--model", default="gpt-4o-mini")
@click.option(
    "--provider",
    default="openai",
    type=click.Choice(["openai", "anthropic", "ollama", "local"]),
)
@click.pass_context
def cmd_batch(
    ctx: click.Context,
    prompts_file: str,
    model: str,
    provider: str,
) -> None:
    """Run batch generation from a prompts file (one prompt per line)."""
    session = _get_session(ctx)
    project = _load_project(session)
    prompts = [
        line.strip()
        for line in Path(prompts_file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    be = AnygenBackend()
    api_key = session.get_api_key(provider)
    batch_results: list[dict[str, Any]] = []
    for prompt in prompts:
        task = create_task(prompt=prompt, model=model, provider=provider)
        project.add_task(task)
        result = be.generate(task, api_key=api_key)
        project.results.append(result)
        batch_results.append(result.to_dict())
        emit(f"  {task.task_id[:8]}… [{result.status}]")
    _save_project(session, project)
    emit_result(
        f"Batch complete: {len(prompts)} tasks",
        {"status": "done", "count": len(prompts), "results": batch_results},
    )


# ---------------------------------------------------------------------------
# results subgroup
# ---------------------------------------------------------------------------


@anygen_cli.group("results")
@click.pass_context
def results_group(ctx: click.Context) -> None:
    """Manage generation results."""


@results_group.command("list")
@click.pass_context
def results_list(ctx: click.Context) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    items = [
        {
            "task_id": r.task_id,
            "status": r.status,
            "model": r.metadata.get("model", ""),
            "provider": r.metadata.get("provider", ""),
        }
        for r in project.results
    ]
    if ctx.obj.get("json"):
        emit_json(items)
    else:
        for item in items:
            sym = "✓" if item["status"] == "completed" else "✗"
            emit(f"  {sym} {item['task_id'][:8]}… [{item['status']}]")


@results_group.command("show")
@click.option("--id", "task_id", required=True)
@click.pass_context
def results_show(ctx: click.Context, task_id: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    result = project.get_result(task_id) or next(
        (r for r in project.results if r.task_id.startswith(task_id)), None
    )
    if result is None:
        emit_error(f"Result not found: {task_id!r}")
    if ctx.obj.get("json"):
        emit_json(result.to_dict())
    else:
        emit(format_result(result, verbose=True))


@results_group.command("export")
@click.option(
    "--format", "fmt", default="json", type=click.Choice(["json", "csv", "markdown"])
)
@click.option("--output", "-o", default=None)
@click.pass_context
def results_export(ctx: click.Context, fmt: str, output: str | None) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    ext_map = {"json": "json", "csv": "csv", "markdown": "md"}
    out_path = output or f"results.{ext_map[fmt]}"
    if fmt == "json":
        export_results_json(project.results, out_path)
    elif fmt == "csv":
        export_results_csv(project.results, out_path)
    elif fmt == "markdown":
        export_results_markdown(project.results, out_path)
    emit_result(f"Exported to {out_path}", {"status": "exported", "path": out_path})


# ---------------------------------------------------------------------------
# config subgroup
# ---------------------------------------------------------------------------


@anygen_cli.group("config")
@click.pass_context
def config_group(ctx: click.Context) -> None:
    """Provider configuration."""


@config_group.command("set-key")
@click.option("--provider", required=True)
@click.option("--key", required=True)
@click.pass_context
def config_set_key(ctx: click.Context, provider: str, key: str) -> None:
    session = _get_session(ctx)
    session.set_api_key(provider, key)
    session.save()
    emit_result(f"API key set for {provider!r}", {"status": "set", "provider": provider})


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    session = _get_session(ctx)
    auth = session.data.get("auth", {})
    masked = {p: (k[:4] + "…" + k[-4:] if len(k) > 8 else "****") for p, k in auth.items()}
    if ctx.obj.get("json"):
        emit_json(masked)
    else:
        if not masked:
            emit("  (no keys configured)")
        for provider, key in masked.items():
            emit(f"  {provider}: {key}")


@config_group.command("clear-keys")
@click.pass_context
def config_clear_keys(ctx: click.Context) -> None:
    session = _get_session(ctx)
    session.clear_keys()
    session.save()
    emit_result("API keys cleared", {"status": "cleared"})


# ---------------------------------------------------------------------------
# session subgroup
# ---------------------------------------------------------------------------


@anygen_cli.group("session")
@click.pass_context
def session_group(ctx: click.Context) -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    s = _get_session(ctx)
    emit_result(f"Session: {s.name!r}", {"name": s.name, "harness": s.harness})


@session_group.command("list")
def session_list() -> None:
    for name in AnygenSession.list_sessions():
        emit(f"  {name}")


@session_group.command("delete")
@click.pass_context
def session_delete(ctx: click.Context) -> None:
    s = _get_session(ctx)
    s.delete()
    emit_result(f"Session {s.name!r} deleted", {"status": "deleted"})


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
    anygen_cli()


if __name__ == "__main__":
    main()
