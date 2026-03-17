"""Tests for the AnyGen harness — models, session, verify, and task helpers."""

from __future__ import annotations

import json
import uuid
import zipfile
from pathlib import Path

import pytest

from sven_integrations.anygen.core.task import (
    expected_extension,
    format_task,
    validate_task,
)
from sven_integrations.anygen.core.verify import VerifyError, verify_file
from sven_integrations.anygen.project import (
    OPERATION_EXTENSIONS,
    VALID_OPERATIONS,
    AnygenTask,
    HistoryEntry,
)
from sven_integrations.anygen.session import AnygenSession

# ---------------------------------------------------------------------------
# AnygenTask
# ---------------------------------------------------------------------------


class TestAnygenTask:
    def _make(self, **kw: object) -> AnygenTask:
        return AnygenTask(
            local_id=str(uuid.uuid4()),
            operation=kw.pop("operation", "slide"),
            prompt=kw.pop("prompt", "Test prompt"),
            **kw,  # type: ignore[arg-type]
        )

    def test_defaults(self) -> None:
        t = self._make()
        assert t.status == "pending"
        assert t.task_id == ""
        assert t.submitted is False
        assert t.output_path is None
        assert t.error is None

    def test_roundtrip(self) -> None:
        t = self._make(operation="doc", prompt="Write a report", task_id="remote-abc")
        t2 = AnygenTask.from_dict(t.to_dict())
        assert t2.local_id == t.local_id
        assert t2.operation == "doc"
        assert t2.task_id == "remote-abc"
        assert t2.prompt == "Write a report"

    def test_from_dict_generates_local_id_when_missing(self) -> None:
        d = {"operation": "slide", "prompt": "Hello"}
        t = AnygenTask.from_dict(d)
        assert t.local_id  # must not be empty

    def test_from_dict_sets_status_default(self) -> None:
        d = {"local_id": "x", "operation": "pdf", "prompt": "a"}
        t = AnygenTask.from_dict(d)
        assert t.status == "pending"

    def test_valid_operations(self) -> None:
        assert "slide" in VALID_OPERATIONS
        assert "doc" in VALID_OPERATIONS
        assert "pdf" in VALID_OPERATIONS
        assert "image" in VALID_OPERATIONS
        assert "data" in VALID_OPERATIONS

    def test_operation_extensions(self) -> None:
        assert OPERATION_EXTENSIONS["slide"] == ".pptx"
        assert OPERATION_EXTENSIONS["doc"] == ".docx"
        assert OPERATION_EXTENSIONS["pdf"] == ".pdf"
        assert OPERATION_EXTENSIONS["image"] == ".png"
        assert OPERATION_EXTENSIONS["data"] == ".json"


# ---------------------------------------------------------------------------
# HistoryEntry
# ---------------------------------------------------------------------------


class TestHistoryEntry:
    def test_roundtrip(self) -> None:
        e = HistoryEntry(action="create", task_id="t1", details={"op": "slide"})
        e2 = HistoryEntry.from_dict(e.to_dict())
        assert e2.action == "create"
        assert e2.task_id == "t1"
        assert e2.details == {"op": "slide"}
        assert e2.timestamp == pytest.approx(e.timestamp, abs=1)

    def test_from_dict_no_task_id(self) -> None:
        e = HistoryEntry.from_dict({"action": "prepare"})
        assert e.task_id is None


# ---------------------------------------------------------------------------
# AnygenSession
# ---------------------------------------------------------------------------


class TestAnygenSession:
    def _session(self, tmp_path: Path) -> AnygenSession:
        import os
        os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
        s = AnygenSession(name="test-session")
        return s

    def test_config_set_get(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        s.set_config("api_key", "sk-ag-test")
        assert s.get_config("api_key") == "sk-ag-test"

    def test_config_missing_returns_none(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        assert s.get_config("missing") is None

    def test_all_config(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        s.set_config("api_key", "k")
        s.set_config("api_base_url", "https://example.com")
        cfg = s.all_config()
        assert cfg["api_key"] == "k"
        assert cfg["api_base_url"] == "https://example.com"

    def test_get_api_base_url_default(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        assert "anygen" in s.get_api_base_url()

    def test_upsert_and_find_task(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        t = AnygenTask(local_id="local-1", operation="slide", prompt="hi", task_id="remote-1")
        s.upsert_task(t)
        found = s.find_task("remote-1")
        assert found is not None
        assert found.local_id == "local-1"

    def test_find_task_by_prefix(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        t = AnygenTask(local_id="abc123", operation="doc", prompt="x")
        s.upsert_task(t)
        assert s.find_task("abc") is not None

    def test_upsert_updates_existing(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        t = AnygenTask(local_id="lid", operation="pdf", prompt="p")
        s.upsert_task(t)
        t.status = "completed"
        s.upsert_task(t)
        tasks = s.load_tasks()
        assert len(tasks) == 1
        assert tasks[0].status == "completed"

    def test_history_undo_redo(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        e1 = HistoryEntry(action="create", task_id="t1")
        e2 = HistoryEntry(action="prepare", task_id="t2")
        s.push_history(e1)
        s.push_history(e2)

        undone = s.undo()
        assert undone is not None
        assert undone.action == "prepare"

        assert len(s.load_history()) == 1
        assert len(s.load_redo_stack()) == 1

        redone = s.redo()
        assert redone is not None
        assert redone.action == "prepare"

        assert len(s.load_history()) == 2
        assert len(s.load_redo_stack()) == 0

    def test_push_history_clears_redo(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        s.push_history(HistoryEntry(action="create", task_id="t1"))
        s.undo()
        assert len(s.load_redo_stack()) == 1
        s.push_history(HistoryEntry(action="create", task_id="t2"))
        assert len(s.load_redo_stack()) == 0

    def test_undo_empty_returns_none(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        assert s.undo() is None

    def test_redo_empty_returns_none(self, tmp_path: Path) -> None:
        s = self._session(tmp_path)
        assert s.redo() is None


# ---------------------------------------------------------------------------
# core.task helpers
# ---------------------------------------------------------------------------


class TestValidateTask:
    def _task(self, **kw: object) -> AnygenTask:
        return AnygenTask(
            local_id=str(uuid.uuid4()),
            operation=kw.pop("operation", "slide"),  # type: ignore[arg-type]
            prompt=kw.pop("prompt", "Hello"),  # type: ignore[arg-type]
            **kw,  # type: ignore[arg-type]
        )

    def test_valid(self) -> None:
        assert validate_task(self._task()) == []

    def test_empty_prompt(self) -> None:
        errors = validate_task(self._task(prompt="   "))
        assert any("prompt" in e for e in errors)

    def test_invalid_operation(self) -> None:
        errors = validate_task(self._task(operation="video"))
        assert any("operation" in e for e in errors)

    def test_missing_local_id(self) -> None:
        t = AnygenTask(local_id="", operation="slide", prompt="hi")
        errors = validate_task(t)
        assert any("local_id" in e for e in errors)


class TestExpectedExtension:
    def test_known(self) -> None:
        assert expected_extension("slide") == ".pptx"
        assert expected_extension("doc") == ".docx"
        assert expected_extension("image") == ".png"

    def test_unknown(self) -> None:
        assert expected_extension("unknown") == ".bin"


class TestFormatTask:
    def test_basic(self) -> None:
        t = AnygenTask(local_id="lid", operation="slide", prompt="Test", task_id="rem-1")
        text = format_task(t)
        assert "rem-1" in text
        assert "slide" in text
        assert "Test" in text

    def test_truncates_long_prompt(self) -> None:
        t = AnygenTask(local_id="lid", operation="doc", prompt="x" * 200)
        text = format_task(t)
        assert "…" in text


# ---------------------------------------------------------------------------
# core.verify
# ---------------------------------------------------------------------------


class TestVerifyFile:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(VerifyError, match="not found"):
            verify_file(tmp_path / "missing.pptx")

    def test_valid_png(self, tmp_path: Path) -> None:
        p = tmp_path / "img.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        r = verify_file(p)
        assert r["ok"] is True
        assert r["type"] == "png"

    def test_invalid_png(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.png"
        p.write_bytes(b"\x00" * 20)
        with pytest.raises(VerifyError, match="magic"):
            verify_file(p)

    def test_valid_pdf(self, tmp_path: Path) -> None:
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4\n%EOF\n")
        r = verify_file(p)
        assert r["ok"] is True

    def test_invalid_pdf(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.pdf"
        p.write_bytes(b"not a pdf")
        with pytest.raises(VerifyError, match="magic"):
            verify_file(p)

    def test_valid_pptx(self, tmp_path: Path) -> None:
        p = tmp_path / "deck.pptx"
        with zipfile.ZipFile(str(p), "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("ppt/presentation.xml", "<p/>")
        r = verify_file(p)
        assert r["ok"] is True
        assert r["type"] == "pptx"

    def test_invalid_pptx_missing_content_types(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.pptx"
        with zipfile.ZipFile(str(p), "w") as zf:
            zf.writestr("other.xml", "<x/>")
        with pytest.raises(VerifyError, match="Content_Types"):
            verify_file(p)

    def test_valid_docx(self, tmp_path: Path) -> None:
        p = tmp_path / "report.docx"
        with zipfile.ZipFile(str(p), "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("word/document.xml", "<w:document/>")
        r = verify_file(p)
        assert r["ok"] is True

    def test_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        r = verify_file(p)
        assert r["ok"] is True

    def test_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not valid json}", encoding="utf-8")
        with pytest.raises(VerifyError, match="JSON"):
            verify_file(p)

    def test_valid_svg(self, tmp_path: Path) -> None:
        p = tmp_path / "icon.svg"
        p.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>', encoding="utf-8")
        r = verify_file(p)
        assert r["ok"] is True

    def test_invalid_svg(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.svg"
        p.write_text("<html><body>not svg</body></html>", encoding="utf-8")
        with pytest.raises(VerifyError, match="svg"):
            verify_file(p)

    def test_unknown_extension_skips_check(self, tmp_path: Path) -> None:
        p = tmp_path / "file.xyz"
        p.write_bytes(b"any content")
        r = verify_file(p)
        assert r["ok"] is True
        assert "skip" in r["details"].lower()
