"""Export utilities for AnyGen generation results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..project import GenerationResult


def export_results_json(results: list[GenerationResult], path: str) -> None:
    """Write results as a JSON array to *path*."""
    payload = [r.to_dict() for r in results]
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def export_results_csv(results: list[GenerationResult], path: str) -> None:
    """Write results as CSV to *path*.

    Columns: task_id, status, output, error, created_at, completed_at
    """
    fieldnames = ["task_id", "status", "output", "error", "created_at", "completed_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {
                "task_id": r.task_id,
                "status": r.status,
                "output": r.output or "",
                "error": r.error or "",
                "created_at": r.created_at,
                "completed_at": r.completed_at or "",
            }
            writer.writerow(row)


def export_results_markdown(results: list[GenerationResult], path: str) -> None:
    """Write results as a Markdown document to *path*."""
    lines: list[str] = ["# Generation Results\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"## Result {i}: `{r.task_id}`\n")
        lines.append(f"- **Status**: {r.status}")
        if r.completed_at:
            elapsed = r.completed_at - r.created_at
            lines.append(f"- **Elapsed**: {elapsed:.2f}s")
        for k, v in r.metadata.items():
            lines.append(f"- **{k.title()}**: {v}")
        if r.output is not None:
            lines.append("\n**Output:**\n")
            lines.append("```")
            lines.append(r.output)
            lines.append("```\n")
        if r.error is not None:
            lines.append(f"\n**Error:** {r.error}\n")
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def format_as_template(result: GenerationResult, template: str) -> str:
    """Fill a string template using result fields.

    Supported placeholders: {output}, {prompt}, {model}, {provider},
    {task_id}, {status}, {error}, {created_at}, {completed_at}
    """
    replacements: dict[str, str] = {
        "{output}": result.output or "",
        "{task_id}": result.task_id,
        "{status}": result.status,
        "{error}": result.error or "",
        "{created_at}": str(result.created_at),
        "{completed_at}": str(result.completed_at or ""),
        "{model}": result.metadata.get("model", ""),
        "{provider}": result.metadata.get("provider", ""),
        "{prompt}": result.metadata.get("prompt", ""),
    }
    out = template
    for placeholder, value in replacements.items():
        out = out.replace(placeholder, value)
    return out
