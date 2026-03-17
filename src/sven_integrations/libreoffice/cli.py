"""LibreOffice CLI — command-line interface for headless LibreOffice operations."""

from __future__ import annotations

import click

from ..shared import cli_main, emit_error, emit_result
from .backend import LibreOfficeBackend, LibreOfficeError
from .core import calc as calc_mod
from .core import document as doc_mod
from .core import impress as impress_mod
from .core import styles as styles_mod
from .core import writer as writer_mod
from .project import OfficeDocument
from .session import LibreOfficeSession


def _get_backend() -> LibreOfficeBackend:
    return LibreOfficeBackend()


def _get_session(name: str) -> LibreOfficeSession:
    return LibreOfficeSession.open_or_create(name)  # type: ignore[return-value]


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
def libreoffice_cli(
    ctx: click.Context, session_name: str, project_path: str | None, use_json: bool
) -> None:
    """LibreOffice integration — headless document creation and conversion."""
    from ..shared.output import set_json_mode
    set_json_mode(use_json)
    ctx.ensure_object(dict)
    ctx.obj["session_name"] = session_name
    if project_path is not None:
        sess = _get_session(session_name)
        sess.set_project_file(project_path)
        sess.save()


# ---------------------------------------------------------------------------
# convert

@libreoffice_cli.command("convert")
@click.argument("input_path")
@click.option("--to", "output_format", required=True, help="Target format, e.g. pdf, docx")
@click.option("--output-dir", default=None, help="Directory for the output file")
@click.pass_context
def cmd_convert(
    ctx: click.Context, input_path: str, output_format: str, output_dir: str | None
) -> None:
    """Convert INPUT_PATH to another format using LibreOffice headless."""
    backend = _get_backend()
    try:
        out = backend.convert(input_path, output_format, output_dir)
        emit_result(f"Converted → {out}", {"input": input_path, "output": str(out), "format": output_format})
    except (LibreOfficeError, FileNotFoundError) as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# writer group

@libreoffice_cli.group("writer")
def writer_group() -> None:
    """Writer document commands."""


@writer_group.command("create")
@click.argument("title")
@click.option("--author", default="", help="Document author")
@click.pass_context
def writer_create(ctx: click.Context, title: str, author: str) -> None:
    """Create a new Writer document in the session."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    doc_model = writer_mod.create_document(title, author)
    session.data["writer"] = doc_model.to_dict()
    session.save()
    emit_result(f"Writer document created: {title!r}", {"title": title, "author": author})


@writer_group.command("heading")
@click.argument("level", type=int)
@click.argument("text")
@click.pass_context
def writer_heading(ctx: click.Context, level: int, text: str) -> None:
    """Append a heading at LEVEL with TEXT to the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        doc_model = _load_writer(session)
        writer_mod.set_heading(doc_model, level, text)
        session.data["writer"] = doc_model.to_dict()
        session.save()
        emit_result(f"Heading {level}: {text!r}", {"level": level, "text": text})
    except (RuntimeError, ValueError) as exc:
        emit_error(str(exc))


@writer_group.command("paragraph")
@click.argument("text")
@click.option("--style", default="Default", help="Paragraph style name")
@click.pass_context
def writer_paragraph(ctx: click.Context, text: str, style: str) -> None:
    """Append a paragraph to the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        doc_model = _load_writer(session)
        writer_mod.append_paragraph(doc_model, text, style)
        session.data["writer"] = doc_model.to_dict()
        session.save()
        emit_result("Paragraph appended", {"style": style})
    except RuntimeError as exc:
        emit_error(str(exc))


@writer_group.command("table")
@click.option("--rows", type=int, required=True)
@click.option("--cols", type=int, required=True)
@click.pass_context
def writer_table(ctx: click.Context, rows: int, cols: int) -> None:
    """Insert an empty table into the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        doc_model = _load_writer(session)
        writer_mod.insert_table(doc_model, rows, cols)
        session.data["writer"] = doc_model.to_dict()
        session.save()
        emit_result(f"Table {rows}×{cols} inserted", {"rows": rows, "cols": cols})
    except (RuntimeError, ValueError) as exc:
        emit_error(str(exc))


@writer_group.command("find-replace")
@click.argument("search")
@click.argument("replacement")
@click.option("--case-sensitive", is_flag=True, default=False)
@click.pass_context
def writer_find_replace(
    ctx: click.Context, search: str, replacement: str, case_sensitive: bool
) -> None:
    """Find and replace text in the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        doc_model = _load_writer(session)
        count = writer_mod.find_replace(doc_model, search, replacement, case_sensitive)
        session.data["writer"] = doc_model.to_dict()
        session.save()
        emit_result(f"{count} replacement(s) made", {"count": count})
    except RuntimeError as exc:
        emit_error(str(exc))


def _load_writer(session: LibreOfficeSession) -> writer_mod.WriterDocument:
    raw = session.data.get("writer")
    if raw is None:
        raise RuntimeError("No Writer document in session — use 'writer create' first")
    return writer_mod.WriterDocument(**{
        k: v for k, v in raw.items()
        if k in writer_mod.WriterDocument.__dataclass_fields__
    })


# ---------------------------------------------------------------------------
# calc group

@libreoffice_cli.group("calc")
def calc_group() -> None:
    """Calc spreadsheet commands."""


@calc_group.command("set-cell")
@click.argument("sheet")
@click.argument("ref")
@click.argument("value")
@click.pass_context
def calc_set_cell(ctx: click.Context, sheet: str, ref: str, value: str) -> None:
    """Set SHEET!REF to VALUE in the session spreadsheet."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        wb = _load_calc(session)
        calc_mod.set_cell(wb, sheet, ref, value)
        session.data["calc"] = wb.to_dict()
        session.save()
        emit_result(f"{sheet}!{ref} = {value}", {"sheet": sheet, "ref": ref, "value": value})
    except (RuntimeError, KeyError, ValueError) as exc:
        emit_error(str(exc))


@calc_group.command("get-cell")
@click.argument("sheet")
@click.argument("ref")
@click.pass_context
def calc_get_cell(ctx: click.Context, sheet: str, ref: str) -> None:
    """Read the value at SHEET!REF."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        wb = _load_calc(session)
        val = calc_mod.get_cell(wb, sheet, ref)
        emit_result(f"{sheet}!{ref} = {val}", {"sheet": sheet, "ref": ref, "value": val})
    except (RuntimeError, KeyError) as exc:
        emit_error(str(exc))


@calc_group.command("add-sheet")
@click.argument("name")
@click.pass_context
def calc_add_sheet(ctx: click.Context, name: str) -> None:
    """Add a sheet named NAME to the session spreadsheet."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        wb = _load_calc(session)
        calc_mod.add_sheet(wb, name)
        session.data["calc"] = wb.to_dict()
        session.save()
        emit_result(f"Sheet {name!r} added", {"name": name})
    except (RuntimeError, ValueError) as exc:
        emit_error(str(exc))


@calc_group.command("sort")
@click.argument("sheet")
@click.argument("range_ref")
@click.option("--col-index", type=int, default=0)
@click.option("--desc", "descending", is_flag=True, default=False)
@click.pass_context
def calc_sort(
    ctx: click.Context,
    sheet: str,
    range_ref: str,
    col_index: int,
    descending: bool,
) -> None:
    """Sort RANGE_REF in SHEET by column at COL_INDEX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        wb = _load_calc(session)
        calc_mod.sort_range(wb, sheet, range_ref, col_index, not descending)
        session.data["calc"] = wb.to_dict()
        session.save()
        emit_result(
            f"Sorted {range_ref} by column {col_index}",
            {"sheet": sheet, "range": range_ref, "col_index": col_index},
        )
    except (RuntimeError, KeyError, IndexError, ValueError) as exc:
        emit_error(str(exc))


def _load_calc(session: LibreOfficeSession) -> calc_mod.CalcSpreadsheet:
    raw = session.data.get("calc")
    if raw is None:
        raise RuntimeError("No Calc workbook in session — create one first")
    wb = calc_mod.CalcSpreadsheet(name=raw["name"])
    for sd in raw.get("sheets", []):
        s = calc_mod.CalcSheet(name=sd["name"])
        for ref, cd in sd.get("cells", {}).items():
            s.cells[ref] = calc_mod.CalcCell(
                value=cd.get("value"),
                formula=cd.get("formula", ""),
                number_format=cd.get("number_format", ""),
            )
        s.column_widths = sd.get("column_widths", {})
        wb.sheets.append(s)
    return wb


# ---------------------------------------------------------------------------
# impress group

@libreoffice_cli.group("impress")
def impress_group() -> None:
    """Impress presentation commands."""


@impress_group.command("add-slide")
@click.option("--layout", type=int, default=1, help="Slide layout index")
@click.pass_context
def impress_add_slide(ctx: click.Context, layout: int) -> None:
    """Append a new slide to the session presentation."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        pres = _load_impress(session)
        impress_mod.add_slide(pres, layout)
        session.data["impress"] = pres.to_dict()
        session.save()
        count = impress_mod.get_slide_count(pres)
        emit_result(f"Slide added (total: {count})", {"slide_count": count})
    except (RuntimeError, IndexError) as exc:
        emit_error(str(exc))


@impress_group.command("set-title")
@click.argument("slide_idx", type=int)
@click.argument("title")
@click.pass_context
def impress_set_title(ctx: click.Context, slide_idx: int, title: str) -> None:
    """Set the title of slide at SLIDE_IDX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        pres = _load_impress(session)
        impress_mod.set_slide_title(pres, slide_idx, title)
        session.data["impress"] = pres.to_dict()
        session.save()
        emit_result(f"Slide {slide_idx} title set", {"slide": slide_idx, "title": title})
    except (RuntimeError, IndexError) as exc:
        emit_error(str(exc))


@impress_group.command("add-image")
@click.argument("slide_idx", type=int)
@click.argument("image_path")
@click.option("--x", type=float, default=10.0)
@click.option("--y", type=float, default=10.0)
@click.option("--width", type=float, default=100.0)
@click.option("--height", type=float, default=80.0)
@click.pass_context
def impress_add_image(
    ctx: click.Context,
    slide_idx: int,
    image_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Add an image to slide SLIDE_IDX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        pres = _load_impress(session)
        impress_mod.add_image(pres, slide_idx, image_path, x, y, width, height)
        session.data["impress"] = pres.to_dict()
        session.save()
        emit_result(f"Image added to slide {slide_idx}", {"slide": slide_idx, "path": image_path})
    except (RuntimeError, IndexError) as exc:
        emit_error(str(exc))


@impress_group.command("export")
@click.argument("output_path")
@click.option("--format", "fmt", default="pdf", help="Output format")
@click.argument("input_path")
@click.pass_context
def impress_export(ctx: click.Context, output_path: str, fmt: str, input_path: str) -> None:
    """Export INPUT_PATH presentation to OUTPUT_PATH in the given FORMAT."""
    backend = _get_backend()
    try:
        result = backend.convert(input_path, fmt, None)
        emit_result(f"Exported → {result}", {"input": input_path, "output": str(result), "format": fmt})
    except (LibreOfficeError, FileNotFoundError) as exc:
        emit_error(str(exc))


def _load_impress(session: LibreOfficeSession) -> impress_mod.ImpressPresentation:
    raw = session.data.get("impress")
    if raw is None:
        raise RuntimeError("No presentation in session — create one first")
    pres = impress_mod.ImpressPresentation(title=raw["title"])
    for sd in raw.get("slides", []):
        slide = impress_mod.ImpressSlide(
            index=sd["index"],
            title=sd.get("title", ""),
            content=sd.get("content", ""),
            layout=sd.get("layout", 1),
            background_color=sd.get("background_color", "#ffffff"),
        )
        pres.slides.append(slide)
    return pres


# ---------------------------------------------------------------------------
# document group

@libreoffice_cli.group("document")
def document_group() -> None:
    """Document creation and metadata commands."""


@document_group.command("new")
@click.option("--type", "doc_type",
              type=click.Choice(["writer", "calc", "impress", "draw"]),
              default="writer", help="Document type")
@click.option("--name", "-n", default="Untitled", show_default=True, help="Document name / title")
@click.option("--profile", default="a4", help="Page profile (a4, letter, legal, …)")
@click.option("--output", "-o", "output_path", default=None, help="Write session JSON to this file.")
@click.pass_context
def document_new(ctx: click.Context, doc_type: str, name: str, profile: str, output_path: str | None) -> None:
    """Create a new document in the session."""
    import json as _json_mod
    from pathlib import Path
    session = _get_session(ctx.obj.get("session_name", "default"))
    try:
        office_doc = doc_mod.create_document(doc_type, name, profile)
        session.data["office_doc"] = office_doc.to_dict()
        session.save()
        if output_path is not None:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_json_mod.dumps(session.data, indent=2), encoding="utf-8")
        emit_result(
            f"{doc_type.capitalize()} document {name!r} created",
            {"ok": True, "type": doc_type, "name": name, "profile": profile},
        )
    except ValueError as exc:
        emit_error(str(exc))


@document_group.command("info")
@click.pass_context
def document_info(ctx: click.Context) -> None:
    """Show summary information about the document in the session."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    info = doc_mod.get_document_info(office_doc)
    emit_result(f"Document: {office_doc.title!r}", info)


@document_group.command("profiles")
def document_profiles() -> None:
    """List all available document profiles."""
    profiles = doc_mod.list_profiles()
    emit_result(f"{len(profiles)} profile(s)", profiles)


@document_group.command("property")
@click.argument("key")
@click.argument("value")
@click.pass_context
def document_property(ctx: click.Context, key: str, value: str) -> None:
    """Set a metadata property KEY to VALUE on the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    try:
        result = doc_mod.set_document_property(office_doc, key, value)
        session.data["office_doc"] = office_doc.to_dict()
        session.save()
        emit_result(f"Property {key!r} set", result)
    except ValueError as exc:
        emit_error(str(exc))


def _load_office_doc(session: LibreOfficeSession) -> "OfficeDocument | None":
    raw = session.data.get("office_doc")
    if raw is None:
        return None
    from .project import OfficeDocument
    return OfficeDocument.from_dict(raw)


# ---------------------------------------------------------------------------
# style group

@libreoffice_cli.group("style")
def style_group() -> None:
    """Style management commands."""


@style_group.command("create")
@click.option("--name", "-n", required=True, help="Style name")
@click.option("--family", default="paragraph",
              type=click.Choice(["paragraph", "character", "table", "page"]),
              help="Style family")
@click.option("--parent", default=None, help="Parent style name")
@click.option("--prop", "props", multiple=True,
              help="CSS-like property as key=value, e.g. font-size=14pt")
@click.pass_context
def style_create(
    ctx: click.Context,
    name: str,
    family: str,
    parent: str | None,
    props: tuple[str, ...],
) -> None:
    """Create a new style in the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    properties = _parse_props(props)
    try:
        result = styles_mod.create_style(office_doc, name, family, parent, properties)
        session.data["office_doc"] = office_doc.to_dict()
        session.save()
        emit_result(f"Style {name!r} created", result)
    except ValueError as exc:
        emit_error(str(exc))


@style_group.command("modify")
@click.argument("name")
@click.option("--prop", "props", multiple=True,
              help="CSS-like property as key=value, e.g. color=#ff0000")
@click.pass_context
def style_modify(ctx: click.Context, name: str, props: tuple[str, ...]) -> None:
    """Modify properties of an existing style NAME."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    properties = _parse_props(props)
    try:
        result = styles_mod.modify_style(office_doc, name, properties)
        session.data["office_doc"] = office_doc.to_dict()
        session.save()
        emit_result(f"Style {name!r} modified", result)
    except KeyError as exc:
        emit_error(str(exc))


@style_group.command("remove")
@click.argument("name")
@click.pass_context
def style_remove(ctx: click.Context, name: str) -> None:
    """Remove a custom style NAME from the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    try:
        result = styles_mod.remove_style(office_doc, name)
        session.data["office_doc"] = office_doc.to_dict()
        session.save()
        emit_result(f"Style {name!r} removed", result)
    except (KeyError, ValueError) as exc:
        emit_error(str(exc))


@style_group.command("list")
@click.pass_context
def style_list(ctx: click.Context) -> None:
    """List all custom styles in the session document."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    result = styles_mod.list_styles(office_doc)
    emit_result(f"{result['count']} style(s)", result)


@style_group.command("get")
@click.argument("name")
@click.pass_context
def style_get(ctx: click.Context, name: str) -> None:
    """Get the definition of style NAME."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    try:
        result = styles_mod.get_style(office_doc, name)
        emit_result(f"Style {name!r}", result)
    except KeyError as exc:
        emit_error(str(exc))


@style_group.command("apply")
@click.argument("name")
@click.argument("content_index", type=int)
@click.pass_context
def style_apply(ctx: click.Context, name: str, content_index: int) -> None:
    """Apply style NAME to the content item at CONTENT_INDEX."""
    session = _get_session(ctx.obj.get("session_name", "default"))
    office_doc = _load_office_doc(session)
    if office_doc is None:
        emit_error("No document in session — use 'document new' first")
        return
    try:
        result = styles_mod.apply_style(office_doc, name, content_index)
        session.data["office_doc"] = office_doc.to_dict()
        session.save()
        emit_result(f"Style {name!r} applied to content {content_index}", result)
    except KeyError as exc:
        emit_error(str(exc))


def _parse_props(props: tuple[str, ...]) -> dict[str, str]:
    """Parse ``key=value`` pairs from the ``--prop`` option."""
    result: dict[str, str] = {}
    for raw in props:
        if "=" not in raw:
            continue
        k, _, v = raw.partition("=")
        result[k.strip()] = v.strip()
    return result


# ---------------------------------------------------------------------------
# session group

@libreoffice_cli.group("session")
def session_group() -> None:
    """Session management commands."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Show the current session state."""
    name = ctx.obj.get("session_name", "default")
    session = _get_session(name)
    emit_result(f"Session: {name}", session.status())


@session_group.command("list")
def session_list() -> None:
    """List all saved LibreOffice sessions."""
    names = LibreOfficeSession.list_sessions()
    emit_result(f"{len(names)} session(s)", names)


@session_group.command("delete")
@click.argument("name")
def session_delete(name: str) -> None:
    """Delete the named session."""
    s = LibreOfficeSession(name)
    if s.delete():
        emit_result(f"Session {name!r} deleted", {"deleted": name})
    else:
        emit_error(f"Session {name!r} not found")


# ---------------------------------------------------------------------------
# repl

@libreoffice_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL session."""
    from .console import LibreOfficeConsole
    name = ctx.obj.get("session_name", "default")
    session = _get_session(name)
    backend = _get_backend()
    console = LibreOfficeConsole(session=session, backend=backend)
    console.cmdloop()


# ---------------------------------------------------------------------------
# Entry point

def main() -> None:
    cli_main(libreoffice_cli)


if __name__ == "__main__":
    main()
