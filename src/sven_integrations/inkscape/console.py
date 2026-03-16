"""Interactive REPL console for the Inkscape harness."""

from __future__ import annotations

from ..shared import Console, Style
from .backend import InkscapeBackend, InkscapeError
from .core import elements as elem_ops
from .core import export as export_ops
from .core import text as text_ops
from .session import InkscapeSession


class InkscapeConsole(Console):
    """REPL for the Inkscape integration harness."""

    harness_name = "inkscape"
    intro_extra = "Commands: element  text  export  status"

    def __init__(self, session_name: str = "default") -> None:
        super().__init__(session_name=session_name)
        self._session = InkscapeSession.open_or_create(session_name)
        self._backend = InkscapeBackend()

    def _svg_path(self) -> str | None:
        """Return the SVG path from the session project, if any."""
        proj = self._session.project
        return proj.svg_path if proj else None

    # ------------------------------------------------------------------
    # element

    def do_element(self, arg: str) -> None:
        """element <subcommand> [args]

        Subcommands:
          list                            — list tracked elements
          move <id> <dx> <dy>
          scale <id> <sx> <sy>
          rotate <id> <angle> [cx cy]
          fill <id> <color>
          stroke <id> <color> [width]
          delete <id>
          duplicate <id>
          group <id1> <id2> ... --group-id <gid>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_element.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "list":
                proj = self._session.project
                if proj is None or not proj.elements:
                    self.bullet("(no elements tracked)")
                    return
                self.section("SVG elements")
                for elem in proj.elements:
                    self.bullet(
                        f"[{elem.tag}] #{elem.element_id}  fill={elem.fill}  "
                        f"stroke={elem.stroke}  label={elem.label or '—'}"
                    )
            elif sub == "move":
                if len(parts) < 4:
                    self.failure("Usage: element move <id> <dx> <dy>")
                    return
                result = elem_ops.move_element(parts[1], float(parts[2]), float(parts[3]))
                self.success(f"Move '{parts[1]}' by ({parts[2]}, {parts[3]}) — actions built.")
            elif sub == "scale":
                if len(parts) < 4:
                    self.failure("Usage: element scale <id> <sx> <sy>")
                    return
                result = elem_ops.scale_element(parts[1], float(parts[2]), float(parts[3]))
                self.success(f"Scale '{parts[1]}' ({parts[2]}×{parts[3]}) — actions built.")
            elif sub == "rotate":
                if len(parts) < 3:
                    self.failure("Usage: element rotate <id> <angle> [cx cy]")
                    return
                angle = float(parts[2])
                cx = float(parts[3]) if len(parts) > 3 else 0.0
                cy = float(parts[4]) if len(parts) > 4 else 0.0
                result = elem_ops.rotate_element(parts[1], angle, cx, cy)
                self.success(f"Rotate '{parts[1]}' by {angle}° — actions built.")
            elif sub == "fill":
                if len(parts) < 3:
                    self.failure("Usage: element fill <id> <color>")
                    return
                result = elem_ops.set_fill(parts[1], parts[2])
                self.success(f"Fill '{parts[1]}' → {parts[2]}")
            elif sub == "stroke":
                if len(parts) < 3:
                    self.failure("Usage: element stroke <id> <color> [width]")
                    return
                width = float(parts[3]) if len(parts) > 3 else 1.0
                result = elem_ops.set_stroke(parts[1], parts[2], width)
                self.success(f"Stroke '{parts[1]}' → {parts[2]} w={width}")
            elif sub == "delete":
                if len(parts) < 2:
                    self.failure("Usage: element delete <id>")
                    return
                result = elem_ops.delete_element(parts[1])
                self.success(f"Delete '{parts[1]}' — actions built.")
            elif sub == "duplicate":
                if len(parts) < 2:
                    self.failure("Usage: element duplicate <id>")
                    return
                result = elem_ops.duplicate_element(parts[1])
                self.success(f"Duplicate '{parts[1]}' — actions built.")
            elif sub == "group":
                ids = [p for p in parts[1:] if not p.startswith("--")]
                gid = "group1"
                for i, p in enumerate(parts):
                    if p == "--group-id" and i + 1 < len(parts):
                        gid = parts[i + 1]
                        break
                if not ids:
                    self.failure("Provide at least one element id.")
                    return
                result = elem_ops.group_elements(ids, gid)
                self.success(f"Group {ids} as '#{gid}' — actions built.")
            else:
                self.failure(f"Unknown element subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # text

    def do_text(self, arg: str) -> None:
        """text <subcommand> [args]

        Subcommands:
          add <x> <y> <content>
          edit <id> <new_content>
          font <id> <family> <size> [weight]
          to-path <id>
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_text.__doc__)
            return
        sub = parts[0]

        try:
            if sub == "add":
                if len(parts) < 4:
                    self.failure("Usage: text add <x> <y> <content>")
                    return
                x, y = float(parts[1]), float(parts[2])
                content = " ".join(parts[3:])
                result = text_ops.add_text(x, y, content)
                self.success(f"Text '{content[:30]}' at ({x},{y}) — actions built.")
            elif sub == "edit":
                if len(parts) < 3:
                    self.failure("Usage: text edit <id> <new_content>")
                    return
                content = " ".join(parts[2:])
                result = text_ops.edit_text(parts[1], content)
                self.success(f"Edit text '{parts[1]}' — actions built.")
            elif sub == "font":
                if len(parts) < 4:
                    self.failure("Usage: text font <id> <family> <size> [weight]")
                    return
                weight = parts[4] if len(parts) > 4 else "normal"
                result = text_ops.set_font(parts[1], parts[2], float(parts[3]), weight)
                self.success(f"Font on '{parts[1]}' → {parts[2]} {parts[3]}px {weight}")
            elif sub == "to-path":
                if len(parts) < 2:
                    self.failure("Usage: text to-path <id>")
                    return
                result = text_ops.convert_text_to_path(parts[1])
                self.success(f"Convert '{parts[1]}' to path — actions built.")
            else:
                self.failure(f"Unknown text subcommand: {sub!r}")
        except (ValueError, IndexError) as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # export

    def do_export(self, arg: str) -> None:
        """export <out_path> [--format <fmt>] [--dpi <n>]

        Supported formats: png  pdf  eps  emf  svg
        """
        parts = self.parse_args(arg)
        if not parts:
            self.failure("Usage: export <out_path> [--format <fmt>] [--dpi <n>]")
            return

        svg = self._svg_path()
        if svg is None:
            self.failure("No SVG document in session.  Open one first.")
            return

        out_path = parts[0]
        fmt = "png"
        dpi = 96.0
        i = 1
        while i < len(parts):
            if parts[i] in ("--format", "-f") and i + 1 < len(parts):
                fmt = parts[i + 1]
                i += 2
            elif parts[i] in ("--dpi", "-d") and i + 1 < len(parts):
                dpi = float(parts[i + 1])
                i += 2
            else:
                i += 1

        try:
            fn_map = {
                "png": lambda: export_ops.export_png(svg, out_path, dpi=dpi),
                "pdf": lambda: export_ops.export_pdf(svg, out_path),
                "eps": lambda: export_ops.export_eps(svg, out_path),
                "emf": lambda: export_ops.export_emf(svg, out_path),
            }
            handler = fn_map.get(fmt.lower())
            if handler is None:
                self.failure(f"Unknown format: {fmt!r}")
                return
            result = handler()
            self.success(f"Export ({fmt.upper()}) → {out_path}")
            self.bullet(f"actions: {', '.join(result['actions'])}")
        except export_ops.ExportError as exc:
            self.failure(str(exc))

    # ------------------------------------------------------------------
    # status

    def do_status(self, _arg: str) -> None:
        """Print a summary of the current Inkscape session."""
        self.section("Inkscape session status")
        self.bullet(f"session : {self._session.name}")
        proj = self._session.project
        if proj is None:
            self.bullet("document: (none)")
        else:
            self.bullet(f"document: {proj.svg_path or '(unsaved)'}")
            self.bullet(f"canvas  : {proj.width_mm} × {proj.height_mm} mm")
            self.bullet(f"elements: {len(proj.elements)} tracked")
