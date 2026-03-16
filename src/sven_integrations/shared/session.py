"""Base session management for integration harnesses.

Each harness maintains a *session* — a named workspace for a running
desktop application.  Sessions are persisted as JSON in a platform-
appropriate state directory so that multiple CLI invocations against
the same application instance share state without extra flags.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class SessionError(RuntimeError):
    """Raised when session state is inconsistent or corrupt."""


def _state_dir() -> Path:
    """Return the per-user state directory for sven-integrations."""
    base = os.environ.get("SVEN_INTEGRATIONS_STATE_DIR") or os.path.expanduser(
        "~/.local/share/sven-integrations"
    )
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class SessionMeta:
    """Metadata stored alongside every session."""

    name: str
    harness: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()


class BaseSession:
    """Persistent JSON-backed session for a harness.

    Subclasses define a *harness* name (e.g. ``"gimp"``).  Each named
    session lives at ``<state_dir>/<harness>/<name>.json``.

    The ``data`` attribute holds the raw session payload and is entirely
    owned by the subclass — this base only handles load / save / list.
    """

    harness: str = "base"

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.meta = SessionMeta(name=name, harness=self.harness)
        self.data: dict[str, Any] = {}
        self._path = _state_dir() / self.harness / f"{name}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Persistence

    def load(self) -> bool:
        """Load session from disk.  Returns True if a file was found."""
        if not self._path.exists():
            return False
        try:
            payload = json.loads(self._path.read_text())
            self.meta = SessionMeta(**payload["meta"])
            self.data = payload.get("data", {})
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SessionError(
                f"Session file {self._path} is corrupt: {exc}"
            ) from exc
        return True

    def save(self) -> None:
        """Persist session to disk atomically."""
        self.meta.touch()
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"meta": asdict(self.meta), "data": self.data},
                indent=2,
                default=str,
            )
        )
        tmp.replace(self._path)

    def delete(self) -> bool:
        """Remove this session file.  Returns True if it existed."""
        if self._path.exists():
            self._path.unlink()
            return True
        return False

    # ------------------------------------------------------------------
    # Introspection

    @classmethod
    def list_sessions(cls) -> list[str]:
        """Return the names of all existing sessions for this harness."""
        directory = _state_dir() / cls.harness
        if not directory.exists():
            return []
        return sorted(p.stem for p in directory.glob("*.json"))

    @classmethod
    def open_or_create(cls, name: str = "default") -> "BaseSession":
        """Return a loaded session or a fresh one with the given name."""
        s = cls(name)
        s.load()
        return s

    # ------------------------------------------------------------------
    # Context-manager support

    def __enter__(self) -> "BaseSession":
        self.load()
        return self

    def __exit__(self, *_: object) -> None:
        self.save()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(harness={self.harness!r}, name={self.name!r})"
