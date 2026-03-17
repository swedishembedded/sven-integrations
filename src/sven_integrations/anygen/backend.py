"""AnyGen content-generation backend (stdlib urllib, zero extra deps)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .project import OPERATION_EXTENSIONS

_DEFAULT_BASE_URL = "https://api.anygen.ai/v1"
_POLL_INTERVAL = 3.0
_DEFAULT_TIMEOUT = 300.0


class AnygenError(RuntimeError):
    """Raised when an AnyGen API call fails."""


class AnygenBackend:
    """Thin REST client for the AnyGen content-generation API.

    All network I/O uses the stdlib ``urllib`` only — no third-party deps.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        poll_interval: float = _POLL_INTERVAL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal HTTP helpers

    def _require_key(self) -> str:
        if not self.api_key:
            raise AnygenError(
                "API key not configured.\n"
                "Run:  sven-integrations-anygen config set api_key <your-key>"
            )
        return self.api_key

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._require_key()}"}

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            **self._auth_headers(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise AnygenError(f"HTTP {exc.code} {exc.reason}: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise AnygenError(f"Network error posting to {url}: {exc.reason}") from exc

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {**self._auth_headers(), "Accept": "application/json"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise AnygenError(f"HTTP {exc.code} {exc.reason}: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise AnygenError(f"Network error fetching {url}: {exc.reason}") from exc

    def _get_binary(self, url: str) -> bytes:
        """Download raw bytes from an absolute or relative URL."""
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"
        headers = self._auth_headers()
        req = urllib.request.Request(full_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise AnygenError(f"HTTP {exc.code} {exc.reason}: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise AnygenError(f"Download failed for {full_url}: {exc.reason}") from exc

    # ------------------------------------------------------------------
    # Public API

    def create_task(self, operation: str, prompt: str, **extra: Any) -> str:
        """POST /tasks — submit a generation task, return remote task_id."""
        payload: dict[str, Any] = {"operation": operation, "prompt": prompt, **extra}
        data = self._post_json("/tasks", payload)
        remote_id = data.get("task_id") or data.get("id")
        if not remote_id:
            raise AnygenError(f"POST /tasks returned no task_id. Response: {data}")
        return str(remote_id)

    def get_status(self, task_id: str) -> dict[str, Any]:
        """GET /tasks/{id} — return current status dict."""
        return self._get_json(f"/tasks/{task_id}")

    def poll_until_done(
        self,
        task_id: str,
        progress_cb: Any = None,
    ) -> dict[str, Any]:
        """Poll GET /tasks/{id} until completed/failed or self.timeout expires."""
        deadline = time.monotonic() + self.timeout
        while True:
            data = self.get_status(task_id)
            status = data.get("status", "unknown")
            if progress_cb:
                progress_cb(data)
            if status in ("completed", "failed", "error", "cancelled"):
                return data
            if time.monotonic() >= deadline:
                raise AnygenError(
                    f"Task {task_id!r} did not finish within {self.timeout:.0f}s "
                    f"(last status: {status!r})"
                )
            time.sleep(self.poll_interval)

    def download(self, task_id: str, dest: Path, operation: str) -> Path:
        """Download the result of a completed task.

        ``dest`` may be a directory (a filename is derived from task_id +
        extension) or a full file path.  Returns the final Path written.
        """
        # Try the canonical download endpoint first.
        try:
            raw = self._get_binary(f"/tasks/{task_id}/download")
        except AnygenError:
            # Fallback: ask status for an output_url / download_url field.
            status_data = self.get_status(task_id)
            url = status_data.get("output_url") or status_data.get("download_url")
            if not url:
                raise AnygenError(
                    f"No download URL available for task {task_id!r}. "
                    f"Status: {status_data.get('status')!r}"
                )
            raw = self._get_binary(url)

        if dest.is_dir() or not dest.suffix:
            ext = OPERATION_EXTENSIONS.get(operation, ".bin")
            dest = dest / f"{task_id}{ext}"

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        return dest
