"""Interactive REPL console for the Mermaid harness."""

from __future__ import annotations

from typing import Any

from ..shared import Console, Style
from .project import MermaidDiagram, MermaidProject
from .session import MermaidSession


class MermaidConsole(Console):
    """REPL for Mermaid diagram management and rendering."""

    harness_name = "mermaid"
    intro_extra = "Commands: render, new, diagram, flowchart, sequence, status, help"

    def __init__(self, session_name: str = "default", **kwargs: Any) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._session = MermaidSession.open_or_create(session_name)
        raw = self._session.data.get("project")
        self._project: MermaidProject | None = (
            MermaidProject.from_dict(raw) if raw else None
        )

    def _save(self) -> None:
        if self._project is not None:
            self._session.data["project"] = self._project.to_dict()
        self._session.save()

    def _ensure_project(self, name: str = "default") -> MermaidProject:
        if self._project is None:
            self._project = MermaidProject(name=name)
        return self._project

    # ------------------------------------------------------------------
    # Commands

    def do_status(self, _arg: str) -> None:
        """Show current project and session status."""
        self.section("Session")
        self.bullet(f"name: {self._session.name}")
        if self._project is None:
            self.bullet("project: (none)")
        else:
            self.bullet(f"project: {self._project.name!r}")
            self.bullet(f"diagrams: {len(self._project.diagrams)}")
            for d in self._project.diagrams:
                self.bullet(f"  {d.title or '(untitled)'!r} [{d.diagram_type}]")

    def do_new(self, arg: str) -> None:
        """Create a new diagram. Usage: new --type TYPE --title TITLE [--theme THEME]"""
        parts = self.parse_args(arg)
        dtype = "flowchart"
        title = None
        theme = "default"
        it = iter(parts)
        for tok in it:
            if tok == "--type":
                dtype = next(it, "flowchart")
            elif tok == "--title":
                title = next(it, None)
            elif tok == "--theme":
                theme = next(it, "default")
        project = self._ensure_project()
        diag = MermaidDiagram(diagram_type=dtype, title=title, theme=theme)
        project.add_diagram(diag)
        self._save()
        self.success(f"Diagram {title!r} [{dtype}] added to project")

    def do_render(self, arg: str) -> None:
        """Render a diagram. Usage: render --title TITLE --output PATH [--format png|svg|pdf]"""
        if self._project is None:
            print(Style.err("  No project. Use 'new' first."))
            return
        parts = self.parse_args(arg)
        title = None
        output = "diagram.png"
        fmt = "png"
        it = iter(parts)
        for tok in it:
            if tok == "--title":
                title = next(it, None)
            elif tok in ("--output", "-o"):
                output = next(it, "diagram.png")
            elif tok in ("--format", "-f"):
                fmt = next(it, "png")
        if title is None:
            if self._project.diagrams:
                diag = self._project.diagrams[-1]
            else:
                print(Style.err("  No diagrams. Use 'new' first."))
                return
        else:
            diag = self._project.find_diagram(title)
            if diag is None:
                self.failure(f"Diagram not found: {title!r}")
                return
        src = diag.render_src()
        from .backend import MermaidBackend

        be = MermaidBackend()
        try:
            if be.is_mmdc_available():
                out = be.render_with_mmdc(src, output, fmt=fmt, theme=diag.theme, bg_color=diag.background_color)
                self.success(f"Rendered to {out}")
            else:
                data = be.render_with_api(src, fmt=fmt, theme=diag.theme)
                with open(output, "wb") as f:
                    f.write(data)
                self.success(f"Rendered to {output} via API")
        except Exception as exc:
            self.failure(str(exc))

    def do_diagram(self, arg: str) -> None:
        """Manage diagrams. Usage: diagram add|remove|list|show [options]"""
        parts = self.parse_args(arg)
        if not parts:
            print(Style.err("  Usage: diagram add|remove|list|show [...]"))
            return
        sub = parts[0]
        if sub == "list":
            if self._project is None:
                self.bullet("(no project)")
                return
            self.section("Diagrams")
            for d in self._project.diagrams:
                self.bullet(f"{d.title or '(untitled)'!r} [{d.diagram_type}] theme={d.theme}")
        elif sub == "show":
            if self._project is None:
                return
            title = parts[2] if len(parts) > 2 and parts[1] == "--title" else (parts[1] if len(parts) > 1 else "")
            diag = self._project.find_diagram(title)
            if diag is None:
                self.failure(f"Not found: {title!r}")
                return
            self.section(f"Diagram: {diag.title!r}")
            print(diag.render_src())
        elif sub == "remove":
            if self._project is None:
                return
            title = parts[2] if len(parts) > 2 and parts[1] == "--title" else (parts[1] if len(parts) > 1 else "")
            removed = self._project.remove_diagram(title)
            if removed:
                self._save()
                self.success(f"Removed {title!r}")
            else:
                self.failure(f"Not found: {title!r}")
        else:
            print(Style.err(f"  Unknown sub-command: {sub!r}"))

    def do_flowchart(self, arg: str) -> None:
        """Build a flowchart. Usage: flowchart --nodes JSON --edges JSON [--direction LR]"""
        import json
        parts = self.parse_args(arg)
        nodes: list = []
        edges: list = []
        direction = "TB"
        it = iter(parts)
        for tok in it:
            if tok == "--nodes":
                nodes = json.loads(next(it, "[]"))
            elif tok == "--edges":
                edges = json.loads(next(it, "[]"))
            elif tok == "--direction":
                direction = next(it, "TB")
        from .core.diagrams import build_flowchart

        src = build_flowchart(nodes, edges, direction)
        project = self._ensure_project()
        diag = MermaidDiagram(diagram_type="flowchart", definition=src)
        project.add_diagram(diag)
        self._save()
        self.success("Flowchart added")
        print(src)

    def do_sequence(self, arg: str) -> None:
        """Build a sequence diagram. Usage: sequence --participants JSON --messages JSON"""
        import json
        parts = self.parse_args(arg)
        participants: list = []
        messages: list = []
        it = iter(parts)
        for tok in it:
            if tok == "--participants":
                participants = json.loads(next(it, "[]"))
            elif tok == "--messages":
                messages = json.loads(next(it, "[]"))
        from .core.diagrams import build_sequence

        src = build_sequence(participants, messages)
        project = self._ensure_project()
        diag = MermaidDiagram(diagram_type="sequenceDiagram", definition=src)
        project.add_diagram(diag)
        self._save()
        self.success("Sequence diagram added")
        print(src)

    def do_session(self, arg: str) -> None:
        """Session management. Usage: session show|list|delete"""
        parts = self.parse_args(arg)
        sub = parts[0] if parts else "show"
        if sub == "show":
            self.section("Session")
            self.bullet(f"name: {self._session.name}")
        elif sub == "list":
            for s in MermaidSession.list_sessions():
                self.bullet(s)
        elif sub == "delete":
            self._session.delete()
            self.success("Session deleted")
        else:
            print(Style.err(f"  Unknown: {sub!r}"))
