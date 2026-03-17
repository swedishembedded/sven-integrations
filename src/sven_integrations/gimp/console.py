"""Interactive REPL console for the GIMP harness.

Provides a text-mode shell that an AI agent (or a human) can use to control
a GIMP session without typing full CLI invocations.  Each ``do_*`` method
maps to one logical domain: layers, filters, canvas, export, undo/redo.
"""

from __future__ import annotations

from typing import Any

from ..shared import Console
from .backend import GimpBackend
from .core import canvas as canvas_ops
from .core import export as export_ops
from .core import filters as filter_ops
from .core import layers as layer_ops
from .session import GimpSession


class GimpConsole(Console):
    """REPL for the GIMP integration harness."""

    harness_name = "gimp"
    intro_extra = "Commands: layer  filter  canvas  export  undo  redo  history  status"

    def __init__(self, session_name: str = "default") -> None:
        super().__init__(session_name=session_name)
        self._session = GimpSession.open_or_create(session_name)
        self._backend = GimpBackend()
        self._undo_stack: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # layer

    def do_layer(self, arg: str) -> None:
        """layer <subcommand> [args]

        Subcommands:
          add <name> <width> <height>   — create a new RGBA layer
          remove <layer_id>             — remove a layer by numeric ID
          list                          — show all layers in the project
          opacity <layer_id> <0.0-1.0>  — set layer opacity
          move <layer_id> <x> <y>       — reposition a layer
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_layer.__doc__)
            return
        sub = parts[0]

        proj = self._session.project
        if proj is None and sub not in ("list",):
            self.failure("No project open.  Use the CLI 'new' command first.")
            return

        if sub == "add":
            if len(parts) < 4:
                self.failure("Usage: layer add <name> <width> <height>")
                return
            name, w, h = parts[1], int(parts[2]), int(parts[3])
            result = layer_ops.create_layer(name, w, h)
            self.success(f"Layer '{name}' created ({w}×{h})")
            self.bullet(f"script: {result['script'][:60]}…")
        elif sub == "remove":
            if len(parts) < 2:
                self.failure("Usage: layer remove <layer_id>")
                return
            lid = int(parts[1])
            if proj and proj.remove_layer(lid):
                self._session.project = proj
                self._session.save()
                self.success(f"Layer {lid} removed.")
            else:
                self.failure(f"Layer {lid} not found.")
        elif sub == "list":
            if proj is None or not proj.layers:
                self.bullet("(no layers)")
            else:
                self.section("Layers")
                for lyr in proj.layers:
                    marker = "▸" if proj.active_layer and lyr.id == proj.active_layer.id else " "
                    vis = "✓" if lyr.visible else "✗"
                    self.bullet(
                        f"{marker} [{lyr.id}] {lyr.name}  opacity={lyr.opacity:.0%}  "
                        f"visible={vis}  mode={lyr.blend_mode}"
                    )
        elif sub == "opacity":
            if len(parts) < 3:
                self.failure("Usage: layer opacity <layer_id> <value>")
                return
            lid, val = int(parts[1]), float(parts[2])
            result = layer_ops.set_layer_opacity(lid, val)
            self.success(f"Layer {lid} opacity → {val:.0%}")
        elif sub == "move":
            if len(parts) < 4:
                self.failure("Usage: layer move <layer_id> <x> <y>")
                return
            lid, x, y = int(parts[1]), int(parts[2]), int(parts[3])
            result = layer_ops.move_layer(lid, x, y)
            self.success(f"Layer {lid} moved to ({x}, {y})")
        else:
            self.failure(f"Unknown layer subcommand: {sub!r}")

    # ------------------------------------------------------------------
    # filter

    def do_filter(self, arg: str) -> None:
        """filter <subcommand> [args]

        Subcommands:
          blur <radius>
          sharpen <amount>
          unsharp <radius> <amount> <threshold>
          levels <in_lo> <in_hi> <gamma> <out_lo> <out_hi>
          huesat <hue> <saturation> <lightness>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_filter.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "blur":
                r = float(parts[1]) if len(parts) > 1 else 2.0
                filter_ops.apply_blur(r)
                self.success(f"Blur applied (radius={r})")
            elif sub == "sharpen":
                amt = float(parts[1]) if len(parts) > 1 else 50.0
                filter_ops.apply_sharpen(amt)
                self.success(f"Sharpen applied (amount={amt})")
            elif sub == "unsharp":
                r = float(parts[1]) if len(parts) > 1 else 5.0
                a = float(parts[2]) if len(parts) > 2 else 0.5
                t = int(parts[3]) if len(parts) > 3 else 0
                filter_ops.apply_unsharp_mask(r, a, t)
                self.success(f"Unsharp mask applied (r={r}, a={a}, t={t})")
            elif sub == "levels":
                if len(parts) < 6:
                    self.failure("Usage: filter levels <in_lo> <in_hi> <gamma> <out_lo> <out_hi>")
                    return
                filter_ops.apply_levels(
                    (int(parts[1]), int(parts[2]), float(parts[3])),
                    (int(parts[4]), int(parts[5])),
                )
                self.success("Levels adjusted.")
            elif sub == "huesat":
                hue = float(parts[1]) if len(parts) > 1 else 0.0
                sat = float(parts[2]) if len(parts) > 2 else 0.0
                lit = float(parts[3]) if len(parts) > 3 else 0.0
                filter_ops.apply_hue_saturation(hue, sat, lit)
                self.success(f"Hue/Sat adjusted (h={hue}, s={sat}, l={lit})")
            else:
                self.failure(f"Unknown filter subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # canvas

    def do_canvas(self, arg: str) -> None:
        """canvas <subcommand> [args]

        Subcommands:
          crop <x> <y> <w> <h>
          resize <w> <h> [offset_x] [offset_y]
          scale <w> <h>
          rotate <angle_deg>
          flip <h|v>
          dpi <value>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_canvas.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "crop":
                x, y, w, h = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                canvas_ops.crop(x, y, w, h)
                self.success(f"Cropped to {w}×{h} at ({x},{y})")
            elif sub == "resize":
                w, h = int(parts[1]), int(parts[2])
                ox = int(parts[3]) if len(parts) > 3 else 0
                oy = int(parts[4]) if len(parts) > 4 else 0
                canvas_ops.resize_canvas(w, h, ox, oy)
                self.success(f"Canvas resized to {w}×{h}")
            elif sub == "scale":
                w, h = int(parts[1]), int(parts[2])
                canvas_ops.scale_image(w, h)
                self.success(f"Image scaled to {w}×{h}")
            elif sub == "rotate":
                angle = float(parts[1]) if len(parts) > 1 else 90.0
                canvas_ops.rotate(angle)
                self.success(f"Rotated {angle}°")
            elif sub == "flip":
                direction = parts[1] if len(parts) > 1 else "h"
                canvas_ops.flip(direction)  # type: ignore[arg-type]
                self.success(f"Flipped {'horizontally' if direction == 'h' else 'vertically'}")
            elif sub == "dpi":
                dpi = float(parts[1]) if len(parts) > 1 else 72.0
                canvas_ops.set_resolution(dpi)
                self.success(f"Resolution set to {dpi} DPI")
            else:
                self.failure(f"Unknown canvas subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # export

    def do_export(self, arg: str) -> None:
        """export <path> [--format <fmt>] [--quality <n>]

        Supported formats: png  jpeg  tiff  webp  pdf
        """
        parts = self.parse_args(arg)
        if not parts:
            self.failure("Usage: export <path> [--format <fmt>]")
            return
        path = parts[0]
        fmt = "png"
        quality = 90
        i = 1
        while i < len(parts):
            if parts[i] in ("--format", "-f") and i + 1 < len(parts):
                fmt = parts[i + 1]
                i += 2
            elif parts[i] in ("--quality", "-q") and i + 1 < len(parts):
                quality = int(parts[i + 1])
                i += 2
            else:
                i += 1
        try:
            fn_map = {
                "png": lambda p: export_ops.export_png(p),
                "jpeg": lambda p: export_ops.export_jpeg(p, quality),
                "jpg": lambda p: export_ops.export_jpeg(p, quality),
                "tiff": lambda p: export_ops.export_tiff(p),
                "webp": lambda p: export_ops.export_webp(p, quality),
                "pdf": lambda p: export_ops.export_pdf(p),
            }
            handler = fn_map.get(fmt.lower())
            if handler is None:
                self.failure(f"Unknown format: {fmt!r}")
                return
            handler(path)
            self.success(f"Export command built for {fmt.upper()} → {path}")
        except export_ops.ExportError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # undo / redo / history / status

    def do_undo(self, _arg: str) -> None:
        """Undo the last recorded operation."""
        if self._undo_stack:
            op = self._undo_stack.pop()
            self.success(f"Undone: {op.get('action', '?')}")
        else:
            self.bullet("Nothing to undo.")

    def do_redo(self, _arg: str) -> None:
        """Redo — not supported in Script-Fu batch mode."""
        self.bullet("Redo is not available in Script-Fu batch mode.")

    def do_history(self, _arg: str) -> None:
        """Show the operation history for the current project."""
        proj = self._session.project
        if proj is None:
            self.failure("No project open.")
            return
        if not proj.history:
            self.bullet("(history is empty)")
            return
        self.section("Operation history")
        for i, entry in enumerate(proj.history, 1):
            self.bullet(f"{i:3d}. {entry}")

    def do_status(self, _arg: str) -> None:
        """Print a summary of the current session and project."""
        self.section("GIMP session status")
        self.bullet(f"session : {self._session.name}")
        proj = self._session.project
        if proj is None:
            self.bullet("project : (none)")
        else:
            self.bullet(f"project : {proj.width}×{proj.height}  {proj.color_mode}  {proj.dpi} DPI")
            self.bullet(f"layers  : {len(proj.layers)}")
            active = proj.active_layer
            if active:
                self.bullet(f"active  : [{active.id}] {active.name}")
