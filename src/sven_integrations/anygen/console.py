"""Interactive REPL console for the AnyGen harness."""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..shared import Console, Style
from .backend import AnygenBackend, AnygenError
from .core.verify import VerifyError, verify_file
from .project import VALID_OPERATIONS, AnygenTask, HistoryEntry
from .session import AnygenSession


class AnygenConsole(Console):
    """REPL for the AnyGen content-generation harness."""

    harness_name = "anygen"
    intro_extra = "Commands: task, config, file, session, status, help"

    def __init__(self, session_name: str = "default", **kwargs: Any) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._session = AnygenSession.open_or_create(session_name)

    def _save(self) -> None:
        self._session.save()

    def _backend(self) -> AnygenBackend:
        return AnygenBackend(
            api_key=self._session.get_api_key(),
            base_url=self._session.get_api_base_url(),
        )

    # ------------------------------------------------------------------
    # status

    def do_status(self, _arg: str) -> None:
        """Show session overview."""
        tasks = self._session.load_tasks()
        history = self._session.load_history()
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        self.section("AnyGen Session")
        self.bullet(f"session  : {self._session.name}")
        self.bullet(f"tasks    : {len(tasks)} ({completed} completed, {failed} failed)")
        self.bullet(f"history  : {len(history)} entries")
        key = self._session.get_api_key()
        masked = (key[:6] + "…" if key else "(not set)")
        self.bullet(f"api_key  : {masked}")

    # ------------------------------------------------------------------
    # task

    def do_task(self, arg: str) -> None:
        """Task management.
        Usage: task run|create|status|download|list|prepare [OPTIONS]
        """
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "list"

        if sub == "list":
            tasks = self._session.load_tasks()
            if not tasks:
                self.bullet("(no tasks)")
                return
            self.section("Tasks")
            for t in tasks:
                sym = "✓" if t.status == "completed" else ("✗" if t.status == "failed" else "·")
                tid = t.task_id or t.local_id
                self.bullet(f"{sym} {tid[:24]}  [{t.operation}]  {t.status}")

        elif sub == "prepare":
            operation, prompt = "", ""
            it = iter(parts[1:])
            for tok in it:
                if tok in ("--operation", "-op"):
                    operation = next(it, "")
                elif tok in ("--prompt", "-p"):
                    prompt = next(it, "")
            if operation not in VALID_OPERATIONS:
                print(Style.err(f"  Invalid operation. Choose: {', '.join(sorted(VALID_OPERATIONS))}"))
                return
            if not prompt.strip():
                print(Style.err("  --prompt cannot be empty"))
                return
            local_id = str(uuid.uuid4())
            task = AnygenTask(
                local_id=local_id, operation=operation, prompt=prompt, submitted=False
            )
            self._session.upsert_task(task)
            self._session.push_history(
                HistoryEntry(action="prepare", task_id=local_id, details={"operation": operation})
            )
            self._save()
            self.success(f"Prepared [{operation}] local_id={local_id}")

        elif sub == "create":
            operation, prompt = "", ""
            it = iter(parts[1:])
            for tok in it:
                if tok in ("--operation", "-op"):
                    operation = next(it, "")
                elif tok in ("--prompt", "-p"):
                    prompt = next(it, "")
            if operation not in VALID_OPERATIONS:
                print(Style.err(f"  Invalid operation. Choose: {', '.join(sorted(VALID_OPERATIONS))}"))
                return
            if not prompt.strip():
                print(Style.err("  --prompt cannot be empty"))
                return
            be = self._backend()
            self.section(f"Creating task [{operation}]…")
            try:
                remote_id = be.create_task(operation=operation, prompt=prompt)
            except AnygenError as exc:
                self.failure(str(exc))
                return
            task = AnygenTask(
                local_id=str(uuid.uuid4()),
                operation=operation,
                prompt=prompt,
                task_id=remote_id,
                submitted=True,
                status="queued",
            )
            self._session.upsert_task(task)
            self._session.push_history(
                HistoryEntry(action="create", task_id=remote_id, details={"operation": operation})
            )
            self._save()
            self.success(f"task_id = {remote_id}")

        elif sub == "status":
            task_id = parts[1] if len(parts) > 1 else ""
            if not task_id:
                print(Style.err("  Provide task_id"))
                return
            be = self._backend()
            local_task = self._session.find_task(task_id)
            remote_id = local_task.task_id if (local_task and local_task.task_id) else task_id
            try:
                data = be.get_status(remote_id)
            except AnygenError as exc:
                self.failure(str(exc))
                return
            if local_task:
                local_task.status = data.get("status", local_task.status)
                self._session.upsert_task(local_task)
                self._save()
            self.section("Status")
            for k, v in data.items():
                self.bullet(f"{k}: {v}")

        elif sub == "download":
            task_id, output = "", "."
            it = iter(parts[1:])
            first = True
            for tok in it:
                if tok in ("--output", "-o"):
                    output = next(it, ".")
                elif first:
                    task_id = tok
                    first = False
            if not task_id:
                print(Style.err("  Provide task_id"))
                return
            be = self._backend()
            local_task = self._session.find_task(task_id)
            remote_id = local_task.task_id if (local_task and local_task.task_id) else task_id
            operation = local_task.operation if local_task else "data"
            from pathlib import Path
            try:
                out_path = be.download(remote_id, Path(output), operation)
            except AnygenError as exc:
                self.failure(str(exc))
                return
            if local_task:
                local_task.output_path = str(out_path)
                local_task.status = "completed"
                self._session.upsert_task(local_task)
                self._save()
            self.success(f"Downloaded: {out_path}")

        elif sub == "run":
            operation, prompt, output, timeout = "", "", ".", 300.0
            it = iter(parts[1:])
            for tok in it:
                if tok in ("--operation", "-op"):
                    operation = next(it, "")
                elif tok in ("--prompt", "-p"):
                    prompt = next(it, "")
                elif tok in ("--output", "-o"):
                    output = next(it, ".")
                elif tok == "--timeout":
                    timeout = float(next(it, "300"))
            if operation not in VALID_OPERATIONS:
                print(Style.err(f"  Invalid operation. Choose: {', '.join(sorted(VALID_OPERATIONS))}"))
                return
            if not prompt.strip():
                print(Style.err("  --prompt cannot be empty"))
                return
            be = self._backend()
            be.timeout = timeout
            self.section(f"Running [{operation}]…")
            try:
                remote_id = be.create_task(operation=operation, prompt=prompt)
                self.bullet(f"created: {remote_id}")
                status_data = be.poll_until_done(
                    remote_id,
                    progress_cb=lambda d: self.bullet(f"status: {d.get('status')}"),
                )
                if status_data.get("status") != "completed":
                    self.failure(f"Task failed: {status_data.get('error')}")
                    return
                from pathlib import Path
                out_path = be.download(remote_id, Path(output), operation)
                self.success(f"Done: {out_path}")
            except AnygenError as exc:
                self.failure(str(exc))

        else:
            print(Style.err(f"  Unknown sub-command: {sub!r}"))

    # ------------------------------------------------------------------
    # config

    def do_config(self, arg: str) -> None:
        """Config management.
        Usage: config set KEY VALUE | get KEY | list
        """
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "list"

        if sub == "set":
            if len(parts) < 3:
                print(Style.err("  Usage: config set KEY VALUE"))
                return
            key, value = parts[1], parts[2]
            self._session.set_config(key, value)
            self._save()
            masked = value[:6] + "…" if len(value) > 8 else value
            self.success(f"{key} = {masked!r}")

        elif sub == "get":
            key = parts[1] if len(parts) > 1 else ""
            if not key:
                print(Style.err("  Usage: config get KEY"))
                return
            val = self._session.get_config(key)
            if val is None:
                print(Style.err(f"  Key {key!r} not set"))
            else:
                self.bullet(f"{key} = {val}")

        elif sub == "list":
            self.section("Configuration")
            cfg = self._session.all_config()
            if not cfg:
                self.bullet("(none)")
                return
            for k, v in cfg.items():
                masked = (v[:6] + "…" + v[-4:] if k.lower().endswith(("key", "secret", "token")) and len(v) > 12 else v)
                self.bullet(f"{k} = {masked}")

        else:
            print(Style.err(f"  Unknown: {sub!r}"))

    # ------------------------------------------------------------------
    # file

    def do_file(self, arg: str) -> None:
        """File utilities.
        Usage: file verify PATH
        """
        parts = self.parse_args(arg)
        sub = parts[0] if parts else ""
        if sub == "verify":
            path = parts[1] if len(parts) > 1 else ""
            if not path:
                print(Style.err("  Usage: file verify PATH"))
                return
            try:
                result = verify_file(path)
                self.success(f"{result['path']}  ({result['type']}, {result['size']} B)  {result['details']}")
            except VerifyError as exc:
                self.failure(str(exc))
        else:
            print(Style.err(f"  Unknown: {sub!r}"))

    # ------------------------------------------------------------------
    # session

    def do_session(self, arg: str) -> None:
        """Session management.
        Usage: session show | list | delete | undo | redo | history
        """
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "show"

        if sub == "show":
            tasks = self._session.load_tasks()
            history = self._session.load_history()
            self.section("Session")
            self.bullet(f"name    : {self._session.name}")
            self.bullet(f"tasks   : {len(tasks)}")
            self.bullet(f"history : {len(history)}")

        elif sub == "list":
            for name in AnygenSession.list_sessions():
                self.bullet(name)

        elif sub == "delete":
            self._session.delete()
            self.success("Session deleted")

        elif sub == "undo":
            entry = self._session.undo()
            self._save()
            if entry is None:
                self.bullet("(nothing to undo)")
            else:
                self.success(f"Undone: {entry.action} task={entry.task_id}")

        elif sub == "redo":
            entry = self._session.redo()
            self._save()
            if entry is None:
                self.bullet("(nothing to redo)")
            else:
                self.success(f"Redone: {entry.action} task={entry.task_id}")

        elif sub == "history":
            history = self._session.load_history()
            if not history:
                self.bullet("(no history)")
                return
            self.section("History")
            for i, e in enumerate(history, 1):
                ts = time.strftime("%H:%M:%S", time.localtime(e.timestamp))
                tid = (e.task_id or "-")[:24]
                self.bullet(f"{i:3}. [{ts}] {e.action:10}  {tid}")

        else:
            print(Style.err(f"  Unknown: {sub!r}"))
