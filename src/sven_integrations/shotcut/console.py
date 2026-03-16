"""Shotcut interactive REPL console."""

from __future__ import annotations

from ..shared import Console, Style
from .backend import ShotcutBackend, ShotcutError
from .project import MltClip, MltTrack, ShotcutProject, new_clip_id, new_track_id
from .session import ShotcutSession


class ShotcutConsole(Console):
    """Interactive REPL for the Shotcut harness."""

    harness_name = "shotcut"
    intro_extra = "Commands: track  clip  filter  render  preview  status  help  quit"

    def __init__(self, session_name: str = "default", **kwargs: object) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._sess = ShotcutSession.open_or_create(session_name)
        self._proj = self._load_project()
        self._backend = ShotcutBackend()

    # ------------------------------------------------------------------
    # Internal helpers

    def _load_project(self) -> ShotcutProject:
        if self._sess.data.get("project"):
            return ShotcutProject.from_dict(self._sess.data["project"])
        return ShotcutProject()

    def _persist(self) -> None:
        self._sess.data["project"] = self._proj.to_dict()
        self._sess.save()

    # ------------------------------------------------------------------
    # track

    def do_track(self, arg: str) -> None:
        """track <add|remove|list|mute> [args...]

        Examples:
          track add Main
          track remove track_abc123
          track mute track_abc123
          track list
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_track.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "add":
            name = rest[0] if rest else "Track"
            track = MltTrack(track_id=new_track_id(), name=name)
            self._proj.add_track(track)
            self._persist()
            self.success(f"Track '{name}' added ({track.track_id})")

        elif sub == "remove":
            if not rest:
                self.failure("Usage: track remove <track_id>")
                return
            ok = self._proj.remove_track(rest[0])
            self._persist()
            self.success(f"Removed {rest[0]}") if ok else self.failure(f"Not found: {rest[0]}")

        elif sub == "list":
            self.section("Tracks")
            for t in self._proj.tracks:
                hide_label = {0: "visible", 1: "no-video", 2: "no-audio"}.get(t.hide, str(t.hide))
                self.bullet(f"{t.track_id}  {Style.info(hide_label)}  {t.name}")

        elif sub == "mute":
            if not rest:
                self.failure("Usage: track mute <track_id>")
                return
            for t in self._proj.tracks:
                if t.track_id == rest[0]:
                    t.hide = 1
                    self._persist()
                    self.success(f"Track {rest[0]} hidden (video)")
                    return
            self.failure(f"Track not found: {rest[0]}")

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # clip

    def do_clip(self, arg: str) -> None:
        """clip <add|remove|trim|move> [args...]

        Examples:
          clip add <track_id> <resource> [in] [out] [pos]
          clip remove <clip_id>
          clip trim <clip_id> <in_frames> <out_frames>
          clip move <clip_id> <position_frames>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_clip.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "add":
            if len(rest) < 2:
                self.failure("Usage: clip add <track_id> <resource> [in] [out] [pos]")
                return
            track_id, resource = rest[0], rest[1]
            in_f = int(rest[2]) if len(rest) > 2 else 0
            out_f = int(rest[3]) if len(rest) > 3 else 250
            pos = int(rest[4]) if len(rest) > 4 else 0
            clip = MltClip(
                clip_id=new_clip_id(),
                resource=resource,
                in_point=in_f,
                out_point=out_f,
                position=pos,
            )
            ok = self._proj.add_clip_to_track(track_id, clip)
            self._persist()
            self.success(f"Clip {clip.clip_id} added") if ok else self.failure(f"Track not found: {track_id}")

        elif sub == "remove":
            if not rest:
                self.failure("Usage: clip remove <clip_id>")
                return
            for track in self._proj.tracks:
                for i, c in enumerate(track.clips):
                    if c.clip_id == rest[0]:
                        del track.clips[i]
                        self._persist()
                        self.success(f"Removed {rest[0]}")
                        return
            self.failure(f"Clip not found: {rest[0]}")

        elif sub == "trim":
            if len(rest) < 3:
                self.failure("Usage: clip trim <clip_id> <in_frames> <out_frames>")
                return
            clip = self._proj.find_clip(rest[0])
            if clip is None:
                self.failure(f"Clip not found: {rest[0]}")
                return
            clip.in_point = int(rest[1])
            clip.out_point = int(rest[2])
            self._persist()
            self.success(f"Trimmed {rest[0]}: {rest[1]}–{rest[2]} frames")

        elif sub == "move":
            if len(rest) < 2:
                self.failure("Usage: clip move <clip_id> <position_frames>")
                return
            clip = self._proj.find_clip(rest[0])
            if clip is None:
                self.failure(f"Clip not found: {rest[0]}")
                return
            clip.position = int(rest[1])
            self._persist()
            self.success(f"Moved {rest[0]} to frame {rest[1]}")

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # filter

    def do_filter(self, arg: str) -> None:
        """filter <add|remove|list> [args...]

        Examples:
          filter add <clip_id> brightness
          filter list <clip_id>
          filter remove <clip_id> brightness
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_filter.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "add":
            if len(rest) < 2:
                self.failure("Usage: filter add <clip_id> <filter_name>")
                return
            clip = self._proj.find_clip(rest[0])
            if clip is None:
                self.failure(f"Clip not found: {rest[0]}")
                return
            clip.filters.append(rest[1])
            self._persist()
            self.success(f"Filter '{rest[1]}' added to {rest[0]}")

        elif sub == "remove":
            if len(rest) < 2:
                self.failure("Usage: filter remove <clip_id> <filter_name>")
                return
            clip = self._proj.find_clip(rest[0])
            if clip is None:
                self.failure(f"Clip not found: {rest[0]}")
                return
            try:
                clip.filters.remove(rest[1])
                self._persist()
                self.success(f"Removed '{rest[1]}'")
            except ValueError:
                self.failure(f"Filter '{rest[1]}' not found")

        elif sub == "list":
            if not rest:
                self.failure("Usage: filter list <clip_id>")
                return
            clip = self._proj.find_clip(rest[0])
            if clip is None:
                self.failure(f"Clip not found: {rest[0]}")
                return
            self.section(f"Filters on {rest[0]}")
            for f in clip.filters:
                self.bullet(f)
            if not clip.filters:
                print(Style.dim("  (none)"))

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # render

    def do_render(self, arg: str) -> None:
        """render <output_path> [preset]

        Examples:
          render /tmp/output.mp4
          render /tmp/output.mp4 vimeo
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_render.__doc__)
            return
        output = parts[0]
        if not self._proj.mlt_path:
            self.failure("No MLT file loaded; use 'open <path>' first.")
            return
        try:
            self._backend.render_mlt(self._proj.mlt_path, output, profile=self._proj.profile_name)
            self.success(f"Rendered to {output}")
        except ShotcutError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # preview

    def do_preview(self, arg: str) -> None:
        """preview <frame_num> <output_png>

        Example:
          preview 100 /tmp/frame100.png
        """
        parts = self.parse_args(arg)
        if len(parts) < 2:
            print(self.do_preview.__doc__)
            return
        if not self._proj.mlt_path:
            self.failure("No MLT file loaded.")
            return
        try:
            self._backend.preview_frame(self._proj.mlt_path, int(parts[0]), parts[1])
            self.success(f"Frame {parts[0]} → {parts[1]}")
        except ShotcutError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # status

    def do_status(self, _arg: str) -> None:
        """Show project and session status."""
        self.section("Project")
        self.bullet(f"path:      {self._proj.mlt_path or '(none)'}")
        self.bullet(f"profile:   {self._proj.profile_name}")
        self.bullet(f"size:      {self._proj.width}×{self._proj.height}")
        self.bullet(f"fps:       {self._proj.fps}")
        self.bullet(f"tracks:    {len(self._proj.tracks)}")
        self.bullet(f"duration:  {self._proj.timeline_duration_frames} frames")
        self.section("Session")
        self.bullet(f"name: {self._sess.name}")
