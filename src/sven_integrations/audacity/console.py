"""Interactive REPL console for the Audacity harness."""

from __future__ import annotations

from ..shared import Console, Style
from .backend import AudacityBackend, AudacityConnectionError
from .session import AudacitySession
from .core import tracks as track_mod
from .core import selection as sel_mod
from .core import effects as fx_mod
from .core import export as exp_mod


class AudacityConsole(Console):
    """REPL console for driving Audacity via mod-script-pipe."""

    harness_name = "audacity"
    intro_extra = "Controls Audacity via mod-script-pipe IPC."

    def __init__(
        self,
        session: AudacitySession,
        backend: AudacityBackend,
        **kwargs: object,
    ) -> None:
        super().__init__(session_name=session.name, **kwargs)
        self._session = session
        self._backend = backend

    # ------------------------------------------------------------------
    # do_connect

    def do_connect(self, _arg: str) -> None:
        """Connect to the Audacity mod-script-pipe (or report status)."""
        try:
            if not self._backend.is_connected():
                self._backend.connect()
            if self._backend.ping():
                self.success("Connected to Audacity")
            else:
                self.failure("Pipe opened but Audacity did not respond")
        except AudacityConnectionError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_status

    def do_status(self, _arg: str) -> None:
        """Show current session and connection status."""
        self.section("Session")
        for key, val in self._session.status().items():
            self.bullet(f"{key}: {val}")
        self.section("Connection")
        self.bullet(f"connected: {self._backend.is_connected()}")

    # ------------------------------------------------------------------
    # do_track

    def do_track(self, arg: str) -> None:
        """Track commands: new-mono|new-stereo|new-label|delete|up|down|mute|solo|gain|pan.

        Usage: track new-mono <name>
               track delete <index>
               track gain <index> <db>
               track pan <index> <value -1..1>
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: track <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "new-mono":
                name = rest[0] if rest else "Mono Track"
                track_mod.new_mono_track(self._backend, name)
                self.success(f"Created mono track {name!r}")
            elif sub == "new-stereo":
                name = rest[0] if rest else "Stereo Track"
                track_mod.new_stereo_track(self._backend, name)
                self.success(f"Created stereo track {name!r}")
            elif sub == "new-label":
                name = rest[0] if rest else "Labels"
                track_mod.new_label_track(self._backend, name)
                self.success(f"Created label track {name!r}")
            elif sub == "delete":
                idx = int(rest[0])
                track_mod.delete_track(self._backend, idx)
                self.success(f"Deleted track {idx}")
            elif sub == "up":
                track_mod.move_track_up(self._backend, int(rest[0]))
                self.success("Track moved up")
            elif sub == "down":
                track_mod.move_track_down(self._backend, int(rest[0]))
                self.success("Track moved down")
            elif sub == "mute":
                track_mod.mute_track(self._backend, int(rest[0]))
                self.success("Track mute toggled")
            elif sub == "solo":
                track_mod.solo_track(self._backend, int(rest[0]))
                self.success("Track solo toggled")
            elif sub == "gain":
                track_mod.set_gain(self._backend, int(rest[0]), float(rest[1]))
                self.success(f"Gain set to {rest[1]} dB")
            elif sub == "pan":
                track_mod.set_pan(self._backend, int(rest[0]), float(rest[1]))
                self.success(f"Pan set to {rest[1]}")
            else:
                self.failure(f"Unknown track subcommand: {sub!r}")
        except (IndexError, ValueError) as exc:
            self.failure(str(exc))
        except AudacityConnectionError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_select

    def do_select(self, arg: str) -> None:
        """Selection commands: all|none|time|tracks|region|trim|split|zoom.

        Usage: select time <start_s> <end_s>
               select region <start_s> <end_s> <first_track> <last_track>
               select tracks <first> <last>
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: select <subcommand> [args]"))
            return
        sub, *rest = tokens
        try:
            if sub == "all":
                sel_mod.select_all(self._backend)
                self.success("Selected all")
            elif sub == "none":
                sel_mod.select_none(self._backend)
                self.success("Selection cleared")
            elif sub == "time":
                sel_mod.select_time(self._backend, float(rest[0]), float(rest[1]))
                self.success(f"Time range {rest[0]}s – {rest[1]}s selected")
            elif sub == "tracks":
                sel_mod.select_tracks(self._backend, int(rest[0]), int(rest[1]))
                self.success(f"Tracks {rest[0]}–{rest[1]} selected")
            elif sub == "region":
                sel_mod.select_region(
                    self._backend, float(rest[0]), float(rest[1]),
                    int(rest[2]), int(rest[3]),
                )
                self.success("Region selected")
            elif sub == "trim":
                sel_mod.trim_to_selection(self._backend)
                self.success("Trimmed to selection")
            elif sub == "split":
                sel_mod.split_at_selection(self._backend)
                self.success("Split at selection")
            elif sub == "zoom":
                sel_mod.zoom_to_selection(self._backend)
                self.success("Zoomed to selection")
            else:
                self.failure(f"Unknown select subcommand: {sub!r}")
        except (IndexError, ValueError) as exc:
            self.failure(str(exc))
        except AudacityConnectionError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_effect

    def do_effect(self, arg: str) -> None:
        """Effect commands: normalize|amplify|fade-in|fade-out|compress|reverb.

        Usage: effect normalize [-1.0]
               effect amplify <db>
               effect compress <threshold> <noise_floor> <ratio> <attack> <release>
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: effect <name> [params...]"))
            return
        sub, *rest = tokens
        try:
            if sub == "normalize":
                peak = float(rest[0]) if rest else -1.0
                fx_mod.apply_normalize(self._backend, peak)
                self.success("Normalize applied")
            elif sub == "amplify":
                fx_mod.apply_amplify(self._backend, float(rest[0]))
                self.success(f"Amplified by {rest[0]} dB")
            elif sub == "fade-in":
                fx_mod.apply_fade_in(self._backend)
                self.success("Fade-in applied")
            elif sub == "fade-out":
                fx_mod.apply_fade_out(self._backend)
                self.success("Fade-out applied")
            elif sub == "compress":
                args = [float(x) for x in rest]
                fx_mod.apply_compressor(self._backend, *args)
                self.success("Compressor applied")
            elif sub == "reverb":
                args = [float(x) for x in rest]
                fx_mod.apply_reverb(self._backend, *args)
                self.success("Reverb applied")
            else:
                self.failure(f"Unknown effect: {sub!r}")
        except (IndexError, ValueError) as exc:
            self.failure(str(exc))
        except AudacityConnectionError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # do_export

    def do_export(self, arg: str) -> None:
        """Export commands: wav|mp3|flac|ogg|aiff.

        Usage: export wav <path> [bit_depth]
               export mp3 <path> [quality]
               export flac <path> [compression]
        """
        tokens = self.parse_args(arg)
        if not tokens:
            print(Style.warn("  Usage: export <format> <path> [options]"))
            return
        fmt, *rest = tokens
        if not rest:
            self.failure("Output path required")
            return
        path = rest[0]
        try:
            if fmt == "wav":
                depth = int(rest[1]) if len(rest) > 1 else 16
                exp_mod.export_wav(self._backend, path, depth)
            elif fmt == "mp3":
                quality = int(rest[1]) if len(rest) > 1 else 2
                exp_mod.export_mp3(self._backend, path, quality)
            elif fmt == "flac":
                compression = int(rest[1]) if len(rest) > 1 else 5
                exp_mod.export_flac(self._backend, path, compression)
            elif fmt == "ogg":
                quality = float(rest[1]) if len(rest) > 1 else 5.0
                exp_mod.export_ogg(self._backend, path, quality)
            elif fmt == "aiff":
                exp_mod.export_aiff(self._backend, path)
            else:
                self.failure(f"Unknown export format: {fmt!r}")
                return
            self.success(f"Exported {fmt.upper()} → {path}")
        except (IndexError, ValueError) as exc:
            self.failure(str(exc))
        except AudacityConnectionError as exc:
            self.failure(str(exc))
