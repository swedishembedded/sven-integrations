"""Task helper utilities for the AnyGen harness."""

from __future__ import annotations

from ..project import OPERATION_EXTENSIONS, VALID_OPERATIONS, AnygenTask


def validate_task(task: AnygenTask) -> list[str]:
    """Return a list of validation error strings (empty list means valid)."""
    errors: list[str] = []
    if not task.local_id:
        errors.append("local_id must not be empty")
    if not task.prompt.strip():
        errors.append("prompt must not be empty")
    if task.operation not in VALID_OPERATIONS:
        errors.append(
            f"operation must be one of {sorted(VALID_OPERATIONS)}, got {task.operation!r}"
        )
    return errors


def expected_extension(operation: str) -> str:
    """Return the expected file extension for a given operation."""
    return OPERATION_EXTENSIONS.get(operation, ".bin")


def format_task(task: AnygenTask, *, verbose: bool = False) -> str:
    """Format a task as a human-readable string."""
    tid = task.task_id or task.local_id
    lines: list[str] = [
        f"task_id   : {tid}",
        f"operation : {task.operation}",
        f"status    : {task.status}",
        f"prompt    : {task.prompt[:120]}{'…' if len(task.prompt) > 120 else ''}",
    ]
    if task.output_path:
        lines.append(f"output    : {task.output_path}")
    if task.error:
        lines.append(f"error     : {task.error}")
    if verbose:
        import time
        lines.append(f"created   : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task.created_at))}")
        if task.completed_at:
            elapsed = task.completed_at - task.created_at
            lines.append(f"elapsed   : {elapsed:.1f}s")
        lines.append(f"submitted : {task.submitted}")
    return "\n".join(lines)
