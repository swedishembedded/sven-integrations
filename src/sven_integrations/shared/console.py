"""Interactive REPL console for sven-integrations harnesses.

Provides a minimal, focused REPL that agents and humans can drive.
Uses Python's stdlib ``cmd.Cmd`` for line dispatch and ``readline``
for history, giving a clean implementation with no external UI
framework dependencies.
"""

from __future__ import annotations

import cmd
import os
import shlex
from pathlib import Path
from typing import Any


class Style:
    """ANSI escape sequences for coloured terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    @classmethod
    def coloured(cls, text: str, *codes: str) -> str:
        if not os.isatty(1):
            return text
        return "".join(codes) + text + cls.RESET

    @classmethod
    def ok(cls, text: str) -> str:
        return cls.coloured(text, cls.GREEN)

    @classmethod
    def warn(cls, text: str) -> str:
        return cls.coloured(text, cls.YELLOW)

    @classmethod
    def err(cls, text: str) -> str:
        return cls.coloured(text, cls.RED, cls.BOLD)

    @classmethod
    def info(cls, text: str) -> str:
        return cls.coloured(text, cls.CYAN)

    @classmethod
    def dim(cls, text: str) -> str:
        return cls.coloured(text, cls.DIM)


class Console(cmd.Cmd):
    """Interactive REPL for a sven-integrations harness.

    Subclass this and implement ``do_<command>`` methods for each
    supported command.  ``harness_name`` and ``session_name`` are used
    to build the prompt and history file path.

    Example::

        class GimpConsole(Console):
            harness_name = "gimp"

            def do_new(self, arg):
                ...
    """

    harness_name: str = "integration"
    intro_extra: str = ""

    def __init__(self, session_name: str = "default", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.session_name = session_name
        self.prompt = self._build_prompt()
        self._setup_history()
        self.intro = self._build_intro()

    def _build_prompt(self) -> str:
        harness = Style.coloured(self.harness_name, Style.CYAN, Style.BOLD)
        session = Style.dim(f"[{self.session_name}]")
        arrow = Style.coloured("› ", Style.BLUE, Style.BOLD)
        return f"{harness} {session} {arrow}"

    def _build_intro(self) -> str:
        lines = [
            Style.coloured(
                f"  sven / {self.harness_name} integration  ",
                Style.BOLD,
                Style.BLUE,
            ),
            Style.dim("  Type 'help' for available commands, 'quit' to exit."),
        ]
        if self.intro_extra:
            lines.append(Style.dim(f"  {self.intro_extra}"))
        return "\n".join(lines) + "\n"

    def _setup_history(self) -> None:
        try:
            import readline  # noqa: PLC0415

            history_dir = Path.home() / ".local" / "share" / "sven-integrations"
            history_dir.mkdir(parents=True, exist_ok=True)
            history_file = history_dir / f"{self.harness_name}.history"
            if history_file.exists():
                readline.read_history_file(str(history_file))
            readline.set_history_length(2000)
            import atexit  # noqa: PLC0415

            atexit.register(readline.write_history_file, str(history_file))
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Built-in commands

    def do_quit(self, _arg: str) -> bool:
        print(Style.dim("  Goodbye."))
        return True

    do_exit = do_quit
    do_q = do_quit

    def do_EOF(self, _arg: str) -> bool:  # noqa: N802
        print()
        return self.do_quit(_arg)

    def emptyline(self) -> None:
        pass

    def default(self, line: str) -> None:
        cmd_name = shlex.split(line)[0] if line.strip() else line
        print(Style.err(f"  Unknown command: {cmd_name!r}  (try 'help')"))

    def cmdloop(self, intro: str | None = None) -> None:  # type: ignore[override]
        try:
            super().cmdloop(intro)
        except KeyboardInterrupt:
            print()
            print(Style.dim("  Interrupted."))

    # ------------------------------------------------------------------
    # Utility helpers for subclasses

    @staticmethod
    def parse_args(arg: str) -> list[str]:
        """Split a raw argument string into tokens respecting quotes."""
        try:
            return shlex.split(arg)
        except ValueError:
            return arg.split()

    @staticmethod
    def require_arg(arg: str, name: str = "argument") -> str:
        """Return *arg* stripped, or print an error and return empty str."""
        value = arg.strip()
        if not value:
            print(Style.err(f"  Missing required {name}."))
        return value

    def section(self, title: str) -> None:
        print(Style.info(f"\n  {title}"))

    def bullet(self, text: str) -> None:
        print(Style.dim("    · ") + text)

    def success(self, text: str) -> None:
        print(Style.ok(f"  ✓ {text}"))

    def failure(self, text: str) -> None:
        print(Style.err(f"  ✗ {text}"))
