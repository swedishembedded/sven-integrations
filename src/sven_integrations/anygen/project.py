"""AnyGen task and session data models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

OPERATION_EXTENSIONS: dict[str, str] = {
    "slide": ".pptx",
    "doc": ".docx",
    "pdf": ".pdf",
    "image": ".png",
    "data": ".json",
}

VALID_OPERATIONS: frozenset[str] = frozenset(OPERATION_EXTENSIONS)


@dataclass
class AnygenTask:
    """A single content-generation task tracked in the session."""

    local_id: str       # local UUID (always set; used before remote_id is known)
    operation: str      # slide | doc | pdf | image | data
    prompt: str
    task_id: str = ""   # remote task ID returned by the API after submission
    status: str = "pending"  # pending | queued | running | completed | failed
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    output_path: str | None = None   # local filesystem path after download
    output_url: str | None = None    # remote URL provided by the API
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    submitted: bool = False          # True once POSTed to the API

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_id": self.local_id,
            "operation": self.operation,
            "prompt": self.prompt,
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "output_path": self.output_path,
            "output_url": self.output_url,
            "error": self.error,
            "metadata": self.metadata,
            "submitted": self.submitted,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AnygenTask":
        raw_local = d.get("local_id") or d.get("task_id") or str(uuid.uuid4())
        return cls(
            local_id=raw_local,
            operation=d.get("operation", "data"),
            prompt=d.get("prompt", ""),
            task_id=d.get("task_id", ""),
            status=d.get("status", "pending"),
            created_at=float(d.get("created_at", time.time())),
            completed_at=d.get("completed_at"),
            output_path=d.get("output_path"),
            output_url=d.get("output_url"),
            error=d.get("error"),
            metadata=dict(d.get("metadata", {})),
            submitted=bool(d.get("submitted", False)),
        )


@dataclass
class HistoryEntry:
    """One entry in the session undo/redo history."""

    action: str
    task_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HistoryEntry":
        return cls(
            action=d["action"],
            task_id=d.get("task_id"),
            timestamp=float(d.get("timestamp", time.time())),
            details=dict(d.get("details", {})),
        )
