"""Interactive REPL console for the AnyGen harness."""

from __future__ import annotations

from typing import Any

from ..shared import Console, Style
from .core.task import create_task, format_result, validate_task
from .project import AnygenProject
from .session import AnygenSession


class AnygenConsole(Console):
    """REPL for AI text generation via multiple providers."""

    harness_name = "anygen"
    intro_extra = "Commands: generate, batch, results, config, status, help"

    def __init__(self, session_name: str = "default", **kwargs: Any) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._session = AnygenSession.open_or_create(session_name)
        raw = self._session.data.get("project")
        self._project: AnygenProject = (
            AnygenProject.from_dict(raw) if raw else AnygenProject()
        )

    def _save(self) -> None:
        self._session.data["project"] = self._project.to_dict()
        self._session.save()

    # ------------------------------------------------------------------
    # Commands

    def do_status(self, _arg: str) -> None:
        """Show current session and project status."""
        self.section("AnyGen Status")
        self.bullet(f"session: {self._session.name}")
        self.bullet(f"project: {self._project.name}")
        self.bullet(f"total tasks: {len(self._project.tasks)}")
        self.bullet(f"completed: {len(self._project.completed_tasks())}")
        self.bullet(f"pending: {len(self._project.pending_tasks())}")
        auth = self._session.data.get("auth", {})
        configured = [p for p, k in auth.items() if k]
        self.bullet(f"configured providers: {', '.join(configured) or '(none)'}")

    def do_generate(self, arg: str) -> None:
        """Generate text. Usage: generate PROMPT [--model MODEL] [--provider PROVIDER]"""
        parts = self.parse_args(arg)
        if not parts:
            print(Style.err("  Provide a prompt."))
            return
        model = "gpt-4o-mini"
        provider = "openai"
        temperature = 0.7
        max_tokens = 1024
        prompt_parts: list[str] = []
        it = iter(parts)
        for tok in it:
            if tok == "--model":
                model = next(it, model)
            elif tok == "--provider":
                provider = next(it, provider)
            elif tok == "--temperature":
                temperature = float(next(it, str(temperature)))
            elif tok == "--max-tokens":
                max_tokens = int(next(it, str(max_tokens)))
            else:
                prompt_parts.append(tok)
        prompt = " ".join(prompt_parts)
        if not prompt.strip():
            print(Style.err("  Prompt cannot be empty."))
            return
        task = create_task(
            prompt=prompt,
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        errors = validate_task(task)
        if errors:
            for e in errors:
                self.failure(e)
            return
        api_key = self._session.get_api_key(provider)
        self._project.add_task(task)
        self._save()
        self.section(f"Generating ({provider}/{model})...")
        from .backend import AnygenBackend

        be = AnygenBackend()
        result = be.generate(task, api_key=api_key)
        self._project.results.append(result)
        self._save()
        if result.status == "completed":
            self.success(f"Task {task.task_id[:8]}… completed")
            print(result.output or "")
        else:
            self.failure(f"Task failed: {result.error}")

    def do_batch(self, arg: str) -> None:
        """Run batch from file. Usage: batch --file PATH [--model MODEL] [--provider PROVIDER]"""
        parts = self.parse_args(arg)
        file_path = ""
        model = "gpt-4o-mini"
        provider = "openai"
        it = iter(parts)
        for tok in it:
            if tok == "--file":
                file_path = next(it, "")
            elif tok == "--model":
                model = next(it, model)
            elif tok == "--provider":
                provider = next(it, provider)
        if not file_path:
            print(Style.err("  Provide --file PATH"))
            return
        try:
            with open(file_path, encoding="utf-8") as f:
                prompts = [line.strip() for line in f if line.strip()]
        except OSError as exc:
            self.failure(str(exc))
            return
        self.section(f"Batch: {len(prompts)} prompts")
        from .backend import AnygenBackend

        be = AnygenBackend()
        api_key = self._session.get_api_key(provider)
        for i, prompt in enumerate(prompts, 1):
            task = create_task(prompt=prompt, model=model, provider=provider)
            self._project.add_task(task)
            result = be.generate(task, api_key=api_key)
            self._project.results.append(result)
            status_sym = "✓" if result.status == "completed" else "✗"
            self.bullet(f"[{i}/{len(prompts)}] {status_sym} {task.task_id[:8]}…")
        self._save()
        self.success("Batch complete")

    def do_results(self, arg: str) -> None:
        """Show results. Usage: results list|show --id ID|export --format FORMAT --output PATH"""
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "list"
        if sub == "list":
            if not self._project.results:
                self.bullet("(no results)")
                return
            self.section("Results")
            for r in self._project.results:
                sym = "✓" if r.status == "completed" else "✗"
                self.bullet(f"{sym} {r.task_id[:8]}… [{r.status}]")
        elif sub == "show":
            task_id = parts[2] if len(parts) > 2 and parts[1] == "--id" else (parts[1] if len(parts) > 1 else "")
            result = self._project.get_result(task_id) or next(
                (r for r in self._project.results if r.task_id.startswith(task_id)), None
            )
            if result is None:
                self.failure(f"Result not found: {task_id!r}")
                return
            print(format_result(result, verbose=True))
        elif sub == "export":
            fmt = "json"
            output = "results.json"
            it = iter(parts[1:])
            for tok in it:
                if tok == "--format":
                    fmt = next(it, "json")
                elif tok in ("--output", "-o"):
                    output = next(it, "results.json")
            from .core.export import (
                export_results_csv,
                export_results_json,
                export_results_markdown,
            )

            try:
                if fmt == "json":
                    export_results_json(self._project.results, output)
                elif fmt == "csv":
                    export_results_csv(self._project.results, output)
                elif fmt in ("md", "markdown"):
                    export_results_markdown(self._project.results, output)
                else:
                    self.failure(f"Unknown format: {fmt!r}")
                    return
                self.success(f"Exported to {output}")
            except OSError as exc:
                self.failure(str(exc))
        else:
            print(Style.err(f"  Unknown: {sub!r}"))

    def do_config(self, arg: str) -> None:
        """Config management. Usage: config set-key --provider P --key K | show | clear-keys"""
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "show"
        if sub == "set-key":
            provider = ""
            key = ""
            it = iter(parts[1:])
            for tok in it:
                if tok == "--provider":
                    provider = next(it, "")
                elif tok == "--key":
                    key = next(it, "")
            if not provider or not key:
                print(Style.err("  Provide --provider and --key"))
                return
            self._session.set_api_key(provider, key)
            self._session.save()
            self.success(f"API key set for {provider!r}")
        elif sub == "show":
            self.section("Provider Config")
            auth = self._session.data.get("auth", {})
            if not auth:
                self.bullet("(none configured)")
            for provider, key in auth.items():
                masked = key[:4] + "…" + key[-4:] if len(key) > 8 else "****"
                self.bullet(f"{provider}: {masked}")
        elif sub == "clear-keys":
            self._session.clear_keys()
            self._session.save()
            self.success("API keys cleared")
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
            for s in AnygenSession.list_sessions():
                self.bullet(s)
        elif sub == "delete":
            self._session.delete()
            self.success("Session deleted")
        else:
            print(Style.err(f"  Unknown: {sub!r}"))
