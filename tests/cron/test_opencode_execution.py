"""Tests for OpenCode cron execution: command building and result parsing."""

from __future__ import annotations

import json
from unittest.mock import patch

from klir.cli.param_resolver import TaskExecutionConfig
from klir.cron.execution import (
    _build_opencode_cmd,
    build_cmd,
    parse_opencode_result,
    parse_result,
)

# ---------------------------------------------------------------------------
# parse_opencode_result
# ---------------------------------------------------------------------------


class TestParseOpenCodeResult:
    def test_empty_stdout(self) -> None:
        assert parse_opencode_result(b"") == ""

    def test_json_result_field(self) -> None:
        data = json.dumps({"result": "Task completed."}).encode()
        assert parse_opencode_result(data) == "Task completed."

    def test_json_text_field(self) -> None:
        data = json.dumps({"text": "Output text"}).encode()
        assert parse_opencode_result(data) == "Output text"

    def test_plain_text_fallback(self) -> None:
        result = parse_opencode_result(b"raw output here")
        assert "raw output here" in result

    def test_parse_result_dispatches_to_opencode(self) -> None:
        data = json.dumps({"result": "dispatched"}).encode()
        assert parse_result("opencode", data) == "dispatched"


# ---------------------------------------------------------------------------
# _build_opencode_cmd
# ---------------------------------------------------------------------------


def _exec_config(**overrides: object) -> TaskExecutionConfig:
    defaults = {
        "provider": "opencode",
        "model": "anthropic/claude-sonnet-4",
        "reasoning_effort": "",
        "cli_parameters": [],
        "permission_mode": "bypassPermissions",
        "working_dir": "/tmp/test",
        "file_access": "all",
        "allowed_tools": [],
        "disallowed_tools": [],
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return TaskExecutionConfig(**defaults)  # type: ignore[arg-type]


class TestBuildOpenCodeCmd:
    def test_returns_none_when_not_installed(self) -> None:
        with patch("klir.cron.execution.which", return_value=None):
            result = _build_opencode_cmd(_exec_config(), "do task")
        assert result is None

    def test_basic_command_structure(self) -> None:
        with patch("klir.cron.execution.which", return_value="/usr/bin/opencode"):
            result = _build_opencode_cmd(_exec_config(), "do task")
        assert result is not None
        cmd = result.cmd
        assert cmd[0] == "/usr/bin/opencode"
        assert "-p" in cmd
        assert "do task" in cmd
        assert "-q" in cmd
        assert "-f" in cmd
        assert "json" in cmd
        assert "-m" in cmd
        assert "anthropic/claude-sonnet-4" in cmd

    def test_no_model_omits_flag(self) -> None:
        with patch("klir.cron.execution.which", return_value="/usr/bin/opencode"):
            result = _build_opencode_cmd(_exec_config(model=""), "task")
        assert result is not None
        assert "-m" not in result.cmd

    def test_tool_filtering(self) -> None:
        with patch("klir.cron.execution.which", return_value="/usr/bin/opencode"):
            result = _build_opencode_cmd(
                _exec_config(
                    allowed_tools=["bash", "read"],
                    disallowed_tools=["write"],
                ),
                "task",
            )
        assert result is not None
        cmd = result.cmd
        idx_allowed = cmd.index("--allowedTools")
        assert cmd[idx_allowed + 1] == "bash,read"
        idx_excluded = cmd.index("--excludedTools")
        assert cmd[idx_excluded + 1] == "write"

    def test_cli_parameters_appended(self) -> None:
        with patch("klir.cron.execution.which", return_value="/usr/bin/opencode"):
            result = _build_opencode_cmd(
                _exec_config(cli_parameters=["--verbose"]),
                "task",
            )
        assert result is not None
        assert "--verbose" in result.cmd

    def test_build_cmd_dispatches_to_opencode(self) -> None:
        with patch("klir.cron.execution.which", return_value="/usr/bin/opencode"):
            result = build_cmd(_exec_config(), "task")
        assert result is not None
        assert result.cmd[0] == "/usr/bin/opencode"

    def test_no_stdin_input(self) -> None:
        with patch("klir.cron.execution.which", return_value="/usr/bin/opencode"):
            result = _build_opencode_cmd(_exec_config(), "task")
        assert result is not None
        assert result.stdin_input is None
