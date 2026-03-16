"""Tests for the AnyGen harness core functionality."""

from __future__ import annotations

import csv
import json
from pathlib import Path


from sven_integrations.anygen.core.export import (
    export_results_csv,
    export_results_json,
    export_results_markdown,
    format_as_template,
)
from sven_integrations.anygen.core.task import (
    create_task,
    estimate_tokens,
    task_to_messages,
    validate_task,
)
from sven_integrations.anygen.project import (
    AnygenProject,
    GenerationParams,
    GenerationResult,
    GenerationTask,
)


# ---------------------------------------------------------------------------
# GenerationParams
# ---------------------------------------------------------------------------


class TestGenerationParams:
    def test_defaults(self) -> None:
        p = GenerationParams()
        assert p.temperature == 0.7
        assert p.max_tokens == 1024
        assert p.top_p is None
        assert p.stop_sequences == []

    def test_roundtrip(self) -> None:
        p = GenerationParams(temperature=0.3, max_tokens=512, top_p=0.9, stop_sequences=["END"])
        p2 = GenerationParams.from_dict(p.to_dict())
        assert p2 == p


# ---------------------------------------------------------------------------
# GenerationTask
# ---------------------------------------------------------------------------


class TestGenerationTask:
    def test_creation(self) -> None:
        task = create_task("Say hello", model="gpt-4o", provider="openai")
        assert task.prompt == "Say hello"
        assert task.model == "gpt-4o"
        assert task.provider == "openai"
        assert len(task.task_id) == 36  # UUID4

    def test_roundtrip(self) -> None:
        task = create_task("Hello", model="claude-3", provider="anthropic", temperature=0.5)
        task2 = GenerationTask.from_dict(task.to_dict())
        assert task2.task_id == task.task_id
        assert task2.parameters.temperature == 0.5

    def test_validate_valid(self) -> None:
        task = create_task("Describe the sky.", model="gpt-4o-mini", provider="openai")
        assert validate_task(task) == []

    def test_validate_empty_prompt(self) -> None:
        task = create_task("", model="gpt-4o-mini", provider="openai")
        errors = validate_task(task)
        assert any("prompt" in e for e in errors)

    def test_validate_invalid_provider(self) -> None:
        task = create_task("Hi", model="gpt-4o", provider="unknown")
        errors = validate_task(task)
        assert any("provider" in e for e in errors)

    def test_validate_bad_temperature(self) -> None:
        task = create_task("Hi", model="gpt-4o", provider="openai", temperature=5.0)
        errors = validate_task(task)
        assert any("temperature" in e for e in errors)


# ---------------------------------------------------------------------------
# GenerationResult
# ---------------------------------------------------------------------------


class TestGenerationResult:
    def test_defaults(self) -> None:
        r = GenerationResult(task_id="abc")
        assert r.status == "pending"
        assert r.output is None
        assert r.error is None

    def test_roundtrip(self) -> None:
        r = GenerationResult(
            task_id="t1",
            status="completed",
            output="Hello!",
            created_at=1000.0,
            completed_at=1002.5,
            metadata={"model": "gpt-4o"},
        )
        r2 = GenerationResult.from_dict(r.to_dict())
        assert r2.task_id == "t1"
        assert r2.output == "Hello!"
        assert r2.completed_at == 1002.5


# ---------------------------------------------------------------------------
# AnygenProject CRUD
# ---------------------------------------------------------------------------


class TestAnygenProject:
    def _make_result(self, task_id: str, status: str = "completed") -> GenerationResult:
        return GenerationResult(task_id=task_id, status=status, output="out")

    def test_add_task(self) -> None:
        project = AnygenProject()
        task = create_task("Test", model="gpt-4o", provider="openai")
        project.add_task(task)
        assert len(project.tasks) == 1

    def test_pending_tasks(self) -> None:
        project = AnygenProject()
        t1 = create_task("P1", model="m", provider="openai")
        t2 = create_task("P2", model="m", provider="openai")
        project.add_task(t1)
        project.add_task(t2)
        project.results.append(self._make_result(t1.task_id, "completed"))
        pending = project.pending_tasks()
        assert len(pending) == 1
        assert pending[0].task_id == t2.task_id

    def test_completed_tasks(self) -> None:
        project = AnygenProject()
        t1 = create_task("C1", model="m", provider="openai")
        project.add_task(t1)
        project.results.append(self._make_result(t1.task_id, "completed"))
        assert len(project.completed_tasks()) == 1

    def test_get_result(self) -> None:
        project = AnygenProject()
        task = create_task("R", model="m", provider="openai")
        project.add_task(task)
        r = self._make_result(task.task_id)
        project.results.append(r)
        assert project.get_result(task.task_id) is r
        assert project.get_result("missing") is None

    def test_roundtrip(self) -> None:
        project = AnygenProject(name="my-project")
        task = create_task("Prompt", model="gpt-4o", provider="openai")
        project.add_task(task)
        project.results.append(GenerationResult(task_id=task.task_id, status="completed", output="ok"))
        p2 = AnygenProject.from_dict(project.to_dict())
        assert p2.name == "my-project"
        assert len(p2.tasks) == 1
        assert len(p2.results) == 1


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_short(self) -> None:
        assert estimate_tokens("Hello") == max(1, len("Hello") // 4)

    def test_long(self) -> None:
        text = "word " * 100
        assert estimate_tokens(text) == len(text) // 4

    def test_empty(self) -> None:
        assert estimate_tokens("") == 1


# ---------------------------------------------------------------------------
# task_to_messages
# ---------------------------------------------------------------------------


class TestTaskToMessages:
    def test_format(self) -> None:
        task = create_task("What is 2+2?", model="gpt-4o", provider="openai")
        msgs = task_to_messages(task)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "What is 2+2?"


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


class TestExportJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        results = [
            GenerationResult(task_id="t1", status="completed", output="Hello"),
            GenerationResult(task_id="t2", status="failed", error="timeout"),
        ]
        out = str(tmp_path / "results.json")
        export_results_json(results, out)
        data = json.loads(Path(out).read_text())
        assert len(data) == 2
        assert data[0]["task_id"] == "t1"
        assert data[1]["status"] == "failed"


class TestExportCsv:
    def test_writes_valid_csv(self, tmp_path: Path) -> None:
        results = [
            GenerationResult(task_id="t1", status="completed", output="out1"),
        ]
        out = str(tmp_path / "results.csv")
        export_results_csv(results, out)
        rows = list(csv.DictReader(open(out)))
        assert len(rows) == 1
        assert rows[0]["task_id"] == "t1"
        assert rows[0]["output"] == "out1"


class TestExportMarkdown:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        results = [GenerationResult(task_id="abc123", status="completed", output="The answer.")]
        out = str(tmp_path / "results.md")
        export_results_markdown(results, out)
        content = Path(out).read_text()
        assert "# Generation Results" in content
        assert "abc123" in content
        assert "The answer." in content


class TestFormatAsTemplate:
    def test_basic_substitution(self) -> None:
        r = GenerationResult(
            task_id="xyz",
            status="completed",
            output="42",
            metadata={"model": "gpt-4o", "provider": "openai"},
        )
        result = format_as_template(r, "Model {model} says: {output}")
        assert result == "Model gpt-4o says: 42"

    def test_missing_placeholder_left_unchanged(self) -> None:
        r = GenerationResult(task_id="id", status="completed", output="hi")
        result = format_as_template(r, "Hello {name}")
        assert "{name}" in result
