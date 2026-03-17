"""CLI entry point for the ComfyUI harness."""

from __future__ import annotations

import json
import sys

import click

from ..shared import emit, emit_error, emit_json, emit_result
from .backend import ComfyBackend, ComfyError
from .core import images as images_mod
from .core import models as models_mod
from .core.queue import (
    cancel_prompt,
    format_queue_status,
)
from .core.workflow import (
    build_img2img_workflow,
    build_txt2img_workflow,
    build_upscale_workflow,
    load_workflow_json,
    save_workflow_json,
)
from .project import ComfyProject
from .session import ComfySession

# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def _get_session(ctx: click.Context) -> ComfySession:
    name: str = ctx.obj.get("session", "default")
    return ComfySession.open_or_create(name)


def _load_project(session: ComfySession) -> ComfyProject:
    raw = session.data.get("project")
    return ComfyProject.from_dict(raw) if raw else ComfyProject()


def _save_project(session: ComfySession, project: ComfyProject) -> None:
    session.data["project"] = project.to_dict()
    session.save()


def _get_backend(project: ComfyProject) -> ComfyBackend:
    return ComfyBackend(server_url=project.server_url)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("comfyui")
@click.option("--session", "-s", default="default", help="Session name.")
@click.option(
    "--project", "-p", "project_path", default=None,
    help="Load/save project state from this JSON file (idempotent; preferred for agents).",
)
@click.option("--json", "use_json", is_flag=True, default=False, help="JSON output.")
@click.pass_context
def comfyui_cli(ctx: click.Context, session: str, project_path: str | None, use_json: bool) -> None:
    """ComfyUI image generation harness for AI agents."""
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
# connect
# ---------------------------------------------------------------------------


@comfyui_cli.command("connect")
@click.option("--url", default="http://127.0.0.1:8188", help="ComfyUI server URL.")
@click.pass_context
def cmd_connect(ctx: click.Context, url: str) -> None:
    """Test connectivity and save the server URL."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = ComfyBackend(server_url=url)
    ok = be.connect(url)
    if ok:
        project.server_url = url
        _save_project(session, project)
        emit_result(f"Connected to {url}", {"status": "connected", "url": url})
    else:
        emit_error(f"Cannot reach ComfyUI at {url}")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@comfyui_cli.command("generate")
@click.option("--positive", required=True, help="Positive prompt.")
@click.option("--negative", default="", help="Negative prompt.")
@click.option("--model", default="v1-5-pruned-emaonly.safetensors")
@click.option("--width", default=512, type=int)
@click.option("--height", default=512, type=int)
@click.option("--steps", default=20, type=int)
@click.option("--cfg", default=7.0, type=float)
@click.option("--seed", default=None, type=int)
@click.option("--output-dir", "output_dir", required=True, help="Absolute output directory (e.g. /tmp/comfy-out).")
@click.pass_context
def cmd_generate(
    ctx: click.Context,
    positive: str,
    negative: str,
    model: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    seed: int | None,
    output_dir: str,
) -> None:
    """Generate an image from text prompts."""
    session = _get_session(ctx)
    project = _load_project(session)
    wf = build_txt2img_workflow(
        positive_prompt=positive,
        negative_prompt=negative,
        model=model,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed,
    )
    project.add_workflow(wf)
    be = _get_backend(project)
    client_id = session.ensure_client_id()
    _save_project(session, project)
    try:
        prompt_id = be.queue_prompt(wf.to_api_format(), client_id)
        emit_result(
            f"Queued prompt: {prompt_id}",
            {"status": "queued", "prompt_id": prompt_id, "workflow": wf.name},
        )
    except ComfyError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# img2img
# ---------------------------------------------------------------------------


@comfyui_cli.command("img2img")
@click.option("--image", required=True, type=click.Path())
@click.option("--positive", required=True)
@click.option("--negative", default="")
@click.option("--model", default="v1-5-pruned-emaonly.safetensors")
@click.option("--denoise", default=0.75, type=float)
@click.option("--output-dir", "output_dir", required=True, help="Absolute output directory (e.g. /tmp/comfy-out).")
@click.pass_context
def cmd_img2img(
    ctx: click.Context,
    image: str,
    positive: str,
    negative: str,
    model: str,
    denoise: float,
    output_dir: str,
) -> None:
    """Image-to-image generation."""
    session = _get_session(ctx)
    project = _load_project(session)
    wf = build_img2img_workflow(
        positive_prompt=positive,
        negative_prompt=negative,
        image_path=image,
        model=model,
        denoise=denoise,
    )
    project.add_workflow(wf)
    be = _get_backend(project)
    client_id = session.ensure_client_id()
    _save_project(session, project)
    try:
        prompt_id = be.queue_prompt(wf.to_api_format(), client_id)
        emit_result(
            f"Queued img2img: {prompt_id}",
            {"status": "queued", "prompt_id": prompt_id},
        )
    except ComfyError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# upscale
# ---------------------------------------------------------------------------


@comfyui_cli.command("upscale")
@click.option("--image", required=True, type=click.Path())
@click.option("--model", default="RealESRGAN_x4plus.pth")
@click.option("--scale", default=4.0, type=float)
@click.option("--output-dir", "output_dir", required=True, help="Absolute output directory (e.g. /tmp/comfy-out).")
@click.pass_context
def cmd_upscale(
    ctx: click.Context,
    image: str,
    model: str,
    scale: float,
    output_dir: str,
) -> None:
    """Upscale an image using an upscale model."""
    session = _get_session(ctx)
    project = _load_project(session)
    wf = build_upscale_workflow(image_path=image, model=model, scale_factor=scale)
    project.add_workflow(wf)
    be = _get_backend(project)
    client_id = session.ensure_client_id()
    _save_project(session, project)
    try:
        prompt_id = be.queue_prompt(wf.to_api_format(), client_id)
        emit_result(
            f"Queued upscale: {prompt_id}",
            {"status": "queued", "prompt_id": prompt_id},
        )
    except ComfyError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# workflow subgroup
# ---------------------------------------------------------------------------


@comfyui_cli.group("workflow")
@click.pass_context
def workflow_group(ctx: click.Context) -> None:
    """Manage ComfyUI workflows."""


@workflow_group.command("load")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True))
@click.pass_context
def workflow_load(ctx: click.Context, file_path: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    try:
        wf = load_workflow_json(file_path)
    except Exception as exc:
        emit_error(str(exc))
    project.add_workflow(wf)
    _save_project(session, project)
    emit_result(
        f"Loaded {wf.name!r} ({len(wf.nodes)} nodes)",
        {"status": "loaded", "name": wf.name, "nodes": len(wf.nodes)},
    )


@workflow_group.command("save")
@click.option("--name", required=True)
@click.option("--output", "-o", required=True, type=click.Path())
@click.pass_context
def workflow_save(ctx: click.Context, name: str, output: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    wf = next((w for w in project.workflows if w.name == name), None)
    if wf is None:
        emit_error(f"Workflow not found: {name!r}")
    save_workflow_json(wf, output)
    emit_result(f"Saved to {output}", {"status": "saved", "path": output})


@workflow_group.command("list")
@click.pass_context
def workflow_list(ctx: click.Context) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    items = [
        {
            "name": wf.name,
            "id": wf.workflow_id,
            "nodes": len(wf.nodes),
            "active": wf.name == project.active_workflow,
        }
        for wf in project.workflows
    ]
    if ctx.obj.get("json"):
        emit_json(items)
    else:
        for item in items:
            marker = "▶" if item["active"] else " "
            emit(f"  {marker} {item['name']!r} ({item['nodes']} nodes)")


@workflow_group.command("show")
@click.option("--name", required=True)
@click.pass_context
def workflow_show(ctx: click.Context, name: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    wf = next((w for w in project.workflows if w.name == name), None)
    if wf is None:
        emit_error(f"Workflow not found: {name!r}")
    if ctx.obj.get("json"):
        emit_json(wf.to_dict())
    else:
        emit(json.dumps(wf.to_dict(), indent=2))


@workflow_group.command("validate")
@click.option("--file", "file_path", default=None, type=click.Path())
@click.pass_context
def workflow_validate(ctx: click.Context, file_path: str | None) -> None:
    if file_path:
        try:
            wf = load_workflow_json(file_path)
        except Exception as exc:
            emit_error(str(exc))
    else:
        session = _get_session(ctx)
        project = _load_project(session)
        wf = project.get_active_workflow()
        if wf is None:
            emit_error("No active workflow and no --file provided.")
    errors = wf.validate()
    if errors:
        for e in errors:
            emit(f"  ✗ {e}")
        sys.exit(1)
    emit_result("Workflow is valid", {"status": "valid", "errors": []})


# ---------------------------------------------------------------------------
# queue subgroup
# ---------------------------------------------------------------------------


@comfyui_cli.group("queue")
@click.pass_context
def queue_group(ctx: click.Context) -> None:
    """ComfyUI queue management."""


@queue_group.command("status")
@click.pass_context
def queue_status(ctx: click.Context) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        status = be.get_queue_status()
        if ctx.obj.get("json"):
            emit_json(status)
        else:
            emit(format_queue_status(status))
    except ComfyError as exc:
        emit_error(str(exc))


@queue_group.command("cancel")
@click.option("--id", "prompt_id", required=True)
@click.pass_context
def queue_cancel(ctx: click.Context, prompt_id: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    ok = cancel_prompt(be, prompt_id)
    if ok:
        emit_result(f"Cancel sent: {prompt_id}", {"status": "cancelled"})
    else:
        emit_error(f"Could not cancel {prompt_id}")


@queue_group.command("history")
@click.option("--id", "prompt_id", required=True)
@click.pass_context
def queue_history(ctx: click.Context, prompt_id: str) -> None:
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        hist = be.get_history(prompt_id)
        if ctx.obj.get("json"):
            emit_json(hist)
        else:
            emit(json.dumps(hist, indent=2))
    except ComfyError as exc:
        emit_error(str(exc))


# ---------------------------------------------------------------------------
# models subgroup
# ---------------------------------------------------------------------------


@comfyui_cli.group("models")
@click.pass_context
def models_group(ctx: click.Context) -> None:
    """List models available on the ComfyUI server."""


@models_group.command("checkpoints")
@click.pass_context
def models_checkpoints(ctx: click.Context) -> None:
    """List all checkpoint models."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        items = models_mod.list_checkpoints(be)
    except ComfyError as exc:
        emit_error(str(exc))
    emit_result(f"{len(items)} checkpoint(s)", items)


@models_group.command("loras")
@click.pass_context
def models_loras(ctx: click.Context) -> None:
    """List all LoRA models."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        items = models_mod.list_loras(be)
    except ComfyError as exc:
        emit_error(str(exc))
    emit_result(f"{len(items)} LoRA(s)", items)


@models_group.command("vaes")
@click.pass_context
def models_vaes(ctx: click.Context) -> None:
    """List all VAE models."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        items = models_mod.list_vaes(be)
    except ComfyError as exc:
        emit_error(str(exc))
    emit_result(f"{len(items)} VAE(s)", items)


@models_group.command("controlnets")
@click.pass_context
def models_controlnets(ctx: click.Context) -> None:
    """List all ControlNet models."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        items = models_mod.list_controlnets(be)
    except ComfyError as exc:
        emit_error(str(exc))
    emit_result(f"{len(items)} ControlNet(s)", items)


@models_group.command("node-info")
@click.argument("class_name")
@click.pass_context
def models_node_info(ctx: click.Context, class_name: str) -> None:
    """Show /object_info for node CLASS_NAME."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        info = models_mod.get_node_info(be, class_name)
    except ComfyError as exc:
        emit_error(str(exc))
    emit_json(info)


@models_group.command("nodes")
@click.pass_context
def models_nodes(ctx: click.Context) -> None:
    """List all registered node class names."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        classes = models_mod.list_all_node_classes(be)
    except ComfyError as exc:
        emit_error(str(exc))
    emit_result(f"{len(classes)} node class(es)", classes)


# ---------------------------------------------------------------------------
# images subgroup
# ---------------------------------------------------------------------------


@comfyui_cli.group("images")
@click.pass_context
def images_group(ctx: click.Context) -> None:
    """Manage output images from completed prompts."""


@images_group.command("list")
@click.argument("prompt_id")
@click.pass_context
def images_list(ctx: click.Context, prompt_id: str) -> None:
    """List output images from prompt PROMPT_ID."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        imgs = images_mod.list_output_images(be, prompt_id)
    except ComfyError as exc:
        emit_error(str(exc))
    items = [i.to_dict() for i in imgs]
    emit_result(f"{len(items)} image(s)", items)


@images_group.command("download")
@click.argument("prompt_id")
@click.option("--output-dir", "output_dir", required=True, help="Absolute directory to save images (e.g. /tmp/comfy-out).")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing files.")
@click.pass_context
def images_download(
    ctx: click.Context,
    prompt_id: str,
    output_dir: str,
    overwrite: bool,
) -> None:
    """Download all output images from prompt PROMPT_ID."""
    session = _get_session(ctx)
    project = _load_project(session)
    be = _get_backend(project)
    try:
        result = images_mod.download_prompt_images(be, prompt_id, output_dir, overwrite)
    except ComfyError as exc:
        emit_error(str(exc))
    downloaded = result["downloaded"]
    skipped = result["skipped"]
    errors = result["errors"]
    msg = f"{len(downloaded)} downloaded, {len(skipped)} skipped, {len(errors)} error(s)"
    emit_result(msg, result)


# ---------------------------------------------------------------------------
# session subgroup
# ---------------------------------------------------------------------------


@comfyui_cli.group("session")
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
    for name in ComfySession.list_sessions():
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


@comfyui_cli.command("repl")
@click.pass_context
def cmd_repl(ctx: click.Context) -> None:
    """Start an interactive REPL."""
    from .console import ComfyConsole

    ComfyConsole(session_name=ctx.obj.get("session", "default")).cmdloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    comfyui_cli()


if __name__ == "__main__":
    main()
