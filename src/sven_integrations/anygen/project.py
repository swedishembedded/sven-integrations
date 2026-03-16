"""AnyGen project and task models."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

TaskStatus = Literal["pending", "running", "completed", "failed"]
ProviderName = Literal["openai", "anthropic", "ollama", "local"]


@dataclass
class GenerationParams:
    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float | None = None
    stop_sequences: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "stop_sequences": self.stop_sequences,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GenerationParams":
        return cls(
            temperature=float(d.get("temperature", 0.7)),
            max_tokens=int(d.get("max_tokens", 1024)),
            top_p=d.get("top_p"),
            stop_sequences=list(d.get("stop_sequences", [])),
        )


@dataclass
class GenerationTask:
    task_id: str
    prompt: str
    model: str
    provider: str
    parameters: GenerationParams = field(default_factory=GenerationParams)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "model": self.model,
            "provider": self.provider,
            "parameters": self.parameters.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GenerationTask":
        return cls(
            task_id=d["task_id"],
            prompt=d["prompt"],
            model=d["model"],
            provider=d["provider"],
            parameters=GenerationParams.from_dict(d.get("parameters", {})),
        )


@dataclass
class GenerationResult:
    task_id: str
    status: str = "pending"
    output: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GenerationResult":
        return cls(
            task_id=d["task_id"],
            status=d.get("status", "pending"),
            output=d.get("output"),
            error=d.get("error"),
            created_at=float(d.get("created_at", time.time())),
            completed_at=d.get("completed_at"),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass
class AnygenProject:
    name: str = "default"
    provider_config: dict[str, Any] = field(default_factory=dict)
    tasks: list[GenerationTask] = field(default_factory=list)
    results: list[GenerationResult] = field(default_factory=list)

    def add_task(self, task: GenerationTask) -> None:
        self.tasks.append(task)

    def get_result(self, task_id: str) -> GenerationResult | None:
        for r in self.results:
            if r.task_id == task_id:
                return r
        return None

    def pending_tasks(self) -> list[GenerationTask]:
        completed_ids = {r.task_id for r in self.results if r.status in ("completed", "failed")}
        return [t for t in self.tasks if t.task_id not in completed_ids]

    def completed_tasks(self) -> list[GenerationTask]:
        completed_ids = {r.task_id for r in self.results if r.status == "completed"}
        return [t for t in self.tasks if t.task_id in completed_ids]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider_config": self.provider_config,
            "tasks": [t.to_dict() for t in self.tasks],
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AnygenProject":
        return cls(
            name=d.get("name", "default"),
            provider_config=dict(d.get("provider_config", {})),
            tasks=[GenerationTask.from_dict(t) for t in d.get("tasks", [])],
            results=[GenerationResult.from_dict(r) for r in d.get("results", [])],
        )
