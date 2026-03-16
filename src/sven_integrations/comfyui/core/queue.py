"""ComfyUI queue management utilities."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..backend import ComfyBackend


def poll_until_done(
    backend: "ComfyBackend",
    prompt_id: str,
    timeout_s: float = 300.0,
    poll_interval_s: float = 2.0,
) -> dict[str, Any]:
    """Poll the history API until the prompt is done or timeout is reached.

    Returns the history entry dict for *prompt_id*.
    Raises ``TimeoutError`` if the prompt is still running after *timeout_s*.
    """
    from ..backend import ComfyError

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            history = backend.get_history(prompt_id)
        except ComfyError:
            history = {}
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(poll_interval_s)
    raise TimeoutError(
        f"Prompt {prompt_id!r} did not complete within {timeout_s:.0f}s"
    )


def format_queue_status(status: dict[str, Any]) -> str:
    """Format a queue status dict as a human-readable string."""
    queue_running = status.get("queue_running", [])
    queue_pending = status.get("queue_pending", [])
    lines: list[str] = [
        f"Running:  {len(queue_running)} prompt(s)",
        f"Pending:  {len(queue_pending)} prompt(s)",
    ]
    for item in queue_running:
        if isinstance(item, list) and len(item) >= 2:
            lines.append(f"  [running] {item[1]}")
    for item in queue_pending:
        if isinstance(item, list) and len(item) >= 2:
            lines.append(f"  [queued]  {item[1]}")
    return "\n".join(lines)


def list_pending_prompts(backend: "ComfyBackend") -> list[dict[str, Any]]:
    """Return a list of pending prompt descriptors from the queue."""
    status = backend.get_queue_status()
    pending = status.get("queue_pending", [])
    result: list[dict[str, Any]] = []
    for item in pending:
        if isinstance(item, list) and len(item) >= 2:
            result.append({"number": item[0], "prompt_id": item[1]})
        elif isinstance(item, dict):
            result.append(item)
    return result


def cancel_prompt(backend: "ComfyBackend", prompt_id: str) -> bool:
    """Attempt to cancel a queued prompt by deleting it from the queue.

    Returns True if the delete request was sent successfully.
    """
    import json
    import urllib.request

    url = f"{backend.server_url}/queue"
    payload = json.dumps({"delete": [prompt_id]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def get_progress(history: dict[str, Any]) -> float:
    """Estimate generation progress as a float in [0.0, 1.0].

    Uses the ``status`` field of the history entry if available.
    Returns 1.0 if the status is ``success`` or if outputs are present.
    """
    status_info = history.get("status", {})
    status_str = status_info.get("status_str", "")
    if status_str in ("success", "complete"):
        return 1.0
    if history.get("outputs"):
        return 1.0
    messages = status_info.get("messages", [])
    for msg in messages:
        if isinstance(msg, (list, tuple)) and len(msg) >= 2:
            if msg[0] in ("execution_success", "execution_complete"):
                return 1.0
    return 0.0
