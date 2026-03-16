"""Interactive REPL console for the Blender harness."""

from __future__ import annotations

from typing import Any

from ..shared import Console, Style
from .backend import BlenderBackend, BlenderError
from .core import materials as mat_ops
from .core import objects as obj_ops
from .core import render as render_ops
from .core import scene as scene_ops
from .session import BlenderSession


class BlenderConsole(Console):
    """REPL for the Blender integration harness."""

    harness_name = "blender"
    intro_extra = "Commands: object  material  scene  render  status"

    def __init__(self, session_name: str = "default") -> None:
        super().__init__(session_name=session_name)
        self._session = BlenderSession.open_or_create(session_name)
        self._backend = BlenderBackend()

    # ------------------------------------------------------------------
    # object

    def do_object(self, arg: str) -> None:
        """object <subcommand> [args]

        Subcommands:
          add <type> [x y z]    — add a mesh (CUBE/SPHERE/PLANE/...)
          delete <name>         — delete by name
          list                  — list scene objects from session
          move <name> <x> <y> <z>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_object.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "add":
                mesh_type = parts[1].upper() if len(parts) > 1 else "CUBE"
                loc: tuple[float, float, float] = (
                    float(parts[2]) if len(parts) > 2 else 0.0,
                    float(parts[3]) if len(parts) > 3 else 0.0,
                    float(parts[4]) if len(parts) > 4 else 0.0,
                )
                result = obj_ops.add_mesh(mesh_type, loc)
                self.success(f"Add {mesh_type} at {loc} — {len(result['statements'])} statements")
            elif sub == "delete":
                if len(parts) < 2:
                    self.failure("Usage: object delete <name>")
                    return
                result = obj_ops.delete_object(parts[1])
                self.success(f"Delete '{parts[1]}' — script ready.")
            elif sub == "list":
                proj = self._session.project
                if proj is None or not proj.objects:
                    self.bullet("(no objects in session)")
                    return
                self.section("Scene objects")
                for obj in proj.objects:
                    self.bullet(
                        f"[{obj.type}] {obj.name}  @ {obj.location}  mat={obj.material or '—'}"
                    )
            elif sub == "move":
                if len(parts) < 5:
                    self.failure("Usage: object move <name> <x> <y> <z>")
                    return
                name = parts[1]
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                stmts = [
                    "import bpy",
                    f'obj = bpy.data.objects.get("{name}")',
                    f"if obj: obj.location = ({x}, {y}, {z})",
                ]
                self.success(f"Move '{name}' to ({x}, {y}, {z}) — script ready.")
            else:
                self.failure(f"Unknown object subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # material

    def do_material(self, arg: str) -> None:
        """material <subcommand> [args]

        Subcommands:
          create <name> [r g b a]
          assign <object> <material>
          metallic <mat_name> <value>
          roughness <mat_name> <value>
          list
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_material.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "create":
                if len(parts) < 2:
                    self.failure("Usage: material create <name> [r g b a]")
                    return
                name = parts[1]
                color: tuple[float, float, float, float] = (
                    float(parts[2]) if len(parts) > 2 else 0.8,
                    float(parts[3]) if len(parts) > 3 else 0.8,
                    float(parts[4]) if len(parts) > 4 else 0.8,
                    float(parts[5]) if len(parts) > 5 else 1.0,
                )
                mat_ops.create_material(name, color)
                self.success(f"Material '{name}' script ready.")
            elif sub == "assign":
                if len(parts) < 3:
                    self.failure("Usage: material assign <object> <material>")
                    return
                mat_ops.assign_material(parts[1], parts[2])
                self.success(f"Assign '{parts[2]}' → '{parts[1]}' script ready.")
            elif sub == "metallic":
                if len(parts) < 3:
                    self.failure("Usage: material metallic <name> <value>")
                    return
                mat_ops.set_metallic(parts[1], float(parts[2]))
                self.success(f"Metallic set on '{parts[1]}'.")
            elif sub == "roughness":
                if len(parts) < 3:
                    self.failure("Usage: material roughness <name> <value>")
                    return
                mat_ops.set_roughness(parts[1], float(parts[2]))
                self.success(f"Roughness set on '{parts[1]}'.")
            elif sub == "list":
                result = mat_ops.list_materials()
                self.success("List-materials script ready.")
                self.bullet(f"statements: {len(result['statements'])}")
            else:
                self.failure(f"Unknown material subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # scene

    def do_scene(self, arg: str) -> None:
        """scene <subcommand> [args]

        Subcommands:
          info               — show scene info
          frame-range <s> <e>
          fps <value>
          camera <name>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_scene.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "info":
                proj = self._session.project
                if proj is None:
                    self.failure("No project in session.")
                    return
                self.section("Scene")
                self.bullet(f"name       : {proj.scene_name}")
                self.bullet(f"blend_file : {proj.blend_file or '(none)'}")
                self.bullet(f"frames     : {proj.frame_start}–{proj.frame_end} @ {proj.fps} fps")
                self.bullet(f"objects    : {len(proj.objects)}")
            elif sub == "frame-range":
                if len(parts) < 3:
                    self.failure("Usage: scene frame-range <start> <end>")
                    return
                scene_ops.set_frame_range(int(parts[1]), int(parts[2]))
                self.success(f"Frame range set to {parts[1]}–{parts[2]}.")
            elif sub == "fps":
                fps = int(parts[1]) if len(parts) > 1 else 24
                scene_ops.set_fps(fps)
                self.success(f"FPS set to {fps}.")
            elif sub == "camera":
                if len(parts) < 2:
                    self.failure("Usage: scene camera <name>")
                    return
                scene_ops.set_active_camera(parts[1])
                self.success(f"Camera set to '{parts[1]}'.")
            else:
                self.failure(f"Unknown scene subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # render

    def do_render(self, arg: str) -> None:
        """render <subcommand> [args]

        Subcommands:
          engine <CYCLES|EEVEE|WORKBENCH>
          resolution <w> <h> [%]
          format <PNG|JPEG|EXR|MP4>
          samples <count>
          output <path>
          denoise <on|off>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_render.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "engine":
                eng = parts[1].upper() if len(parts) > 1 else "CYCLES"
                result = render_ops.set_render_engine(eng)
                self.success(f"Render engine → {result['engine']}")
            elif sub == "resolution":
                if len(parts) < 3:
                    self.failure("Usage: render resolution <w> <h> [pct]")
                    return
                w, h = int(parts[1]), int(parts[2])
                pct = int(parts[3]) if len(parts) > 3 else 100
                render_ops.set_output_resolution(w, h, pct)
                self.success(f"Resolution → {w}×{h} @ {pct}%")
            elif sub == "format":
                fmt = parts[1] if len(parts) > 1 else "PNG"
                result = render_ops.set_output_format(fmt)
                self.success(f"Format → {result['format']}")
            elif sub == "samples":
                n = int(parts[1]) if len(parts) > 1 else 128
                render_ops.set_samples(n)
                self.success(f"Samples → {n}")
            elif sub == "output":
                path = parts[1] if len(parts) > 1 else "/tmp/render"
                render_ops.set_output_path(path)
                self.success(f"Output path → {path}")
            elif sub == "denoise":
                flag = (parts[1].lower() != "off") if len(parts) > 1 else True
                render_ops.enable_denoising(flag)
                self.success(f"Denoising {'on' if flag else 'off'}")
            else:
                self.failure(f"Unknown render subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # status

    def do_status(self, _arg: str) -> None:
        """Print a summary of the current Blender session."""
        self.section("Blender session status")
        self.bullet(f"session : {self._session.name}")
        proj = self._session.project
        if proj is None:
            self.bullet("project : (none)")
        else:
            self.bullet(f"scene   : {proj.scene_name}")
            self.bullet(f"file    : {proj.blend_file or '(unsaved)'}")
            self.bullet(f"frames  : {proj.frame_start}–{proj.frame_end} @ {proj.fps} fps")
            self.bullet(f"objects : {len(proj.objects)}")
