"""Interactive REPL console for the ComfyUI harness."""

from __future__ import annotations

import json
from typing import Any

from ..shared import Console, Style
from .core.workflow import (
    build_img2img_workflow,
    build_txt2img_workflow,
    build_upscale_workflow,
    load_workflow_json,
)
from .project import ComfyProject, ComfyWorkflow
from .session import ComfySession


class ComfyConsole(Console):
    """REPL for ComfyUI workflow management and image generation."""

    harness_name = "comfyui"
    intro_extra = "Commands: connect, generate, img2img, upscale, workflow, queue, status, help"

    def __init__(self, session_name: str = "default", **kwargs: Any) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._session = ComfySession.open_or_create(session_name)
        raw = self._session.data.get("project")
        self._project: ComfyProject = (
            ComfyProject.from_dict(raw) if raw else ComfyProject()
        )

    def _save(self) -> None:
        self._session.data["project"] = self._project.to_dict()
        self._session.save()

    def _backend(self):
        from .backend import ComfyBackend
        return ComfyBackend(server_url=self._project.server_url)

    # ------------------------------------------------------------------
    # Commands

    def do_status(self, _arg: str) -> None:
        """Show session and server status."""
        self.section("ComfyUI Status")
        self.bullet(f"session:    {self._session.name}")
        self.bullet(f"server_url: {self._project.server_url}")
        self.bullet(f"workflows:  {len(self._project.workflows)}")
        self.bullet(f"active:     {self._project.active_workflow or '(none)'}")
        be = self._backend()
        try:
            stats = be.get_system_stats()
            devices = stats.get("devices", [{}])
            if devices:
                vram = devices[0].get("vram_total", "?")
                self.bullet(f"VRAM total: {vram}")
            self.success("ComfyUI reachable")
        except Exception:
            self.failure("ComfyUI not reachable")

    def do_connect(self, arg: str) -> None:
        """Connect to ComfyUI. Usage: connect [URL]"""
        parts = self.parse_args(arg)
        url = parts[0] if parts else self._project.server_url
        be = self._backend()
        ok = be.connect(url)
        if ok:
            self._project.server_url = url
            self._save()
            self.success(f"Connected to {url}")
        else:
            self.failure(f"Cannot reach ComfyUI at {url}")

    def do_generate(self, arg: str) -> None:
        """Generate an image. Usage: generate --positive PROMPT [--model M --steps N ...]"""
        parts = self.parse_args(arg)
        positive = ""
        negative = ""
        model = "v1-5-pruned-emaonly.safetensors"
        width = 512
        height = 512
        steps = 20
        cfg = 7.0
        seed = None
        output_dir = "."
        it = iter(parts)
        for tok in it:
            if tok == "--positive":
                positive = next(it, "")
            elif tok == "--negative":
                negative = next(it, "")
            elif tok == "--model":
                model = next(it, model)
            elif tok == "--width":
                width = int(next(it, str(width)))
            elif tok == "--height":
                height = int(next(it, str(height)))
            elif tok == "--steps":
                steps = int(next(it, str(steps)))
            elif tok == "--cfg":
                cfg = float(next(it, str(cfg)))
            elif tok == "--seed":
                seed = int(next(it, "-1"))
            elif tok == "--output-dir":
                output_dir = next(it, ".")
        if not positive:
            print(Style.err("  Provide --positive PROMPT"))
            return
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
        self._run_workflow(wf)

    def do_img2img(self, arg: str) -> None:
        """Image-to-image generation. Usage: img2img --image PATH --positive PROMPT [...]"""
        parts = self.parse_args(arg)
        positive = ""
        negative = ""
        image = ""
        model = "v1-5-pruned-emaonly.safetensors"
        denoise = 0.75
        steps = 20
        it = iter(parts)
        for tok in it:
            if tok == "--positive":
                positive = next(it, "")
            elif tok == "--negative":
                negative = next(it, "")
            elif tok == "--image":
                image = next(it, "")
            elif tok == "--model":
                model = next(it, model)
            elif tok == "--denoise":
                denoise = float(next(it, str(denoise)))
            elif tok == "--steps":
                steps = int(next(it, str(steps)))
        if not image or not positive:
            print(Style.err("  Provide --image PATH --positive PROMPT"))
            return
        wf = build_img2img_workflow(
            positive_prompt=positive,
            negative_prompt=negative,
            image_path=image,
            model=model,
            denoise=denoise,
            steps=steps,
        )
        self._run_workflow(wf)

    def do_upscale(self, arg: str) -> None:
        """Upscale an image. Usage: upscale --image PATH [--model M --scale N]"""
        parts = self.parse_args(arg)
        image = ""
        model = "RealESRGAN_x4plus.pth"
        scale = 4.0
        it = iter(parts)
        for tok in it:
            if tok == "--image":
                image = next(it, "")
            elif tok == "--model":
                model = next(it, model)
            elif tok == "--scale":
                scale = float(next(it, str(scale)))
        if not image:
            print(Style.err("  Provide --image PATH"))
            return
        wf = build_upscale_workflow(image_path=image, model=model, scale_factor=scale)
        self._run_workflow(wf)

    def _run_workflow(self, wf: ComfyWorkflow) -> None:
        be = self._backend()
        client_id = self._session.ensure_client_id()
        self._project.add_workflow(wf)
        self._save()
        try:
            prompt_id = be.queue_prompt(wf.to_api_format(), client_id)
            self.success(f"Queued prompt: {prompt_id}")
        except Exception as exc:
            self.failure(str(exc))

    def do_workflow(self, arg: str) -> None:
        """Workflow management. Usage: workflow load|save|list|show|validate [options]"""
        parts = self.parse_args(arg)
        if not parts:
            print(Style.err("  Usage: workflow load|save|list|show|validate [...]"))
            return
        sub = parts[0]
        if sub == "load":
            file_path = parts[2] if len(parts) > 2 and parts[1] == "--file" else (parts[1] if len(parts) > 1 else "")
            if not file_path:
                print(Style.err("  Provide --file PATH"))
                return
            try:
                wf = load_workflow_json(file_path)
                self._project.add_workflow(wf)
                self._save()
                self.success(f"Loaded workflow {wf.name!r} ({len(wf.nodes)} nodes)")
            except Exception as exc:
                self.failure(str(exc))
        elif sub == "list":
            self.section("Workflows")
            for wf in self._project.workflows:
                marker = "▶" if wf.name == self._project.active_workflow else " "
                self.bullet(f"{marker} {wf.name!r} ({len(wf.nodes)} nodes)")
        elif sub == "show":
            name = parts[2] if len(parts) > 2 and parts[1] == "--name" else (parts[1] if len(parts) > 1 else "")
            wf = next((w for w in self._project.workflows if w.name == name), None)
            if wf is None:
                self.failure(f"Workflow not found: {name!r}")
                return
            print(json.dumps(wf.to_dict(), indent=2))
        elif sub == "validate":
            file_path = parts[2] if len(parts) > 2 and parts[1] == "--file" else (parts[1] if len(parts) > 1 else "")
            if file_path:
                try:
                    wf = load_workflow_json(file_path)
                except Exception as exc:
                    self.failure(str(exc))
                    return
            else:
                wf = self._project.get_active_workflow()
                if wf is None:
                    self.failure("No active workflow")
                    return
            errors = wf.validate()
            if errors:
                for e in errors:
                    self.failure(e)
            else:
                self.success("Workflow is valid")
        else:
            print(Style.err(f"  Unknown: {sub!r}"))

    def do_queue(self, arg: str) -> None:
        """Queue management. Usage: queue status|cancel --id ID|history --id ID"""
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "status"
        be = self._backend()
        if sub == "status":
            try:
                status = be.get_queue_status()
                from .core.queue import format_queue_status
                print(format_queue_status(status))
            except Exception as exc:
                self.failure(str(exc))
        elif sub == "cancel":
            prompt_id = parts[2] if len(parts) > 2 and parts[1] == "--id" else (parts[1] if len(parts) > 1 else "")
            from .core.queue import cancel_prompt
            ok = cancel_prompt(be, prompt_id)
            if ok:
                self.success(f"Cancel sent for {prompt_id}")
            else:
                self.failure(f"Could not cancel {prompt_id}")
        elif sub == "history":
            prompt_id = parts[2] if len(parts) > 2 and parts[1] == "--id" else (parts[1] if len(parts) > 1 else "")
            try:
                hist = be.get_history(prompt_id)
                print(json.dumps(hist, indent=2))
            except Exception as exc:
                self.failure(str(exc))
        else:
            print(Style.err(f"  Unknown: {sub!r}"))

    def do_session(self, arg: str) -> None:
        """Session management. Usage: session show|list|delete"""
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "show"
        if sub == "show":
            self.section("Session")
            self.bullet(f"name: {self._session.name}")
        elif sub == "list":
            for s in ComfySession.list_sessions():
                self.bullet(s)
        elif sub == "delete":
            self._session.delete()
            self.success("Session deleted")
        else:
            print(Style.err(f"  Unknown: {sub!r}"))
