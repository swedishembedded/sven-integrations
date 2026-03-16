"""Kdenlive interactive REPL console."""

from __future__ import annotations

from ..shared import Console, Style
from .core import effects as eff_mod
from .core import render as render_mod
from .core import timeline as tl_mod
from .project import KdenliveProject, TimelineClip, new_clip_id
from .session import KdenliveSession


class KdenliveConsole(Console):
    """Interactive REPL for the Kdenlive harness."""

    harness_name = "kdenlive"
    intro_extra = "Commands: track  clip  effect  render  status  help  quit"

    def __init__(self, session_name: str = "default", **kwargs: object) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._sess = KdenliveSession.open_or_create(session_name)
        self._proj = self._load_project()

    # ------------------------------------------------------------------
    # Internal helpers

    def _load_project(self) -> KdenliveProject:
        if self._sess.data.get("project"):
            return KdenliveProject.from_dict(self._sess.data["project"])
        return KdenliveProject()

    def _persist(self) -> None:
        self._sess.data["project"] = self._proj.to_dict()
        self._sess.save()

    # ------------------------------------------------------------------
    # track

    def do_track(self, arg: str) -> None:
        """track <add-video|add-audio|remove|mute|lock|list> [args...]

        Examples:
          track add-video Main
          track add-audio Narration
          track remove track_abc123
          track mute track_abc123
          track lock track_abc123
          track list
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_track.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "add-video":
            name = rest[0] if rest else "Video"
            t = tl_mod.add_video_track(self._proj, name)
            self._persist()
            self.success(f"Video track '{name}' added ({t.track_id})")

        elif sub == "add-audio":
            name = rest[0] if rest else "Audio"
            t = tl_mod.add_audio_track(self._proj, name)
            self._persist()
            self.success(f"Audio track '{name}' added ({t.track_id})")

        elif sub == "remove":
            if not rest:
                self.failure("Usage: track remove <track_id>")
                return
            ok = tl_mod.remove_track(self._proj, rest[0])
            self._persist()
            self.success(f"Removed {rest[0]}") if ok else self.failure(f"Not found: {rest[0]}")

        elif sub == "mute":
            if not rest:
                self.failure("Usage: track mute <track_id>")
                return
            tl_mod.mute_track(self._proj, rest[0], True)
            self._persist()
            self.success(f"Muted {rest[0]}")

        elif sub == "lock":
            if not rest:
                self.failure("Usage: track lock <track_id>")
                return
            tl_mod.lock_track(self._proj, rest[0], True)
            self._persist()
            self.success(f"Locked {rest[0]}")

        elif sub == "list":
            self.section("Tracks")
            for t in self._proj.tracks:
                flags = []
                if t.muted:
                    flags.append("muted")
                if t.locked:
                    flags.append("locked")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                self.bullet(f"{t.track_id}  {Style.info(t.kind)}  {t.name}{flag_str}")
        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # clip

    def do_clip(self, arg: str) -> None:
        """clip <add|move|trim|split|remove> [args...]

        Examples:
          clip add <track_id> <bin_id> --pos=0 --out=10
          clip move <clip_id> <new_position>
          clip trim <clip_id> <in> <out>
          clip split <clip_id> <split_pos>
          clip remove <clip_id>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_clip.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "add":
            if len(rest) < 2:
                self.failure("Usage: clip add <track_id> <bin_id> [in] [out] [pos]")
                return
            track_id, bin_id = rest[0], rest[1]
            in_pt = float(rest[2]) if len(rest) > 2 else 0.0
            out_pt = float(rest[3]) if len(rest) > 3 else 10.0
            pos = float(rest[4]) if len(rest) > 4 else 0.0
            clip = TimelineClip(
                clip_id=new_clip_id(),
                bin_id=bin_id,
                in_point=in_pt,
                out_point=out_pt,
                position=pos,
            )
            if self._proj.add_clip(track_id, clip):
                self._persist()
                self.success(f"Clip {clip.clip_id} added to {track_id}")
            else:
                self.failure(f"Track '{track_id}' not found")

        elif sub == "move":
            if len(rest) < 2:
                self.failure("Usage: clip move <clip_id> <position>")
                return
            ok = tl_mod.move_clip(self._proj, rest[0], float(rest[1]))
            self._persist()
            self.success(f"Moved {rest[0]}") if ok else self.failure(f"Clip not found: {rest[0]}")

        elif sub == "trim":
            if len(rest) < 3:
                self.failure("Usage: clip trim <clip_id> <in> <out>")
                return
            ok = tl_mod.trim_clip(self._proj, rest[0], float(rest[1]), float(rest[2]))
            self._persist()
            self.success(f"Trimmed {rest[0]}") if ok else self.failure(f"Clip not found: {rest[0]}")

        elif sub == "split":
            if len(rest) < 2:
                self.failure("Usage: clip split <clip_id> <split_pos>")
                return
            result = tl_mod.split_clip_at(self._proj, rest[0], float(rest[1]))
            self._persist()
            if result:
                left, right = result
                self.success(f"Split into {left.clip_id} and {right.clip_id}")
            else:
                self.failure("Split failed: clip not found or position out of range")

        elif sub == "remove":
            if not rest:
                self.failure("Usage: clip remove <clip_id>")
                return
            ok = tl_mod.remove_clip(self._proj, rest[0])
            self._persist()
            self.success(f"Removed {rest[0]}") if ok else self.failure(f"Not found: {rest[0]}")

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # effect

    def do_effect(self, arg: str) -> None:
        """effect <add|remove|list> [args...]

        Examples:
          effect add <clip_id> brightness level=1.2
          effect list <clip_id>
          effect remove <clip_id> <effect_id>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_effect.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "add":
            if len(rest) < 2:
                self.failure("Usage: effect add <clip_id> <effect_name> [key=val ...]")
                return
            clip_id, eff_name = rest[0], rest[1]
            params: dict[str, str | float | int] = {}
            for p in rest[2:]:
                if "=" in p:
                    k, v_s = p.split("=", 1)
                    try:
                        v: str | float | int = int(v_s) if "." not in v_s else float(v_s)
                    except ValueError:
                        v = v_s
                    params[k] = v
            eff = eff_mod.add_effect(self._proj, clip_id, eff_name, params)
            self._persist()
            self.success(f"Effect '{eff_name}' added ({eff['effect_id']})")

        elif sub == "remove":
            if len(rest) < 2:
                self.failure("Usage: effect remove <clip_id> <effect_id>")
                return
            ok = eff_mod.remove_effect(self._proj, rest[0], rest[1])
            self._persist()
            self.success("Removed") if ok else self.failure("Not found")

        elif sub == "list":
            if not rest:
                self.failure("Usage: effect list <clip_id>")
                return
            effects = eff_mod.list_effects(self._proj, rest[0])
            self.section(f"Effects on {rest[0]}")
            for e in effects:
                self.bullet(f"{e['effect_id']}  {Style.info(e['name'])}  {e['params']}")
            if not effects:
                print(Style.dim("  (none)"))

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # render

    def do_render(self, arg: str) -> None:
        """render <output_path> [profile] [start_s end_s]

        Examples:
          render /tmp/output.mp4
          render /tmp/output.mp4 youtube_720p
          render /tmp/output.mp4 youtube_1080p 0 60
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_render.__doc__)
            return

        output = parts[0]
        profile = parts[1] if len(parts) > 1 else None
        if len(parts) >= 4:
            render_mod.set_render_range(float(parts[2]), float(parts[3]))
        try:
            result = render_mod.render_to_file(output, profile=profile, mlt_path=self._proj.project_path)
            self.success(f"Rendered to {output}  (success={result['success']})")
        except render_mod.RenderError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # status

    def do_status(self, _arg: str) -> None:
        """Show project and session status."""
        self.section("Project")
        self.bullet(f"path:     {self._proj.project_path or '(none)'}")
        self.bullet(f"profile:  {self._proj.profile_name}")
        self.bullet(f"size:     {self._proj.width}×{self._proj.height}")
        self.bullet(f"fps:      {self._proj.fps_num}/{self._proj.fps_den}")
        self.bullet(f"tracks:   {len(self._proj.tracks)}")
        self.bullet(f"duration: {self._proj.duration_seconds:.2f}s")
        self.section("Session")
        self.bullet(f"name: {self._sess.name}")
        self.bullet(f"render profile: {render_mod._active_profile}")
