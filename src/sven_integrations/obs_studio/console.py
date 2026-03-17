"""Interactive REPL console for the OBS Studio harness."""

from __future__ import annotations

from ..shared import Console, Style
from .backend import ObsBackend, ObsConnectionError, ObsRequestError
from .core import recording as rec_mod
from .core import scenes as scene_mod
from .core import sources as src_mod
from .session import ObsSession


class ObsConsole(Console):
    """REPL console for driving OBS Studio via WebSocket."""

    harness_name = "obs"
    intro_extra = "Controls OBS Studio via obs-websocket."

    def __init__(
        self,
        session: ObsSession,
        backend: ObsBackend,
        **kwargs: object,
    ) -> None:
        super().__init__(session_name=session.name, **kwargs)
        self._session = session
        self._backend = backend

    # ------------------------------------------------------------------
    # do_connect

    def do_connect(self, arg: str) -> None:
        """Connect to OBS WebSocket.

        Usage: connect [host] [port] [password]
        """
        tokens = self.parse_args(arg)
        host = tokens[0] if len(tokens) > 0 else "localhost"
        port = int(tokens[1]) if len(tokens) > 1 else 4455
        password = tokens[2] if len(tokens) > 2 else ""
        try:
            if not self._backend.is_connected():
                self._backend.connect(host, port, password)
            self._session.set_connection(host, port, password)
            self._session.save()
            version = self._backend.get_version()
            self.success(f"Connected to OBS {version} at {host}:{port}")
        except ObsConnectionError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_status

    def do_status(self, _arg: str) -> None:
        """Show current session and connection status."""
        self.section("Session")
        for key, val in self._session.status().items():
            self.bullet(f"{key}: {val}")
        self.section("WebSocket")
        self.bullet(f"connected: {self._backend.is_connected()}")

    # ------------------------------------------------------------------
    # do_scene

    def do_scene(self, arg: str) -> None:
        """Scene commands: list|switch|create|remove|current.

        Usage: scene list
               scene switch <name>
               scene create <name>
               scene remove <name>
               scene current
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: scene <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "list":
                names = scene_mod.list_scenes(self._backend)
                self.section("Scenes")
                for n in names:
                    self.bullet(n)
            elif sub == "switch":
                name = " ".join(rest)
                scene_mod.switch_scene(self._backend, name)
                self.success(f"Switched to scene {name!r}")
            elif sub == "create":
                name = " ".join(rest)
                scene_mod.create_scene(self._backend, name)
                self.success(f"Scene {name!r} created")
            elif sub == "remove":
                name = " ".join(rest)
                scene_mod.remove_scene(self._backend, name)
                self.success(f"Scene {name!r} removed")
            elif sub == "current":
                name = scene_mod.get_current_scene(self._backend)
                self.success(f"Current scene: {name!r}")
            else:
                self.failure(f"Unknown scene subcommand: {sub!r}")
        except (ObsConnectionError, ObsRequestError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_source

    def do_source(self, arg: str) -> None:
        """Source commands: list|add|remove|volume|mute|unmute|visible.

        Usage: source list <scene>
               source add <scene> <name> <kind>
               source volume <name> <db>
               source mute <name>
               source visible <scene> <name> on|off
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: source <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "list":
                items = src_mod.list_sources(self._backend, rest[0])
                self.section(f"Sources in {rest[0]!r}")
                for item in items:
                    self.bullet(f"{item.get('sourceName')} ({item.get('inputKind', '?')})")
            elif sub == "add":
                src_mod.add_source(self._backend, rest[0], rest[1], rest[2])
                self.success(f"Source {rest[1]!r} added to {rest[0]!r}")
            elif sub == "remove":
                src_mod.remove_source(self._backend, rest[0], rest[1])
                self.success(f"Source {rest[1]!r} removed from {rest[0]!r}")
            elif sub == "volume":
                src_mod.set_source_volume(self._backend, rest[0], float(rest[1]))
                self.success(f"Volume of {rest[0]!r} set to {rest[1]} dB")
            elif sub == "mute":
                src_mod.mute_source(self._backend, rest[0])
                self.success(f"Source {rest[0]!r} muted")
            elif sub == "unmute":
                src_mod.unmute_source(self._backend, rest[0])
                self.success(f"Source {rest[0]!r} unmuted")
            elif sub == "visible":
                flag = rest[2].lower() in ("on", "true", "1", "yes")
                src_mod.set_source_visible(self._backend, rest[0], rest[1], flag)
                state = "visible" if flag else "hidden"
                self.success(f"Source {rest[1]!r} {state}")
            else:
                self.failure(f"Unknown source subcommand: {sub!r}")
        except (ObsConnectionError, ObsRequestError, IndexError, ValueError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_record

    def do_record(self, arg: str) -> None:
        """Recording commands: start|stop|status|toggle.

        Usage: record start
               record stop
               record status
        """
        tokens = self.parse_args(arg)
        sub = tokens[0] if tokens else ""
        try:
            if sub == "start":
                rec_mod.start_recording(self._backend)
                self.success("Recording started")
            elif sub == "stop":
                info = rec_mod.stop_recording(self._backend)
                self.success(f"Recording stopped: {info}")
            elif sub == "toggle":
                rec_mod.toggle_recording(self._backend)
                self.success("Recording toggled")
            elif sub == "status":
                info = rec_mod.get_recording_status(self._backend)
                self.section("Recording status")
                for k, v in info.items():
                    self.bullet(f"{k}: {v}")
            else:
                self.failure(f"Unknown record subcommand: {sub!r}")
        except (ObsConnectionError, ObsRequestError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_stream

    def do_stream(self, arg: str) -> None:
        """Streaming commands: start|stop|status.

        Usage: stream start
               stream stop
               stream status
        """
        tokens = self.parse_args(arg)
        sub = tokens[0] if tokens else ""
        try:
            if sub == "start":
                rec_mod.start_streaming(self._backend)
                self.success("Stream started")
            elif sub == "stop":
                info = rec_mod.stop_streaming(self._backend)
                self.success(f"Stream stopped: {info}")
            elif sub == "status":
                info = rec_mod.get_streaming_status(self._backend)
                self.section("Streaming status")
                for k, v in info.items():
                    self.bullet(f"{k}: {v}")
            else:
                self.failure(f"Unknown stream subcommand: {sub!r}")
        except (ObsConnectionError, ObsRequestError) as exc:
            self.failure(str(exc))
