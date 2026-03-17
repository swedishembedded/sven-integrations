"""CLI entry point for the draw.io harness."""

from __future__ import annotations

from pathlib import Path

import click

from ..shared import cli_main, emit, emit_error, emit_json, emit_result
from .backend import DrawioBackend, DrawioError
from .drawio_xml import (
    add_connector,
    add_shape,
    parse_diagram,
    remove_cell,
    render_xml,
    update_cell_label,
)
from .project import DrawioDocument
from .session import DrawioSession

# ---------------------------------------------------------------------------
# Shared context helpers
# ---------------------------------------------------------------------------


def _get_session(ctx: click.Context) -> DrawioSession:
    name: str = ctx.obj.get("session", "default")
    return DrawioSession.open_or_create(name)


def _load_doc(session: DrawioSession) -> DrawioDocument:
    raw = session.data.get("document")
    if not raw:
        emit_error("No document in session. Run 'new' or 'open' first.")
    return DrawioDocument.from_dict(raw)


def _save_doc(session: DrawioSession, doc: DrawioDocument) -> None:
    session.data["document"] = doc.to_dict()
    session.save()


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("drawio")
@click.option("--session", "-s", default="default", help="Session name.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False, help="Emit JSON output.")
@click.pass_context
def drawio_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """Draw.io diagram control harness for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    ctx.obj["json"] = use_json
    from ..shared.output import set_json_mode
    set_json_mode(use_json)
    if project_path is not None:
        sess = DrawioSession.open_or_create(session)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# project group
# ---------------------------------------------------------------------------


@drawio_cli.group("project")
def project_group() -> None:
    """Project-level management commands."""


@project_group.command("new")
@click.option("--name", default="Untitled", show_default=True, help="Document name.")
@click.option("--page-name", "page_name", default="Page-1", show_default=True, help="First page name.")
@click.option("--output", "-o", "output_path", default=None, help="Write document to this file.")
@click.pass_context
def project_new(ctx: click.Context, name: str, page_name: str, output_path: str | None) -> None:
    """Create a new empty draw.io document."""
    from pathlib import Path
    session = _get_session(ctx)
    doc = DrawioDocument()
    doc.add_page(page_name)
    session.data["name"] = name
    _save_doc(session, doc)
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        from .drawio_xml import render_xml
        p.write_text(render_xml(doc), encoding="utf-8")
    emit_result(
        f"Created document {name!r} with page {page_name!r}",
        {"ok": True, "status": "created", "name": name, "page": page_name},
    )


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


@drawio_cli.command("new")
@click.option("--name", default="Untitled", help="Document name.")
@click.option("--page-name", "page_name", default="Page-1", help="First page name.")
@click.pass_context
def cmd_new(ctx: click.Context, name: str, page_name: str) -> None:
    """Create a new empty draw.io document."""
    session = _get_session(ctx)
    doc = DrawioDocument()
    doc.add_page(page_name)
    session.data["name"] = name
    _save_doc(session, doc)
    emit_result(
        f"Created document {name!r} with page {page_name!r}",
        {"status": "created", "name": name, "page": page_name},
    )


# ---------------------------------------------------------------------------
# open
# ---------------------------------------------------------------------------


@drawio_cli.command("open")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def cmd_open(ctx: click.Context, path: str) -> None:
    """Open an existing .drawio file into the session."""
    content = Path(path).read_text(encoding="utf-8")
    try:
        doc = parse_diagram(content)
        doc.file_path = path
        session = _get_session(ctx)
        _save_doc(session, doc)
        emit_result(
            f"Opened {path!r} ({len(doc.pages)} pages)",
            {"status": "opened", "path": path, "pages": len(doc.pages)},
        )
    except ValueError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


@drawio_cli.command("save")
@click.argument("path", type=click.Path())
@click.pass_context
def cmd_save(ctx: click.Context, path: str) -> None:
    """Save the current document to a .drawio XML file (no Draw.io desktop required)."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    xml = render_xml(doc)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(xml, encoding="utf-8")
    emit_result(
        f"Saved to {path}",
        {"status": "saved", "path": path},
    )


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@drawio_cli.command("export")
@click.option(
    "--format", "fmt", type=click.Choice(["png", "pdf", "svg", "jpg"]), default="png"
)
@click.option("--page", "page_index", default=0, help="Page index to export.")
@click.option("--output", "-o", required=True, help="Output file path (absolute path required).")
@click.pass_context
def cmd_export(ctx: click.Context, fmt: str, page_index: int, output: str) -> None:
    """Export the current document to an image or PDF."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    be = DrawioBackend()
    xml = render_xml(doc)
    try:
        result_path = be.convert_xml(xml, output, fmt=fmt)
        emit_result(
            f"Exported to {result_path}",
            {"status": "exported", "output": str(result_path), "format": fmt},
        )
    except DrawioError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# shape subgroup
# ---------------------------------------------------------------------------


@drawio_cli.group("shape")
@click.pass_context
def shape_group(ctx: click.Context) -> None:
    """Manage shapes in the current document."""


@shape_group.command("add")
@click.option("--type", "shape_type", default="rectangle", help="Shape type.")
@click.option("--label", default="", help="Cell label.")
@click.option("--x", default=100.0, type=float)
@click.option("--y", default=100.0, type=float)
@click.option("--width", "-w", default=120.0, type=float)
@click.option("--height", "-H", default=60.0, type=float)
@click.pass_context
def shape_add(
    ctx: click.Context,
    shape_type: str,
    label: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Add a shape to the first page."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    if not doc.pages:
        emit_error("Document has no pages. Run 'new' or 'open' first.")
    else:
        cid = add_shape(doc, 0, shape_type, label, x, y, width, height)
        _save_doc(session, doc)
        emit_result(f"Shape added: {cid}", {"status": "added", "cell_id": cid, "type": shape_type})


@shape_group.command("remove")
@click.option("--id", "cell_id", required=True, help="Cell ID to remove.")
@click.pass_context
def shape_remove(ctx: click.Context, cell_id: str) -> None:
    """Remove a shape by ID."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    removed = remove_cell(doc, 0, cell_id)
    if removed:
        _save_doc(session, doc)
        emit_result(f"Removed cell {cell_id}", {"status": "removed", "cell_id": cell_id})
    else:
        emit_error(f"Cell not found: {cell_id}")


@shape_group.command("label")
@click.option("--id", "cell_id", required=True)
@click.option("--text", required=True)
@click.pass_context
def shape_label(ctx: click.Context, cell_id: str, text: str) -> None:
    """Update the label of a shape."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    ok = update_cell_label(doc, 0, cell_id, text)
    if ok:
        _save_doc(session, doc)
        emit_result(f"Label updated: {cell_id}", {"status": "updated", "cell_id": cell_id})
    else:
        emit_error(f"Cell not found: {cell_id}")


@shape_group.command("list")
@click.pass_context
def shape_list(ctx: click.Context) -> None:
    """List all vertex cells in the document."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    cells = [
        {"page": p.name, "cell_id": c.cell_id, "value": c.value, "style": c.style}
        for p in doc.pages
        for c in p.cells
        if c.vertex
    ]
    if ctx.obj.get("json"):
        emit_json(cells)
    else:
        for item in cells:
            emit(f"  [{item['page']}] {item['cell_id'][:8]}… {item['value']!r}")


# ---------------------------------------------------------------------------
# connector subgroup
# ---------------------------------------------------------------------------


@drawio_cli.group("connector")
@click.pass_context
def connector_group(ctx: click.Context) -> None:
    """Manage connectors (edges) in the document."""


@connector_group.command("add")
@click.option("--from", "src_id", required=True, help="Source cell ID.")
@click.option("--to", "tgt_id", required=True, help="Target cell ID.")
@click.option("--label", default="", help="Edge label.")
@click.pass_context
def connector_add(ctx: click.Context, src_id: str, tgt_id: str, label: str) -> None:
    """Add a connector between two cells."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    eid = add_connector(doc, 0, src_id, tgt_id, label)
    _save_doc(session, doc)
    emit_result(
        f"Connector added: {eid}",
        {"status": "added", "edge_id": eid, "from": src_id, "to": tgt_id},
    )


@connector_group.command("remove")
@click.option("--id", "edge_id", required=True)
@click.pass_context
def connector_remove(ctx: click.Context, edge_id: str) -> None:
    """Remove a connector by ID."""
    session = _get_session(ctx)
    doc = _load_doc(session)
    removed = remove_cell(doc, 0, edge_id)
    if removed:
        _save_doc(session, doc)
        emit_result(f"Removed edge {edge_id}", {"status": "removed", "edge_id": edge_id})
    else:
        emit_error(f"Edge not found: {edge_id}")


# ---------------------------------------------------------------------------
# page subgroup
# ---------------------------------------------------------------------------


@drawio_cli.group("page")
@click.pass_context
def page_group(ctx: click.Context) -> None:
    """Manage pages in the document."""


@page_group.command("add")
@click.option("--name", required=True, help="Page name.")
@click.pass_context
def page_add(ctx: click.Context, name: str) -> None:
    session = _get_session(ctx)
    doc = _load_doc(session)
    page = doc.add_page(name)
    _save_doc(session, doc)
    emit_result(f"Page added: {name!r}", {"status": "added", "page": name, "id": page.page_id})


@page_group.command("remove")
@click.option("--name", required=True)
@click.pass_context
def page_remove(ctx: click.Context, name: str) -> None:
    session = _get_session(ctx)
    doc = _load_doc(session)
    removed = doc.remove_page(name)
    if removed:
        _save_doc(session, doc)
        emit_result(f"Page removed: {name!r}", {"status": "removed", "page": name})
    else:
        emit_error(f"Page not found: {name!r}")


@page_group.command("list")
@click.pass_context
def page_list(ctx: click.Context) -> None:
    session = _get_session(ctx)
    doc = _load_doc(session)
    pages = [{"name": p.name, "id": p.page_id, "cells": len(p.cells)} for p in doc.pages]
    if ctx.obj.get("json"):
        emit_json(pages)
    else:
        for p in pages:
            emit(f"  {p['name']!r} (id={p['id'][:8]}…, cells={p['cells']})")


# ---------------------------------------------------------------------------
# session subgroup
# ---------------------------------------------------------------------------


@drawio_cli.group("session")
@click.pass_context
def session_group(ctx: click.Context) -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    s = _get_session(ctx)
    info = {"name": s.name, "harness": s.harness, "keys": list(s.data.keys())}
    emit_result(f"Session: {s.name!r}", info)


@session_group.command("list")
def session_list() -> None:
    sessions = DrawioSession.list_sessions()
    if not sessions:
        emit("(no sessions)")
    for name in sessions:
        emit(f"  {name}")


@session_group.command("delete")
@click.pass_context
def session_delete(ctx: click.Context) -> None:
    s = _get_session(ctx)
    s.delete()
    emit_result(f"Session {s.name!r} deleted", {"status": "deleted", "name": s.name})


# ---------------------------------------------------------------------------
# repl
# ---------------------------------------------------------------------------


@drawio_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL."""
    from .console import DrawioConsole

    session_name = ctx.obj.get("session", "default")
    DrawioConsole(session_name=session_name).cmdloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cli_main(drawio_cli)


if __name__ == "__main__":
    main()
