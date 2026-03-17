"""AnyGen session management."""

from __future__ import annotations

from ..shared import BaseSession
from .project import AnygenTask, HistoryEntry


class AnygenSession(BaseSession):
    """Persistent session for AnyGen.

    ``data["config"]``     — {key: value} pairs (api_key, api_base_url, …)
    ``data["tasks"]``      — list of serialised AnygenTask dicts
    ``data["history"]``    — list of HistoryEntry dicts (undo stack)
    ``data["redo_stack"]`` — list of HistoryEntry dicts (redo stack)
    """

    harness: str = "anygen"

    # ------------------------------------------------------------------
    # Config

    def get_config(self, key: str) -> str | None:
        return self.data.get("config", {}).get(key)

    def set_config(self, key: str, value: str) -> None:
        if "config" not in self.data:
            self.data["config"] = {}
        self.data["config"][key] = value

    def all_config(self) -> dict[str, str]:
        return dict(self.data.get("config", {}))

    def get_api_key(self) -> str | None:
        return self.get_config("api_key")

    def get_api_base_url(self) -> str:
        return self.get_config("api_base_url") or "https://api.anygen.ai/v1"

    # ------------------------------------------------------------------
    # Tasks

    def load_tasks(self) -> list[AnygenTask]:
        return [AnygenTask.from_dict(d) for d in self.data.get("tasks", [])]

    def save_tasks(self, tasks: list[AnygenTask]) -> None:
        self.data["tasks"] = [t.to_dict() for t in tasks]

    def upsert_task(self, task: AnygenTask) -> None:
        """Insert or update a task by local_id."""
        tasks = self.load_tasks()
        for i, t in enumerate(tasks):
            if t.local_id == task.local_id:
                tasks[i] = task
                self.save_tasks(tasks)
                return
        tasks.append(task)
        self.save_tasks(tasks)

    def find_task(self, identifier: str) -> AnygenTask | None:
        """Resolve by remote task_id or local_id; prefix match supported."""
        for t in self.load_tasks():
            if t.task_id == identifier or t.local_id == identifier:
                return t
            if (t.task_id and t.task_id.startswith(identifier)) or t.local_id.startswith(identifier):
                return t
        return None

    # ------------------------------------------------------------------
    # History / undo-redo

    def load_history(self) -> list[HistoryEntry]:
        return [HistoryEntry.from_dict(d) for d in self.data.get("history", [])]

    def load_redo_stack(self) -> list[HistoryEntry]:
        return [HistoryEntry.from_dict(d) for d in self.data.get("redo_stack", [])]

    def push_history(self, entry: HistoryEntry) -> None:
        history = self.load_history()
        history.append(entry)
        self.data["history"] = [e.to_dict() for e in history]
        self.data["redo_stack"] = []  # clear redo on new action

    def undo(self) -> HistoryEntry | None:
        history = self.load_history()
        if not history:
            return None
        entry = history.pop()
        self.data["history"] = [e.to_dict() for e in history]
        redo = self.load_redo_stack()
        redo.append(entry)
        self.data["redo_stack"] = [e.to_dict() for e in redo]
        return entry

    def redo(self) -> HistoryEntry | None:
        redo = self.load_redo_stack()
        if not redo:
            return None
        entry = redo.pop()
        self.data["redo_stack"] = [e.to_dict() for e in redo]
        history = self.load_history()
        history.append(entry)
        self.data["history"] = [e.to_dict() for e in history]
        return entry
