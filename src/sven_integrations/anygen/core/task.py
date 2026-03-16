"""Task management utilities for AnyGen."""

from __future__ import annotations

import uuid

from ..project import GenerationParams, GenerationResult, GenerationTask

VALID_PROVIDERS = {"openai", "anthropic", "ollama", "local"}


def create_task(
    prompt: str,
    model: str,
    provider: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    top_p: float | None = None,
    stop_sequences: list[str] | None = None,
) -> GenerationTask:
    """Construct a new GenerationTask with a fresh UUID."""
    params = GenerationParams(
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        stop_sequences=stop_sequences or [],
    )
    return GenerationTask(
        task_id=str(uuid.uuid4()),
        prompt=prompt,
        model=model,
        provider=provider,
        parameters=params,
    )


def validate_task(task: GenerationTask) -> list[str]:
    """Return a list of validation error strings (empty means valid)."""
    errors: list[str] = []
    if not task.task_id:
        errors.append("task_id must not be empty")
    if not task.prompt.strip():
        errors.append("prompt must not be empty")
    if not task.model.strip():
        errors.append("model must not be empty")
    if task.provider not in VALID_PROVIDERS:
        errors.append(
            f"provider must be one of {sorted(VALID_PROVIDERS)}, got {task.provider!r}"
        )
    if not (0.0 <= task.parameters.temperature <= 2.0):
        errors.append(
            f"temperature must be between 0.0 and 2.0, got {task.parameters.temperature}"
        )
    if task.parameters.max_tokens < 1:
        errors.append(f"max_tokens must be >= 1, got {task.parameters.max_tokens}")
    if task.parameters.top_p is not None and not (0.0 <= task.parameters.top_p <= 1.0):
        errors.append(
            f"top_p must be between 0.0 and 1.0, got {task.parameters.top_p}"
        )
    return errors


def estimate_tokens(text: str) -> int:
    """Rough token count: ~1 token per 4 characters."""
    return max(1, len(text) // 4)


def format_result(result: GenerationResult, verbose: bool = False) -> str:
    """Format a GenerationResult as a human-readable string."""
    lines: list[str] = [
        f"Task:   {result.task_id}",
        f"Status: {result.status}",
    ]
    if result.output is not None:
        lines.append(f"Output:\n{result.output}")
    if result.error is not None:
        lines.append(f"Error:  {result.error}")
    if verbose:
        lines.append(f"Created: {result.created_at}")
        if result.completed_at:
            elapsed = result.completed_at - result.created_at
            lines.append(f"Elapsed: {elapsed:.2f}s")
        for k, v in result.metadata.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def task_to_messages(task: GenerationTask) -> list[dict[str, str]]:
    """Convert a GenerationTask to an OpenAI-style messages list."""
    return [{"role": "user", "content": task.prompt}]
