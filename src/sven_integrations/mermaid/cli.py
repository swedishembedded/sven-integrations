"""CLI entry point for the Mermaid harness."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..shared import cli_main, emit, emit_error, emit_json, emit_result
from .backend import MermaidBackend, MermaidError
from .core.diagrams import (
    build_flowchart,
    build_gantt,
    build_sequence,
)
from .project import MermaidDiagram, MermaidProject
from .session import MermaidSession

# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _get_session(ctx: click.Context) -> MermaidSession:
    name: str = ctx.obj.get("session", "default")
    return MermaidSession.open_or_create(name)


def _load_project(session: MermaidSession) -> MermaidProject:
    raw = session.data.get("project")
    if raw:
        return MermaidProject.from_dict(raw)
    return MermaidProject()


def _save_project(session: MermaidSession, project: MermaidProject) -> None:
    session.data["project"] = project.to_dict()
    session.save()


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("mermaid")
@click.option("--session", "-s", default="default", help="Session name.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False, help="JSON output.")
@click.pass_context
def mermaid_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """Mermaid diagram control harness for AI agents."""
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
# project group
# ---------------------------------------------------------------------------


@mermaid_cli.group("project")
def project_group() -> None:
    """Project-level management commands."""


@project_group.command("new")
@click.option("--title", default="Untitled", show_default=True, help="Project title.")
@click.option("--theme", default="default", show_default=True, help="Default diagram theme.")
@click.option("--output", "-o", "output_path", default=None, help="Write project JSON to this file.")
@click.pass_context
def project_new(ctx: click.Context, title: str, theme: str, output_path: str | None) -> None:
    """Create a new empty Mermaid project in the session."""
    sess = _get_session(ctx)
    proj = MermaidProject(name=title, default_theme=theme)
    _save_project(sess, proj)
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(proj.to_dict(), indent=2), encoding="utf-8")
    emit_result(
        f"Mermaid project {title!r} created.",
        {"ok": True, "title": title, "theme": theme},
    )


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


@mermaid_cli.command("render")
@click.argument("definition", default="", required=False)
@click.option("--file", "input_file", default=None, type=click.Path(), help="Input .mmd file.")
@click.option("--type", "diagram_type", default="flowchart")
@click.option("--theme", default="default")
@click.option("--output", "-o", required=True, help="Absolute output path (e.g. /tmp/diagram.png).")
@click.option("--format", "fmt", default="png", type=click.Choice(["png", "svg", "pdf"]))
@click.pass_context
def cmd_render(
    ctx: click.Context,
    definition: str,
    input_file: str | None,
    diagram_type: str,
    theme: str,
    output: str,
    fmt: str,
) -> None:
    """Render a Mermaid definition to an image."""
    if input_file:
        definition = Path(input_file).read_text(encoding="utf-8")
    if not definition.strip():
        emit_error("Provide a definition or --file.")
    diag = MermaidDiagram(diagram_type=diagram_type, definition=definition, theme=theme)
    src = diag.render_src()
    out_path = output
    be = MermaidBackend()
    try:
        if be.is_mmdc_available():
            result = be.render_with_mmdc(src, out_path, fmt=fmt, theme=theme)
            emit_result(
                f"Rendered to {result}",
                {"status": "rendered", "output": str(result), "renderer": "mmdc"},
            )
        else:
            data = be.render_with_api(src, fmt=fmt, theme=theme)
            with open(out_path, "wb") as f:
                f.write(data)
            emit_result(
                f"Rendered to {out_path} via API",
                {"status": "rendered", "output": out_path, "renderer": "api"},
            )
    except MermaidError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


@mermaid_cli.command("new")
@click.option("--type", "diagram_type", default="flowchart")
@click.option("--title", default=None)
@click.option("--theme", default="default")
@click.pass_context
def cmd_new(ctx: click.Context, diagram_type: str, title: str | None, theme: str) -> None:
    """Create a new diagram in the session project."""
    session = _get_session(ctx)
    project = _load_project(session)
    diag = MermaidDiagram(diagram_type=diagram_type, title=title, theme=theme)
    project.add_diagram(diag)
    _save_project(session, project)
    emit_result(
        f"Diagram {title!r} [{diagram_type}] added",
        {"status": "created", "title": title, "type": diagram_type},
    )


# ---------------------------------------------------------------------------
# diagram subgroup
# ---------------------------------------------------------------------------


@mermaid_cli.group("diagram")
@click.pass_context
def diagram_group(ctx: click.Context) -> None:
    """Manage diagrams in the project."""


@diagram_group.command("add")
@click.option("--type", "diagram_type", default="flowchart")
@click.option("--title", default=None)
@click.pass_context
def diagram_add(ctx: click.Context, diagram_type: str, title: str | None) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    diag = MermaidDiagram(diagram_type=diagram_type, title=title)
    project.add_diagram(diag)
    _save_project(session, project)
    emit_result(f"Added {title!r}", {"status": "added", "title": title})


@diagram_group.command("remove")
@click.option("--title", required=True)
@click.pass_context
def diagram_remove(ctx: click.Context, title: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    removed = project.remove_diagram(title)
    if removed:
        _save_project(session, project)
        emit_result(f"Removed {title!r}", {"status": "removed", "title": title})
    else:
        emit_error(f"Diagram not found: {title!r}")


@diagram_group.command("list")
@click.pass_context
def diagram_list(ctx: click.Context) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    items = [
        {"title": d.title, "type": d.diagram_type, "theme": d.theme}
        for d in project.diagrams
    ]
    if ctx.obj.get("json"):
        emit_json(items)
    else:
        for item in items:
            emit(f"  {item['title']!r} [{item['type']}] theme={item['theme']}")


@diagram_group.command("show")
@click.option("--title", required=True)
@click.pass_context
def diagram_show(ctx: click.Context, title: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    diag = project.find_diagram(title)
    if diag is None:
        emit_error(f"Diagram not found: {title!r}")
    src = diag.render_src()
    if ctx.obj.get("json"):
        emit_json({"title": title, "source": src, "type": diag.diagram_type})
    else:
        emit(src)


# ---------------------------------------------------------------------------
# flowchart
# ---------------------------------------------------------------------------


@mermaid_cli.command("flowchart")
@click.option("--nodes", default="[]", help="JSON array of node dicts.")
@click.option("--edges", default="[]", help="JSON array of edge dicts.")
@click.option("--direction", default="TB", type=click.Choice(["TB", "LR", "BT", "RL"]))
@click.pass_context
def cmd_flowchart(ctx: click.Context, nodes: str, edges: str, direction: str) -> None:
    """Generate a flowchart definition and store it."""
    try:
        node_list = json.loads(nodes)
        edge_list = json.loads(edges)
    except json.JSONDecodeError as exc:
        emit_error(f"Invalid JSON: {exc}")
    src = build_flowchart(node_list, edge_list, direction)
    session = _get_session(ctx)
    project = _load_project(session)
    diag = MermaidDiagram(diagram_type="flowchart", definition=src)
    project.add_diagram(diag)
    _save_project(session, project)
    emit_result(src, {"status": "created", "definition": src})


# ---------------------------------------------------------------------------
# sequence
# ---------------------------------------------------------------------------


@mermaid_cli.command("sequence")
@click.option("--participants", default="[]", help="JSON array of participant names.")
@click.option("--messages", default="[]", help="JSON array of message dicts.")
@click.pass_context
def cmd_sequence(ctx: click.Context, participants: str, messages: str) -> None:
    """Generate a sequence diagram and store it."""
    try:
        parts = json.loads(participants)
        msgs = json.loads(messages)
    except json.JSONDecodeError as exc:
        emit_error(f"Invalid JSON: {exc}")
    src = build_sequence(parts, msgs)
    session = _get_session(ctx)
    project = _load_project(session)
    diag = MermaidDiagram(diagram_type="sequenceDiagram", definition=src)
    project.add_diagram(diag)
    _save_project(session, project)
    emit_result(src, {"status": "created", "definition": src})


# ---------------------------------------------------------------------------
# gantt
# ---------------------------------------------------------------------------


@mermaid_cli.command("gantt")
@click.option("--title", required=True)
@click.option("--sections", default="[]", help="JSON array of section dicts.")
@click.pass_context
def cmd_gantt(ctx: click.Context, title: str, sections: str) -> None:
    """Generate a Gantt chart and store it."""
    try:
        section_list = json.loads(sections)
    except json.JSONDecodeError as exc:
        emit_error(f"Invalid JSON: {exc}")
    src = build_gantt(title, section_list)
    session = _get_session(ctx)
    project = _load_project(session)
    diag = MermaidDiagram(diagram_type="gantt", title=title, definition=src)
    project.add_diagram(diag)
    _save_project(session, project)
    emit_result(src, {"status": "created", "definition": src})


# ---------------------------------------------------------------------------
# session subgroup
# ---------------------------------------------------------------------------


@mermaid_cli.group("session")
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
    sessions = MermaidSession.list_sessions()
    for name in sessions:
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


@mermaid_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL."""
    from .console import MermaidConsole

    MermaidConsole(session_name=ctx.obj.get("session", "default")).cmdloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cli_main(mermaid_cli)


if __name__ == "__main__":
    main()
