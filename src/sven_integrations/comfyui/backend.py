"""ComfyUI REST API + WebSocket backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class ComfyError(RuntimeError):
    """Raised when a ComfyUI API operation fails."""


class ComfyBackend:
    """Wraps the ComfyUI REST API for queue and history operations.

    Optional WebSocket support for live queue monitoring requires the
    ``websocket-client`` package; falls back to polling if unavailable.
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8188") -> None:
        self.server_url = server_url.rstrip("/")

    # ------------------------------------------------------------------
    # Connection check

    def connect(self, server_url: str | None = None) -> bool:
        """Test connectivity to the ComfyUI server.

        Updates ``self.server_url`` if *server_url* is provided.
        Returns True if the server responds to ``/system_stats``.
        """
        if server_url:
            self.server_url = server_url.rstrip("/")
        try:
            self.get_system_stats()
            return True
        except ComfyError:
            return False

    # ------------------------------------------------------------------
    # Queue operations

    def queue_prompt(self, workflow_api: dict[str, Any], client_id: str) -> str:
        """Submit a workflow prompt to the ComfyUI queue.

        Returns the ``prompt_id`` assigned by the server.
        """
        payload = {"prompt": workflow_api, "client_id": client_id}
        data = self._post("/prompt", payload)
        try:
            return data["prompt_id"]
        except KeyError as exc:
            raise ComfyError(f"Unexpected queue response: {data}") from exc

    def get_queue_status(self) -> dict[str, Any]:
        """Return the current queue state (running + pending)."""
        return self._get("/queue")

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        """Return the execution history for a given prompt_id."""
        return self._get(f"/history/{prompt_id}")

    def get_output_images(self, prompt_id: str) -> list[dict[str, Any]]:
        """Return a list of output image descriptors for a completed prompt."""
        history = self.get_history(prompt_id)
        entry = history.get(prompt_id, {})
        outputs: list[dict[str, Any]] = []
        for node_output in entry.get("outputs", {}).values():
            for img in node_output.get("images", []):
                outputs.append(img)
        return outputs

    def interrupt_current(self) -> None:
        """Send an interrupt signal to stop the currently executing prompt."""
        self._post("/interrupt", {})

    def get_system_stats(self) -> dict[str, Any]:
        """Return server system statistics (VRAM, Python version, etc.)."""
        return self._get("/system_stats")

    def upload_image(self, image_path: str) -> dict[str, Any]:
        """Upload an image file to the ComfyUI input directory.

        Uses a multipart/form-data POST to ``/upload/image``.
        Returns the server's response dict with ``name`` and ``subfolder``.
        """
        path = Path(image_path)
        if not path.exists():
            raise ComfyError(f"Image not found: {image_path!r}")
        boundary = "----sven-boundary"
        file_data = path.read_bytes()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
        url = f"{self.server_url}/upload/image"
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ComfyError(f"Upload failed {exc.code}: {exc.read().decode()}") from exc
        except urllib.error.URLError as exc:
            raise ComfyError(f"Upload request failed: {exc.reason}") from exc

    # ------------------------------------------------------------------
    # Low-level HTTP helpers

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.server_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ComfyError(f"GET {path} failed {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ComfyError(
                f"Cannot reach ComfyUI at {self.server_url} ({exc.reason}). "
                "Is ComfyUI running?"
            ) from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.server_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            raise ComfyError(f"POST {path} failed {exc.code}: {exc.read().decode()}") from exc
        except urllib.error.URLError as exc:
            raise ComfyError(f"POST {path} request failed: {exc.reason}") from exc
