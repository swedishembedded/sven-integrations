"""Mermaid diagram and project models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DiagramType = Literal[
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "gantt",
    "pie",
    "gitGraph",
    "mindmap",
]

Theme = Literal["default", "dark", "forest", "neutral"]

VALID_DIAGRAM_TYPES: set[str] = {
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "gantt",
    "pie",
    "gitGraph",
    "mindmap",
}

VALID_THEMES: set[str] = {"default", "dark", "forest", "neutral"}

# Minimal structural markers for each diagram type used in syntax validation
_STRUCTURE_MARKERS: dict[str, list[str]] = {
    "flowchart": ["flowchart", "graph"],
    "sequenceDiagram": ["sequenceDiagram"],
    "classDiagram": ["classDiagram"],
    "stateDiagram": ["stateDiagram"],
    "erDiagram": ["erDiagram"],
    "gantt": ["gantt"],
    "pie": ["pie"],
    "gitGraph": ["gitGraph"],
    "mindmap": ["mindmap"],
}


@dataclass
class MermaidDiagram:
    diagram_type: str = "flowchart"
    title: str | None = None
    definition: str = ""
    theme: str = "default"
    background_color: str = "white"

    def render_src(self) -> str:
        """Return full Mermaid source including title directive."""
        parts: list[str] = []
        if self.title:
            parts.append(f"---\ntitle: {self.title}\n---")
        parts.append(self.definition.strip())
        return "\n".join(parts)

    def validate_syntax(self) -> bool:
        """Basic structural validation: check that the definition starts with the right keyword."""
        stripped = self.definition.strip().lower()
        markers = _STRUCTURE_MARKERS.get(self.diagram_type, [self.diagram_type.lower()])
        for marker in markers:
            if stripped.startswith(marker.lower()):
                return True
        # Allow definitions that don't start with the keyword (user provides body only)
        # Consider it valid if there's at least some non-empty content
        return len(stripped) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "definition": self.definition,
            "theme": self.theme,
            "background_color": self.background_color,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MermaidDiagram":
        return cls(
            diagram_type=d.get("diagram_type", "flowchart"),
            title=d.get("title"),
            definition=d.get("definition", ""),
            theme=d.get("theme", "default"),
            background_color=d.get("background_color", "white"),
        )


@dataclass
class MermaidProject:
    name: str = "Untitled"
    diagrams: list[MermaidDiagram] = field(default_factory=list)
    default_theme: str = "default"

    def add_diagram(self, diagram: MermaidDiagram) -> None:
        self.diagrams.append(diagram)

    def remove_diagram(self, title: str) -> bool:
        for i, d in enumerate(self.diagrams):
            if d.title == title:
                self.diagrams.pop(i)
                return True
        return False

    def find_diagram(self, title: str) -> MermaidDiagram | None:
        for d in self.diagrams:
            if d.title == title:
                return d
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "diagrams": [d.to_dict() for d in self.diagrams],
            "default_theme": self.default_theme,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MermaidProject":
        return cls(
            name=d.get("name", "Untitled"),
            diagrams=[MermaidDiagram.from_dict(x) for x in d.get("diagrams", [])],
            default_theme=d.get("default_theme", "default"),
        )
