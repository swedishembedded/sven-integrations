"""AnyGen unified generation backend using stdlib urllib only."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from .project import GenerationResult, GenerationTask


class AnygenError(RuntimeError):
    """Raised when a generation call fails."""


class AnygenBackend:
    """Unified generation backend that delegates to multiple LLM providers."""

    OLLAMA_BASE = "http://localhost:11434"

    def generate(
        self,
        task: GenerationTask,
        api_key: str | None = None,
    ) -> GenerationResult:
        """Dispatch to the appropriate provider and return a GenerationResult."""
        result = GenerationResult(
            task_id=task.task_id,
            status="running",
            created_at=time.time(),
            metadata={"model": task.model, "provider": task.provider},
        )
        try:
            provider = task.provider.lower()
            if provider == "openai":
                output = self._call_openai(task, api_key)
            elif provider == "anthropic":
                output = self._call_anthropic(task, api_key)
            elif provider == "ollama":
                output = self._call_ollama(task)
            elif provider == "local":
                output = self._call_local(task)
            else:
                raise AnygenError(f"Unknown provider: {task.provider!r}")
            result.status = "completed"
            result.output = output
        except AnygenError as exc:
            result.status = "failed"
            result.error = str(exc)
        finally:
            result.completed_at = time.time()
        return result

    def _call_openai(self, task: GenerationTask, api_key: str | None) -> str:
        if not api_key:
            raise AnygenError("OpenAI API key required. Set via 'config set-key --provider openai'.")
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": task.model,
            "messages": [{"role": "user", "content": task.prompt}],
            "temperature": task.parameters.temperature,
            "max_tokens": task.parameters.max_tokens,
        }
        if task.parameters.top_p is not None:
            payload["top_p"] = task.parameters.top_p
        if task.parameters.stop_sequences:
            payload["stop"] = task.parameters.stop_sequences
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = self._http_post(url, payload, headers)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AnygenError(f"Unexpected OpenAI response: {data}") from exc

    def _call_anthropic(self, task: GenerationTask, api_key: str | None) -> str:
        if not api_key:
            raise AnygenError("Anthropic API key required.")
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": task.model,
            "max_tokens": task.parameters.max_tokens,
            "messages": [{"role": "user", "content": task.prompt}],
        }
        if task.parameters.stop_sequences:
            payload["stop_sequences"] = task.parameters.stop_sequences
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = self._http_post(url, payload, headers)
        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise AnygenError(f"Unexpected Anthropic response: {data}") from exc

    def _call_ollama(self, task: GenerationTask) -> str:
        url = f"{self.OLLAMA_BASE}/api/generate"
        payload = {
            "model": task.model,
            "prompt": task.prompt,
            "stream": False,
            "options": {
                "temperature": task.parameters.temperature,
                "num_predict": task.parameters.max_tokens,
            },
        }
        if task.parameters.top_p is not None:
            payload["options"]["top_p"] = task.parameters.top_p
        try:
            data = self._http_post(url, payload, {})
        except AnygenError as exc:
            raise AnygenError(
                f"Ollama request failed (is Ollama running on localhost:11434?): {exc}"
            ) from exc
        try:
            return data["response"]
        except KeyError as exc:
            raise AnygenError(f"Unexpected Ollama response: {data}") from exc

    def _call_local(self, task: GenerationTask) -> str:
        """Call a local binary named after the model via subprocess."""
        payload_str = json.dumps(
            {"prompt": task.prompt, "params": task.parameters.to_dict()}
        )
        try:
            result = subprocess.run(
                [task.model],
                input=payload_str,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise AnygenError(f"Local binary not found: {task.model!r}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AnygenError(f"Local binary timed out: {task.model!r}") from exc
        if result.returncode != 0:
            raise AnygenError(
                f"Local binary {task.model!r} exited {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def _http_post(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise AnygenError(f"HTTP {exc.code} from {url}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise AnygenError(f"Request to {url} failed: {exc.reason}") from exc
