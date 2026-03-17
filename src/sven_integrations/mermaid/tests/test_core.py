"""Tests for the Mermaid harness core functionality."""

from __future__ import annotations

from sven_integrations.mermaid.core.diagrams import (
    build_class_diagram,
    build_er_diagram,
    build_flowchart,
    build_gantt,
    build_pie,
    build_sequence,
    build_state_diagram,
)
from sven_integrations.mermaid.project import MermaidDiagram, MermaidProject

# ---------------------------------------------------------------------------
# MermaidDiagram model
# ---------------------------------------------------------------------------


class TestMermaidDiagram:
    def test_defaults(self) -> None:
        d = MermaidDiagram()
        assert d.diagram_type == "flowchart"
        assert d.theme == "default"
        assert d.background_color == "white"
        assert d.title is None

    def test_render_src_with_title(self) -> None:
        d = MermaidDiagram(
            diagram_type="flowchart",
            title="My Chart",
            definition="flowchart TB\n    A --> B",
        )
        src = d.render_src()
        assert "---" in src
        assert "title: My Chart" in src
        assert "flowchart TB" in src

    def test_render_src_without_title(self) -> None:
        d = MermaidDiagram(definition="flowchart TB\n    A --> B")
        src = d.render_src()
        assert "---" not in src
        assert "flowchart TB" in src

    def test_validate_syntax_valid_flowchart(self) -> None:
        d = MermaidDiagram(
            diagram_type="flowchart",
            definition="flowchart TB\n    A --> B",
        )
        assert d.validate_syntax() is True

    def test_validate_syntax_valid_sequence(self) -> None:
        d = MermaidDiagram(
            diagram_type="sequenceDiagram",
            definition="sequenceDiagram\n    Alice->>Bob: Hello",
        )
        assert d.validate_syntax() is True

    def test_validate_syntax_nonempty_passes(self) -> None:
        d = MermaidDiagram(diagram_type="flowchart", definition="A --> B")
        assert d.validate_syntax() is True

    def test_validate_syntax_empty_fails(self) -> None:
        d = MermaidDiagram(diagram_type="flowchart", definition="")
        assert d.validate_syntax() is False

    def test_roundtrip(self) -> None:
        d = MermaidDiagram(
            diagram_type="gantt",
            title="Sprint",
            definition="gantt\n    title Sprint",
            theme="dark",
            background_color="transparent",
        )
        assert MermaidDiagram.from_dict(d.to_dict()) == d


# ---------------------------------------------------------------------------
# MermaidProject CRUD
# ---------------------------------------------------------------------------


class TestMermaidProject:
    def test_add_diagram(self) -> None:
        p = MermaidProject(name="Test")
        d = MermaidDiagram(title="D1", definition="flowchart TB\n    A")
        p.add_diagram(d)
        assert len(p.diagrams) == 1

    def test_remove_diagram(self) -> None:
        p = MermaidProject()
        p.add_diagram(MermaidDiagram(title="Keep", definition="flowchart TB\n    K"))
        p.add_diagram(MermaidDiagram(title="Drop", definition="flowchart TB\n    D"))
        removed = p.remove_diagram("Drop")
        assert removed is True
        assert len(p.diagrams) == 1
        assert p.diagrams[0].title == "Keep"

    def test_remove_nonexistent(self) -> None:
        p = MermaidProject()
        assert p.remove_diagram("Ghost") is False

    def test_find_diagram(self) -> None:
        p = MermaidProject()
        d = MermaidDiagram(title="Found", definition="flowchart TB\n    X")
        p.add_diagram(d)
        assert p.find_diagram("Found") is d
        assert p.find_diagram("Missing") is None

    def test_roundtrip(self) -> None:
        p = MermaidProject(name="Proj", default_theme="dark")
        p.add_diagram(MermaidDiagram(title="A", diagram_type="pie", definition="pie\n    title T"))
        p2 = MermaidProject.from_dict(p.to_dict())
        assert p2.name == "Proj"
        assert p2.default_theme == "dark"
        assert len(p2.diagrams) == 1
        assert p2.diagrams[0].title == "A"


# ---------------------------------------------------------------------------
# Diagram builder tests
# ---------------------------------------------------------------------------


class TestBuildFlowchart:
    def test_basic(self) -> None:
        nodes = [{"id": "A", "label": "Start"}, {"id": "B", "label": "End"}]
        edges = [{"from": "A", "to": "B", "label": "go"}]
        src = build_flowchart(nodes, edges, "LR")
        assert "flowchart LR" in src
        assert '"Start"' in src
        assert '"End"' in src
        assert "go" in src

    def test_default_direction(self) -> None:
        src = build_flowchart([], [])
        assert "flowchart TB" in src

    def test_shapes(self) -> None:
        nodes = [
            {"id": "D", "label": "Decision", "shape": "diamond"},
            {"id": "C", "label": "Circle", "shape": "circle"},
        ]
        src = build_flowchart(nodes, [])
        assert "{" in src
        assert "((" in src

    def test_invalid_direction_falls_back(self) -> None:
        src = build_flowchart([], [], direction="INVALID")
        assert "flowchart TB" in src


class TestBuildSequence:
    def test_basic(self) -> None:
        parts = ["Alice", "Bob"]
        msgs = [{"from": "Alice", "to": "Bob", "text": "Hello"}]
        src = build_sequence(parts, msgs)
        assert "sequenceDiagram" in src
        assert "participant Alice" in src
        assert "participant Bob" in src
        assert "Alice->>Bob: Hello" in src

    def test_with_note(self) -> None:
        msgs = [{"from": "A", "to": "B", "text": "Hi", "note": "important"}]
        src = build_sequence(["A", "B"], msgs)
        assert "Note over A,B: important" in src

    def test_custom_arrow(self) -> None:
        msgs = [{"from": "A", "to": "B", "text": "req", "type": "->"}]
        src = build_sequence(["A", "B"], msgs)
        assert "A->B: req" in src


class TestBuildGantt:
    def test_basic(self) -> None:
        sections = [
            {
                "title": "Phase 1",
                "tasks": [{"name": "Design", "start": "2024-01-01", "end": "2024-01-07"}],
            }
        ]
        src = build_gantt("My Project", sections)
        assert "gantt" in src
        assert "title My Project" in src
        assert "section Phase 1" in src
        assert "Design" in src

    def test_empty_sections(self) -> None:
        src = build_gantt("Empty", [])
        assert "gantt" in src


class TestBuildPie:
    def test_basic(self) -> None:
        slices = [("Alpha", 40.0), ("Beta", 35.0), ("Gamma", 25.0)]
        src = build_pie("Distribution", slices)
        assert "pie title Distribution" in src
        assert '"Alpha" : 40.0' in src

    def test_empty(self) -> None:
        src = build_pie("Empty", [])
        assert "pie" in src


class TestBuildStateDiagram:
    def test_basic(self) -> None:
        states = ["Idle", "Running", "Done"]
        transitions = [
            {"from": "__start__", "to": "Idle"},
            {"from": "Idle", "to": "Running", "label": "start"},
            {"from": "Running", "to": "Done"},
        ]
        src = build_state_diagram(states, transitions)
        assert "stateDiagram-v2" in src
        assert "[*] --> Idle" in src
        assert "Idle --> Running : start" in src


class TestBuildClassDiagram:
    def test_basic(self) -> None:
        classes = [
            {"name": "Animal", "attributes": ["String name"], "methods": ["speak"]}
        ]
        relationships = [{"from": "Dog", "to": "Animal", "type": "<|--"}]
        src = build_class_diagram(classes, relationships)
        assert "classDiagram" in src
        assert "class Animal" in src
        assert "String name" in src
        assert "speak()" in src
        assert "Dog <|-- Animal" in src


class TestBuildErDiagram:
    def test_basic(self) -> None:
        entities = [
            {
                "name": "User",
                "attributes": [
                    {"type": "int", "name": "id", "key": True},
                    {"type": "string", "name": "email"},
                ],
            }
        ]
        relationships = [
            {"from": "User", "to": "Order", "relation": "||--o{", "label": "places"}
        ]
        src = build_er_diagram(entities, relationships)
        assert "erDiagram" in src
        assert "User {" in src
        assert "int id PK" in src
        assert "string email" in src
        assert 'User ||--o{ Order : "places"' in src


# ---------------------------------------------------------------------------
# Backend renderer selection
# ---------------------------------------------------------------------------


class TestMermaidBackend:
    def test_choose_renderer_api_when_mmdc_missing(self) -> None:
        from sven_integrations.mermaid.backend import MermaidBackend

        be = MermaidBackend(mmdc_bin="definitely_not_installed_binary_xyz")
        assert be.is_mmdc_available() is False
        assert be.choose_renderer() == "api"

    def test_is_mmdc_available_returns_bool(self) -> None:
        from sven_integrations.mermaid.backend import MermaidBackend

        be = MermaidBackend()
        result = be.is_mmdc_available()
        assert isinstance(result, bool)
