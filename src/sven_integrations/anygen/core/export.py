"""Export utilities for AnyGen task lists."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..project import AnygenTask


def export_tasks_json(tasks: list[AnygenTask], path: str) -> None:
    """Write tasks as a JSON array."""
    Path(path).write_text(
        json.dumps([t.to_dict() for t in tasks], indent=2, default=str),
        encoding="utf-8",
    )


def export_tasks_csv(tasks: list[AnygenTask], path: str) -> None:
    """Write tasks as CSV (task_id, operation, status, prompt, output_path, error)."""
    fieldnames = ["task_id", "local_id", "operation", "status", "prompt", "output_path", "error", "created_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for t in tasks:
            writer.writerow(
                {
                    "task_id": t.task_id,
                    "local_id": t.local_id,
                    "operation": t.operation,
                    "status": t.status,
                    "prompt": t.prompt,
                    "output_path": t.output_path or "",
                    "error": t.error or "",
                    "created_at": t.created_at,
                }
            )


def export_tasks_markdown(tasks: list[AnygenTask], path: str) -> None:
    """Write tasks as a Markdown document."""
    lines: list[str] = ["# AnyGen Tasks\n"]
    for i, t in enumerate(tasks, 1):
        tid = t.task_id or t.local_id
        lines.append(f"## Task {i}: `{tid}`\n")
        lines.append(f"- **Operation**: {t.operation}")
        lines.append(f"- **Status**: {t.status}")
        if t.output_path:
            lines.append(f"- **Output**: `{t.output_path}`")
        if t.error:
            lines.append(f"- **Error**: {t.error}")
        lines.append(f"\n**Prompt:**\n\n> {t.prompt}\n")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
