"""Tests for CronRunLogEntry model and JSONL log operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from klir.cron.run_log import (
    CronRunLogEntry,
    RunLogPage,
    append_run_log,
    read_run_log_page,
    resolve_run_log_path,
    save_run_output,
)


class TestCronRunLogEntry:
    def test_to_json_line_basic(self) -> None:
        entry = CronRunLogEntry(ts=1234567890.0, job_id="daily", status="success")
        line = entry.to_json_line()
        data = json.loads(line)
        assert data["ts"] == 1234567890.0
        assert data["job_id"] == "daily"
        assert data["status"] == "success"
        assert data["action"] == "finished"

    def test_to_json_line_omits_none(self) -> None:
        entry = CronRunLogEntry(ts=1.0, job_id="test")
        line = entry.to_json_line()
        data = json.loads(line)
        assert "error" not in data
        assert "summary" not in data
        assert "model" not in data

    def test_from_json_line_roundtrip(self) -> None:
        entry = CronRunLogEntry(
            ts=1234567890.0,
            job_id="daily",
            status="success",
            duration_ms=1500,
            provider="claude",
        )
        line = entry.to_json_line()
        restored = CronRunLogEntry.from_json_line(line)
        assert restored is not None
        assert restored.ts == 1234567890.0
        assert restored.job_id == "daily"
        assert restored.status == "success"
        assert restored.duration_ms == 1500
        assert restored.provider == "claude"

    def test_from_json_line_int_ts_works(self) -> None:
        line = '{"ts": 1234567890, "job_id": "daily"}'
        entry = CronRunLogEntry.from_json_line(line)
        assert entry is not None
        assert entry.ts == 1234567890
        assert entry.job_id == "daily"

    def test_from_json_line_malformed_returns_none(self) -> None:
        assert CronRunLogEntry.from_json_line("{not valid json") is None
        assert CronRunLogEntry.from_json_line("") is None
        assert CronRunLogEntry.from_json_line("null") is None
        # Missing ts
        assert CronRunLogEntry.from_json_line('{"job_id": "daily"}') is None
        # Non-numeric ts (string)
        assert CronRunLogEntry.from_json_line('{"ts": "not_a_number", "job_id": "daily"}') is None
        # Empty job_id
        assert CronRunLogEntry.from_json_line('{"ts": 1234567890.0, "job_id": ""}') is None
        # Whitespace-only job_id
        assert CronRunLogEntry.from_json_line('{"ts": 1234567890.0, "job_id": "  "}') is None
        # Missing job_id entirely
        assert CronRunLogEntry.from_json_line('{"ts": 1234567890.0}') is None


class TestResolveRunLogPath:
    def test_returns_jsonl_path(self, tmp_path: Path) -> None:
        path = resolve_run_log_path(tmp_path / "state", "daily")
        assert path == tmp_path / "state" / "daily" / "runs.jsonl"

    def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="path traversal"):
            resolve_run_log_path(tmp_path / "state", "../escape")


class TestAppendRunLog:
    async def test_creates_file_and_appends(self, tmp_path: Path) -> None:
        path = tmp_path / "daily" / "runs.jsonl"
        entry = CronRunLogEntry(ts=1.0, job_id="daily", status="success")
        await append_run_log(path, entry)
        assert path.exists()
        lines = path.read_text().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["status"] == "success"

    async def test_multiple_appends(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        for i in range(3):
            entry = CronRunLogEntry(ts=float(i), job_id="job", status="success")
            await append_run_log(path, entry)
        lines = path.read_text().splitlines()
        assert len(lines) == 3

    async def test_prunes_when_exceeds_max_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        # Write enough entries to exceed 100 bytes with keep_lines=2
        for i in range(10):
            entry = CronRunLogEntry(ts=float(i), job_id="job", status="success")
            await append_run_log(path, entry, max_bytes=100, keep_lines=2)
        lines = path.read_text().splitlines()
        assert len(lines) <= 2


class TestReadRunLogPage:
    async def test_empty_file_returns_empty_page(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        page = await read_run_log_page(path)
        assert page.entries == []
        assert page.total == 0
        assert page.has_more is False

    async def test_missing_file_returns_empty_page(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.jsonl"
        page = await read_run_log_page(path)
        assert page.entries == []
        assert page.total == 0

    async def test_desc_order(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        for i in range(3):
            entry = CronRunLogEntry(ts=float(i), job_id="job", status="success")
            await append_run_log(path, entry)
        page = await read_run_log_page(path, sort_dir="desc")
        assert page.entries[0].ts == 2.0
        assert page.entries[-1].ts == 0.0

    async def test_status_filter(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        await append_run_log(path, CronRunLogEntry(ts=1.0, job_id="job", status="success"))
        await append_run_log(path, CronRunLogEntry(ts=2.0, job_id="job", status="error:exit_1"))
        page = await read_run_log_page(path, status_filter="success")
        assert page.total == 1
        assert page.entries[0].status == "success"

    async def test_pagination_offset(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        for i in range(5):
            await append_run_log(path, CronRunLogEntry(ts=float(i), job_id="job", status="success"))
        page = await read_run_log_page(path, limit=2, offset=2)
        assert len(page.entries) == 2
        assert page.total == 5
        assert page.has_more is True

    async def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "runs.jsonl"
        path.write_text('{"ts": 1.0, "job_id": "ok", "action": "finished"}\nnot-json\n')
        page = await read_run_log_page(path)
        assert page.total == 1

    def test_run_log_page_type(self) -> None:
        """RunLogPage is accessible from the import."""
        assert RunLogPage is not None


class TestSaveRunOutput:
    async def test_saves_stdout_and_stderr(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        result = await save_run_output(state_dir, run_id="abc123", stdout=b"hello", stderr=b"warn")
        assert result is not None
        assert result.exists()
        content = result.read_bytes()
        assert b"hello" in content
        assert b"warn" in content

    async def test_creates_directory(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "new" / "state"
        result = await save_run_output(state_dir, run_id="xyz", stdout=b"output", stderr=b"")
        assert result is not None
        assert result.parent.exists()

    async def test_returns_none_for_empty_output(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        result = await save_run_output(state_dir, run_id="empty", stdout=b"", stderr=b"")
        assert result is None
