"""Output formatting utilities for sven-integrations CLIs.

All harness commands produce either:
  - Human-readable coloured text (default, interactive use)
  - Structured JSON (when ``--json`` flag is active)

Both modes go to *stdout* so they can be piped.  Errors always go to
*stderr* regardless of mode.
"""

from __future__ import annotations

import functools
import json
import sys
from typing import Any, Callable, NoReturn, TypeVar

import click

_F = TypeVar("_F", bound=Callable[..., Any])

# Thread-local flag set by the top-level CLI when ``--json`` is passed.
_JSON_MODE: bool = False


def set_json_mode(enabled: bool) -> None:  # noqa: FBT001
    global _JSON_MODE
    _JSON_MODE = enabled


def is_json_mode() -> bool:
    return _JSON_MODE


def emit(message: str, *, nl: bool = True) -> None:
    """Print a human-readable message (suppressed in JSON mode)."""
    if not _JSON_MODE:
        click.echo(message, nl=nl)


def emit_json(payload: Any) -> None:
    """Emit a JSON payload to stdout."""
    click.echo(json.dumps(payload, indent=2, default=str))


def emit_result(human_msg: str, json_payload: dict[str, Any]) -> None:
    """Emit either a human message or JSON depending on active mode."""
    if _JSON_MODE:
        emit_json(json_payload)
    else:
        click.echo(human_msg)


def emit_error(message: str, *, code: int = 1) -> NoReturn:
    """Write an error to stderr and exit with non-zero code."""
    click.echo(f"Error: {message}", err=True)
    sys.exit(code)


def cli_main(entry_point: Callable[[], None]) -> None:
    """Run a CLI entry point, ensuring non-zero exit on any failure.

    Catches uncaught exceptions and exits with code 1. Propagates SystemExit
    and KeyboardInterrupt so emit_error() and user interrupt work correctly.
    """
    try:
        entry_point()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


class OutputFormatter:
    """Stateful formatter used inside a single command invocation."""

    def __init__(self, *, json_mode: bool = False) -> None:
        self._json_mode = json_mode
        self._records: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self._records.append(kwargs)
        if not self._json_mode:
            parts = (f"{k}={v}" for k, v in kwargs.items())
            click.echo("  " + "  ".join(parts))

    def flush(self) -> None:
        if self._json_mode:
            emit_json(self._records if len(self._records) != 1 else self._records[0])
        self._records.clear()


def json_output(fn: _F) -> _F:
    """Click command decorator that adds a ``--json`` flag.

    When ``--json`` is supplied the global JSON mode is activated for the
    duration of the command and deactivated on return.
    """

    @click.option("--json", "use_json", is_flag=True, default=False, help="Emit JSON output.")
    @functools.wraps(fn)
    def wrapper(*args: Any, use_json: bool = False, **kwargs: Any) -> Any:
        set_json_mode(use_json)
        try:
            return fn(*args, **kwargs)
        finally:
            set_json_mode(False)

    return wrapper  # type: ignore[return-value]
