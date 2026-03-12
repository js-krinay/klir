# OpenCode Feature Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring OpenCode provider to full feature parity with Claude, Codex, and Gemini across tests, cron execution, workspace rules, and orchestrator integration.

**Architecture:** OpenCode was added as the 4th provider (commit 8f156da) with a working provider + events module, auth detection, factory wiring, config support, and model selector entry. However, it shipped with zero tests and missing integration in cron execution, workspace rules deployment, rule file sync, and the model selector's model-selection handler. This plan fills every gap identified by comparing OpenCode against the other three providers across all dimensions.

**Tech Stack:** Python 3.11+, pytest (asyncio_mode=auto), aiogram 3.x, Pydantic 2.x, asyncio

---

## Gap Summary

| Area | Status | Tasks |
|---|---|---|
| Provider + events tests | ZERO tests | Task 1-2 |
| Auth tests | ZERO tests | Task 3 |
| Factory tests | Missing OpenCode case | Task 4 |
| Orchestrator provider tests | Missing OpenCode cases | Task 5 |
| Cron/background execution | No `_build_opencode_cmd`, no parser | Task 6 |
| Workspace rules deployment | No `OPENCODE.md` in zone2/sync/selector | Task 7 |
| Cron task rule files | `_RULE_FILENAMES` missing `OPENCODE.md` | Task 8 |
| Skill sync | `_cli_skill_dirs()` missing opencode | Task 9 |
| Model selector handler | Falls through to Codex logic | Task 10 |

---

### Task 1: OpenCode Events Parser Tests

**Files:**
- Create: `tests/cli/test_opencode_events.py`
- Reference: `klir/cli/opencode_events.py`
- Reference: `tests/cli/test_codex_events.py` (pattern to follow)
- Reference: `tests/cli/test_gemini_events.py` (pattern to follow)

This task tests `parse_opencode_json()` and `parse_opencode_stream_event()` from `klir/cli/opencode_events.py`. The events module handles JSON line parsing, session ID extraction, usage extraction, text extraction, and event dispatch.

**Step 1: Write the test file with parse_opencode_json tests**

```python
"""Tests for OpenCode CLI JSON event parsing."""

from __future__ import annotations

import json

from klir.cli.opencode_events import parse_opencode_json, parse_opencode_stream_event
from klir.cli.stream_events import (
    AssistantTextDelta,
    ResultEvent,
    SystemInitEvent,
    ThinkingEvent,
    ToolUseEvent,
)


# ---------------------------------------------------------------------------
# parse_opencode_json
# ---------------------------------------------------------------------------


class TestParseOpenCodeJson:
    def test_empty_input(self) -> None:
        text, sid, usage = parse_opencode_json("")
        assert text == ""
        assert sid is None
        assert usage is None

    def test_plain_text_fallback(self) -> None:
        text, sid, usage = parse_opencode_json("Hello world")
        assert text == "Hello world"
        assert sid is None
        assert usage is None

    def test_multiline_plain_text(self) -> None:
        text, sid, usage = parse_opencode_json("line one\nline two")
        assert text == "line one\nline two"

    def test_json_with_result_field(self) -> None:
        data = json.dumps({"result": "The answer is 42."})
        text, sid, usage = parse_opencode_json(data)
        assert text == "The answer is 42."

    def test_json_with_text_field(self) -> None:
        data = json.dumps({"text": "Some text output"})
        text, sid, usage = parse_opencode_json(data)
        assert text == "Some text output"

    def test_json_with_content_field(self) -> None:
        data = json.dumps({"content": "Content value"})
        text, sid, usage = parse_opencode_json(data)
        assert text == "Content value"

    def test_session_id_extraction(self) -> None:
        data = json.dumps({"session_id": "sess-abc123", "text": "output"})
        text, sid, usage = parse_opencode_json(data)
        assert sid == "sess-abc123"

    def test_session_id_from_sessionId_key(self) -> None:
        data = json.dumps({"sessionId": "sess-xyz", "text": "output"})
        _, sid, _ = parse_opencode_json(data)
        assert sid == "sess-xyz"

    def test_session_id_from_id_key(self) -> None:
        data = json.dumps({"id": "sess-id-001", "text": "hi"})
        _, sid, _ = parse_opencode_json(data)
        assert sid == "sess-id-001"

    def test_first_session_id_wins(self) -> None:
        lines = "\n".join([
            json.dumps({"session_id": "first", "text": "a"}),
            json.dumps({"session_id": "second", "text": "b"}),
        ])
        _, sid, _ = parse_opencode_json(lines)
        assert sid == "first"

    def test_usage_from_result_event(self) -> None:
        data = json.dumps({
            "type": "result",
            "text": "done",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        _, _, usage = parse_opencode_json(data)
        assert usage == {"input_tokens": 100, "output_tokens": 50}

    def test_usage_from_stats_block(self) -> None:
        data = json.dumps({
            "text": "out",
            "stats": {"input_tokens": 200, "output_tokens": 80},
        })
        _, _, usage = parse_opencode_json(data)
        assert usage is not None
        assert usage["input_tokens"] == 200
        assert usage["output_tokens"] == 80

    def test_message_started_with_content_list(self) -> None:
        data = json.dumps({
            "type": "message.completed",
            "content": [
                {"type": "text", "text": "block one"},
                {"type": "text", "text": "block two"},
            ],
        })
        text, _, _ = parse_opencode_json(data)
        assert "block one" in text
        assert "block two" in text

    def test_message_part_updated_text(self) -> None:
        data = json.dumps({
            "type": "message.part.updated",
            "text": "partial update",
        })
        text, _, _ = parse_opencode_json(data)
        assert text == "partial update"

    def test_blank_lines_skipped(self) -> None:
        raw = "\n\n" + json.dumps({"text": "value"}) + "\n\n"
        text, _, _ = parse_opencode_json(raw)
        assert text == "value"

    def test_non_dict_json_treated_as_plain_text(self) -> None:
        raw = json.dumps([1, 2, 3])
        text, sid, usage = parse_opencode_json(raw)
        assert text == raw
        assert sid is None

    def test_empty_session_id_ignored(self) -> None:
        data = json.dumps({"session_id": "  ", "text": "ok"})
        _, sid, _ = parse_opencode_json(data)
        assert sid is None


# ---------------------------------------------------------------------------
# parse_opencode_stream_event
# ---------------------------------------------------------------------------


class TestParseOpenCodeStreamEvent:
    def test_empty_line(self) -> None:
        assert parse_opencode_stream_event("") == []
        assert parse_opencode_stream_event("   ") == []

    def test_plain_text_becomes_text_delta(self) -> None:
        events = parse_opencode_stream_event("Hello stream")
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)
        assert events[0].text == "Hello stream"

    def test_session_started_event(self) -> None:
        line = json.dumps({"type": "session.started", "session_id": "s-001"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], SystemInitEvent)
        assert events[0].session_id == "s-001"

    def test_session_created_event(self) -> None:
        line = json.dumps({"type": "session.created", "id": "s-002"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], SystemInitEvent)
        assert events[0].session_id == "s-002"

    def test_session_completed_event(self) -> None:
        line = json.dumps({
            "type": "session.completed",
            "text": "final",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].usage == {"input_tokens": 10, "output_tokens": 5}

    def test_message_completed_event(self) -> None:
        line = json.dumps({"type": "message.completed", "text": "done"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)

    def test_result_type_event(self) -> None:
        line = json.dumps({"type": "result", "text": "answer"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)

    def test_error_event(self) -> None:
        line = json.dumps({
            "type": "error",
            "error": {"message": "rate limited"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].is_error is True
        assert "rate limited" in events[0].result

    def test_session_failed_event(self) -> None:
        line = json.dumps({"type": "session.failed", "error": "timeout"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].is_error is True

    def test_message_part_updated_text_delta(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "text", "text": "chunk"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)
        assert events[0].text == "chunk"

    def test_message_delta_text(self) -> None:
        line = json.dumps({"type": "message.delta", "text": "delta text"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)

    def test_content_delta_text(self) -> None:
        line = json.dumps({"type": "content.delta", "content": "content val"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)

    def test_thinking_event(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "thinking", "text": "reasoning..."},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "reasoning..."

    def test_reasoning_event(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "reasoning", "text": "thinking hard"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)

    def test_tool_started_event(self) -> None:
        line = json.dumps({
            "type": "tool.started",
            "name": "bash",
            "parameters": {"command": "ls"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolUseEvent)
        assert events[0].tool_name == "bash"
        assert events[0].parameters == {"command": "ls"}

    def test_tool_use_event(self) -> None:
        line = json.dumps({
            "type": "tool_use",
            "tool_name": "read_file",
            "input": {"path": "/tmp/x"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolUseEvent)
        assert events[0].tool_name == "read_file"

    def test_tool_running_event(self) -> None:
        line = json.dumps({"type": "tool.running", "tool": "edit"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolUseEvent)
        assert events[0].tool_name == "edit"

    def test_unknown_event_type_returns_empty(self) -> None:
        line = json.dumps({"type": "internal.debug", "data": "foo"})
        events = parse_opencode_stream_event(line)
        assert events == []

    def test_tool_without_name_returns_empty(self) -> None:
        line = json.dumps({"type": "tool.started"})
        events = parse_opencode_stream_event(line)
        assert events == []

    def test_content_update_empty_text_returns_empty(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "text", "text": ""},
        })
        events = parse_opencode_stream_event(line)
        assert events == []
```

**Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/cli/test_opencode_events.py -v
```

Expected: All PASS (these test existing, already-implemented code).

**Step 3: Commit**

```bash
git add tests/cli/test_opencode_events.py
git commit -m "test(cli): Add OpenCode events parser tests"
```

---

### Task 2: OpenCode Provider Tests

**Files:**
- Create: `tests/cli/test_opencode_provider.py`
- Reference: `klir/cli/opencode_provider.py`
- Reference: `tests/cli/test_claude_provider.py` (pattern to follow)
- Reference: `tests/cli/test_gemini_provider.py` (pattern to follow)

This task tests `OpenCodeCLI` from `klir/cli/opencode_provider.py`. The provider wraps the `opencode` binary, builds commands, composes prompts, parses output, and handles streaming. We mock the subprocess layer (executor functions) and the `which("opencode")` call.

**Step 1: Write the test file**

```python
"""Tests for OpenCode CLI provider wrapper."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from klir.cli.base import CLIConfig
from klir.cli.opencode_provider import OpenCodeCLI, _StreamState
from klir.cli.stream_events import AssistantTextDelta, ResultEvent, SystemInitEvent
from klir.cli.types import CLIResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli() -> OpenCodeCLI:
    with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
        return OpenCodeCLI(CLIConfig(provider="opencode", model="anthropic/claude-sonnet-4"))


@pytest.fixture()
def cli_with_tools() -> OpenCodeCLI:
    with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
        return OpenCodeCLI(
            CLIConfig(
                provider="opencode",
                model="anthropic/claude-sonnet-4",
                allowed_tools=["bash", "read"],
                disallowed_tools=["write"],
            )
        )


@pytest.fixture()
def cli_with_system_prompt() -> OpenCodeCLI:
    with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
        return OpenCodeCLI(
            CLIConfig(
                provider="opencode",
                model="anthropic/claude-sonnet-4",
                system_prompt="You are helpful.",
                append_system_prompt="Be concise.",
            )
        )


# ---------------------------------------------------------------------------
# _find_cli
# ---------------------------------------------------------------------------


class TestFindCli:
    def test_raises_when_not_found(self) -> None:
        with (
            patch("klir.cli.opencode_provider.which", return_value=None),
            pytest.raises(FileNotFoundError, match="opencode CLI not found"),
        ):
            OpenCodeCLI(CLIConfig(provider="opencode"))

    def test_returns_path_when_found(self) -> None:
        with patch("klir.cli.opencode_provider.which", return_value="/usr/local/bin/opencode"):
            cli = OpenCodeCLI(CLIConfig(provider="opencode"))
        assert cli._cli == "/usr/local/bin/opencode"


# ---------------------------------------------------------------------------
# _compose_prompt
# ---------------------------------------------------------------------------


class TestComposePrompt:
    def test_plain_prompt(self, cli: OpenCodeCLI) -> None:
        result = cli._compose_prompt("Hello")
        assert result == "Hello"

    def test_with_system_prompts(self, cli_with_system_prompt: OpenCodeCLI) -> None:
        result = cli_with_system_prompt._compose_prompt("Hello")
        assert "You are helpful." in result
        assert "Hello" in result
        assert "Be concise." in result
        # Order: system, user, append
        parts = result.split("\n\n")
        assert parts[0] == "You are helpful."
        assert parts[1] == "Hello"
        assert parts[2] == "Be concise."


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------


class TestBuildCommand:
    def test_basic_command(self, cli: OpenCodeCLI) -> None:
        cmd = cli._build_command("test prompt")
        assert cmd[0] == "/usr/bin/opencode"
        assert "-p" in cmd
        assert "-q" in cmd
        assert "-f" in cmd
        assert "json" in cmd
        assert "-m" in cmd
        assert "anthropic/claude-sonnet-4" in cmd

    def test_resume_session_adds_continue_flag(self, cli: OpenCodeCLI) -> None:
        cmd = cli._build_command("test", resume_session="sess-123")
        assert "-c" in cmd

    def test_no_resume_no_continue_flag(self, cli: OpenCodeCLI) -> None:
        cmd = cli._build_command("test")
        assert "-c" not in cmd

    def test_json_output_disabled(self, cli: OpenCodeCLI) -> None:
        cmd = cli._build_command("test", json_output=False)
        assert "-f" not in cmd
        assert "json" not in cmd

    def test_tool_filtering(self, cli_with_tools: OpenCodeCLI) -> None:
        cmd = cli_with_tools._build_command("test")
        # Check allowed tools
        idx_allowed = cmd.index("--allowedTools")
        assert cmd[idx_allowed + 1] == "bash,read"
        # Check excluded tools
        idx_excluded = cmd.index("--excludedTools")
        assert cmd[idx_excluded + 1] == "write"

    def test_cli_parameters_appended(self) -> None:
        with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
            cli = OpenCodeCLI(
                CLIConfig(
                    provider="opencode",
                    model="openai/gpt-4o",
                    cli_parameters=["--verbose", "--no-cache"],
                )
            )
        cmd = cli._build_command("test")
        assert "--verbose" in cmd
        assert "--no-cache" in cmd

    def test_no_model_omits_flag(self) -> None:
        with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
            cli = OpenCodeCLI(CLIConfig(provider="opencode", model=""))
        cmd = cli._build_command("test")
        assert "-m" not in cmd


# ---------------------------------------------------------------------------
# _parse_output (static method)
# ---------------------------------------------------------------------------


class TestParseOutput:
    def test_empty_stdout(self) -> None:
        resp = OpenCodeCLI._parse_output(b"", b"", 0)
        assert resp.is_error is True
        assert resp.result == ""

    def test_json_output_with_result(self) -> None:
        data = json.dumps({
            "result": "The answer",
            "session_id": "s-42",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })
        resp = OpenCodeCLI._parse_output(data.encode(), b"", 0)
        assert resp.is_error is False
        assert resp.result == "The answer"
        assert resp.session_id == "s-42"
        assert resp.usage == {"input_tokens": 10, "output_tokens": 5}

    def test_nonzero_returncode_is_error(self) -> None:
        data = json.dumps({"result": "partial"})
        resp = OpenCodeCLI._parse_output(data.encode(), b"", 1)
        assert resp.is_error is True
        assert resp.returncode == 1

    def test_stderr_logged(self) -> None:
        data = json.dumps({"text": "ok"})
        resp = OpenCodeCLI._parse_output(data.encode(), b"warning msg", 0)
        assert resp.stderr == "warning msg"

    def test_plain_text_fallback(self) -> None:
        resp = OpenCodeCLI._parse_output(b"raw text output", b"", 0)
        assert "raw text output" in resp.result


# ---------------------------------------------------------------------------
# _StreamState
# ---------------------------------------------------------------------------


class TestStreamState:
    def test_tracks_session_id(self) -> None:
        state = _StreamState()
        event = SystemInitEvent(type="system", subtype="init", session_id="s-1")
        state.track(event)
        assert state.session_id == "s-1"

    def test_tracks_text_deltas(self) -> None:
        state = _StreamState()
        state.track(AssistantTextDelta(type="assistant", text="hello "))
        state.track(AssistantTextDelta(type="assistant", text="world"))
        assert state.accumulated_text == ["hello ", "world"]

    def test_first_session_id_wins(self) -> None:
        state = _StreamState()
        state.track(SystemInitEvent(type="system", subtype="init", session_id="first"))
        state.track(SystemInitEvent(type="system", subtype="init", session_id="second"))
        assert state.session_id == "first"


# ---------------------------------------------------------------------------
# send (integration-level with mocked executor)
# ---------------------------------------------------------------------------


class TestSend:
    async def test_send_calls_executor(self, cli: OpenCodeCLI) -> None:
        mock_response = CLIResponse(result="response text", session_id="s-1")
        with patch(
            "klir.cli.opencode_provider.run_oneshot_subprocess",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_exec:
            result = await cli.send("test prompt")
        assert result.result == "response text"
        mock_exec.assert_called_once()

    async def test_send_with_continue_session(self, cli: OpenCodeCLI) -> None:
        mock_response = CLIResponse(result="continued")
        with patch(
            "klir.cli.opencode_provider.run_oneshot_subprocess",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await cli.send("follow up", continue_session=True)
        assert result.result == "continued"

    async def test_send_with_resume_session(self, cli: OpenCodeCLI) -> None:
        mock_response = CLIResponse(result="resumed")
        with patch(
            "klir.cli.opencode_provider.run_oneshot_subprocess",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await cli.send("follow up", resume_session="sess-old")
        assert result.result == "resumed"


# ---------------------------------------------------------------------------
# send_streaming (integration-level with mocked executor)
# ---------------------------------------------------------------------------


class TestSendStreaming:
    async def test_streaming_yields_events(self, cli: OpenCodeCLI) -> None:
        events = [
            SystemInitEvent(type="system", subtype="init", session_id="s-1"),
            AssistantTextDelta(type="assistant", text="hello"),
            ResultEvent(type="result", result="hello", session_id="s-1"),
        ]

        async def mock_streaming(*args, **kwargs):
            for event in events:
                yield event

        with patch(
            "klir.cli.opencode_provider.run_streaming_subprocess",
            side_effect=mock_streaming,
        ):
            collected = []
            async for event in cli.send_streaming("prompt"):
                collected.append(event)

        assert len(collected) == 3
        assert isinstance(collected[0], SystemInitEvent)
        assert isinstance(collected[1], AssistantTextDelta)
        assert isinstance(collected[2], ResultEvent)
```

**Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/cli/test_opencode_provider.py -v
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add tests/cli/test_opencode_provider.py
git commit -m "test(cli): Add OpenCode provider tests"
```

---

### Task 3: OpenCode Auth Tests

**Files:**
- Modify: `tests/cli/test_auth.py` (append new tests)
- Modify: `tests/cli/test_auth_extended.py` (add `check_all_auth` OpenCode assertion)
- Reference: `klir/cli/auth.py:398-427` (`check_opencode_auth`)

The auth function `check_opencode_auth()` exists but has zero test coverage. It checks: config file at `$XDG_CONFIG_HOME/opencode/opencode.json`, env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`) + `which("opencode")`, and binary presence.

**Step 1: Add OpenCode auth tests to `tests/cli/test_auth.py`**

Add the following imports at the top of `tests/cli/test_auth.py`:

```python
from klir.cli.auth import check_opencode_auth
```

Add at the import line where `check_gemini_auth` is imported (line 13), append `check_opencode_auth`:

Existing line 8-16:
```python
from klir.cli.auth import (
    AuthResult,
    AuthStatus,
    check_claude_auth,
    check_codex_auth,
    check_gemini_auth,
    format_age,
    gemini_uses_api_key_mode,
)
```

Change to:
```python
from klir.cli.auth import (
    AuthResult,
    AuthStatus,
    check_claude_auth,
    check_codex_auth,
    check_gemini_auth,
    check_opencode_auth,
    format_age,
    gemini_uses_api_key_mode,
)
```

Then append these test functions at the end of the file:

```python
# -- OpenCode auth --


def test_check_opencode_auth_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("shutil.which", lambda x: None)
    result = check_opencode_auth()
    assert result.status == AuthStatus.NOT_FOUND


def test_check_opencode_auth_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    import klir.cli.auth as _auth_mod
    monkeypatch.setattr(_auth_mod, "which", lambda x: "/usr/bin/opencode")
    result = check_opencode_auth()
    assert result.status == AuthStatus.INSTALLED


def test_check_opencode_auth_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    (config_dir / "opencode.json").write_text('{"provider":"anthropic"}')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    result = check_opencode_auth()
    assert result.status == AuthStatus.AUTHENTICATED
    assert result.auth_file is not None


def test_check_opencode_auth_env_key_anthropic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import klir.cli.auth as _auth_mod
    monkeypatch.setattr(_auth_mod, "which", lambda x: "/usr/bin/opencode")
    result = check_opencode_auth()
    assert result.status == AuthStatus.AUTHENTICATED


def test_check_opencode_auth_env_key_openai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    import klir.cli.auth as _auth_mod
    monkeypatch.setattr(_auth_mod, "which", lambda x: "/usr/bin/opencode")
    result = check_opencode_auth()
    assert result.status == AuthStatus.AUTHENTICATED


def test_check_opencode_auth_env_key_without_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import klir.cli.auth as _auth_mod
    monkeypatch.setattr(_auth_mod, "which", lambda x: None)
    result = check_opencode_auth()
    assert result.status == AuthStatus.NOT_FOUND
```

**Step 2: Update `test_auth_extended.py` to assert OpenCode in `check_all_auth`**

In `tests/cli/test_auth_extended.py`, update the `test_check_all_auth_returns_both` test to also assert `"opencode"` is present:

Change:
```python
    assert "claude" in results
    assert "codex" in results
```

To:
```python
    assert "claude" in results
    assert "codex" in results
    assert "opencode" in results
```

**Step 3: Run tests**

```bash
uv run pytest tests/cli/test_auth.py tests/cli/test_auth_extended.py -v
```

Expected: All PASS.

**Step 4: Commit**

```bash
git add tests/cli/test_auth.py tests/cli/test_auth_extended.py
git commit -m "test(cli): Add OpenCode auth detection tests"
```

---

### Task 4: Factory Test for OpenCode

**Files:**
- Modify: `tests/cli/test_factory.py` (add one test)
- Reference: `klir/cli/factory.py:25-28`

**Step 1: Add OpenCode import and test**

Add import at top of `tests/cli/test_factory.py`:

```python
from klir.cli.opencode_provider import OpenCodeCLI
```

Add test function at end of file:

```python
def test_create_cli_returns_opencode() -> None:
    with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
        cli = create_cli(CLIConfig(provider="opencode"))
    assert isinstance(cli, OpenCodeCLI)
```

**Step 2: Run tests**

```bash
uv run pytest tests/cli/test_factory.py -v
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add tests/cli/test_factory.py
git commit -m "test(cli): Add OpenCode factory wiring test"
```

---

### Task 5: Orchestrator Provider Tests for OpenCode

**Files:**
- Modify: `tests/orchestrator/test_providers.py` (add test methods)
- Reference: `klir/orchestrator/providers.py`

Add tests covering OpenCode in the existing test classes. The `ProviderManager` already handles OpenCode in production code but has zero test coverage for it.

**Step 1: Add OpenCode test cases**

Add to `TestResolveRuntimeTarget`:

```python
    def test_opencode_model(self) -> None:
        pm = _pm()
        model, provider = pm.resolve_runtime_target("anthropic/claude-sonnet-4")
        assert model == "anthropic/claude-sonnet-4"
        assert provider == "opencode"
```

Add to `TestResolveSessionDirective`:

```python
    def test_provider_name_opencode(self) -> None:
        pm = _pm()
        result = pm.resolve_session_directive("opencode")
        assert result is not None
        assert result[0] == "opencode"
        assert result[1] == ""  # opencode default is empty

    def test_slash_model_resolves_to_opencode(self) -> None:
        pm = _pm()
        result = pm.resolve_session_directive("openai/gpt-4o")
        # slash models are not in known_model_ids, so this returns None
        # unless we check the ModelRegistry. The ModelRegistry.provider_for
        # handles slash format, but resolve_session_directive checks
        # is_known_model first which does not know slash models.
        # This documents current behavior.
        assert result is None
```

Add to `TestIsKnownModel`:

```python
    def test_opencode_slash_model_not_in_known(self) -> None:
        pm = _pm()
        # Slash models are not in _known_model_ids (they're validated by CLI).
        assert pm.is_known_model("anthropic/claude-sonnet-4") is False
```

Add to `TestDefaultModelForProvider`:

```python
    def test_opencode(self) -> None:
        pm = _pm()
        assert pm.default_model_for_provider("opencode") == ""
```

Add to `TestActiveProviderName`:

```python
    def test_opencode(self) -> None:
        pm = _pm(model="anthropic/claude-sonnet-4", provider="opencode")
        assert pm.active_provider_name == "OpenCode"
```

Add to `TestApplyAuthResults`:

```python
    def test_opencode_authenticated(self) -> None:
        pm = _pm()
        cli_service = MagicMock()

        auth_status = MagicMock()
        auth_status.AUTHENTICATED = "auth"
        auth_status.INSTALLED = "inst"

        results = {}
        for name in ("claude", "codex", "gemini", "opencode"):
            r = MagicMock()
            r.status = "auth"
            r.is_authenticated = True
            results[name] = r

        pm.apply_auth_results(
            results,
            auth_status_enum=auth_status,
            cli_service=cli_service,
        )
        assert "opencode" in pm.available_providers
        assert pm.available_providers == frozenset({"claude", "codex", "gemini", "opencode"})
```

**Step 2: Run tests**

```bash
uv run pytest tests/orchestrator/test_providers.py -v
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add tests/orchestrator/test_providers.py
git commit -m "test(orchestrator): Add OpenCode provider manager tests"
```

---

### Task 6: Cron/Background Execution Support

**Files:**
- Modify: `klir/cron/execution.py:21` (add import)
- Modify: `klir/cron/execution.py` (add `_build_opencode_cmd`, `parse_opencode_result`, register in dicts)
- Create: `tests/cron/test_opencode_execution.py`
- Reference: `klir/cli/opencode_events.py:21-43` (`parse_opencode_json`)

The cron execution module builds one-shot CLI commands for scheduled tasks. OpenCode is completely absent: no builder, no parser, not registered in `_CMD_BUILDERS` or `_RESULT_PARSERS`. When an OpenCode cron task runs, it falls through to the default `_build_claude_cmd` which is wrong.

**Step 1: Add the import**

At top of `klir/cron/execution.py`, after line 14 (`from klir.cli.gemini_utils import find_gemini_cli`), add:

```python
from klir.cli.opencode_events import parse_opencode_json
```

**Step 2: Add `parse_opencode_result` function**

After `parse_codex_result` (after line 91), add:

```python
def parse_opencode_result(stdout: bytes) -> str:
    """Extract result text from OpenCode CLI JSON output."""
    if not stdout:
        return ""
    raw = stdout.decode(errors="replace").strip()
    if not raw:
        return ""
    result_text, _session_id, _usage = parse_opencode_json(raw)
    return result_text or raw[:2000]
```

**Step 3: Add `_build_opencode_cmd` function**

After `_build_codex_cmd` (after line 182), add:

```python
def _build_opencode_cmd(exec_config: TaskExecutionConfig, prompt: str) -> OneShotCommand | None:
    """Build an OpenCode CLI command for one-shot cron execution."""
    cli = which("opencode")
    if not cli:
        return None
    cmd = [cli, "-p", prompt, "-q", "-f", "json"]

    if exec_config.model:
        cmd += ["-m", exec_config.model]

    # Add tool filtering
    if exec_config.allowed_tools:
        cmd += ["--allowedTools", ",".join(exec_config.allowed_tools)]
    if exec_config.disallowed_tools:
        cmd += ["--excludedTools", ",".join(exec_config.disallowed_tools)]

    # Add extra CLI parameters
    cmd.extend(exec_config.cli_parameters)
    return OneShotCommand(cmd=cmd)
```

**Step 4: Register in lookup dicts**

Update `_CMD_BUILDERS` (line 188-192) to add `"opencode"`:

```python
_CMD_BUILDERS: dict[str, _CmdBuilder] = {
    "claude": _build_claude_cmd,
    "gemini": _build_gemini_cmd,
    "codex": _build_codex_cmd,
    "opencode": _build_opencode_cmd,
}
```

Update `_RESULT_PARSERS` (line 194-198) to add `"opencode"`:

```python
_RESULT_PARSERS: dict[str, _ResultParser] = {
    "claude": parse_claude_result,
    "gemini": parse_gemini_result,
    "codex": parse_codex_result,
    "opencode": parse_opencode_result,
}
```

**Step 5: Write tests**

Create `tests/cron/test_opencode_execution.py`:

```python
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
    defaults.update(overrides)
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
```

**Step 6: Run tests**

```bash
uv run pytest tests/cron/test_opencode_execution.py -v
```

Expected: All PASS.

**Step 7: Commit**

```bash
git add klir/cron/execution.py tests/cron/test_opencode_execution.py
git commit -m "feat(cron): Add OpenCode command builder and result parser"
```

---

### Task 7: Workspace Rules Deployment for OpenCode

**Files:**
- Modify: `klir/workspace/init.py:22` (add `OPENCODE.md` to `_ZONE2_FILES`)
- Modify: `klir/workspace/init.py:159` (add `OPENCODE.md` to `_RULE_FILE_NAMES`)
- Modify: `klir/workspace/init.py:106-110` (add OPENCODE.md mirror in zone2 handler)
- Modify: `klir/workspace/rules_selector.py` (add `_opencode_authenticated`, add variant logic, deploy OPENCODE.md, cleanup stale)

The workspace rules system deploys `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` based on which providers are authenticated. OpenCode needs an `OPENCODE.md` file to follow the same pattern.

**Step 1: Update `_ZONE2_FILES` in `klir/workspace/init.py`**

Change line 22:
```python
_ZONE2_FILES = frozenset({"CLAUDE.md", "AGENTS.md", "GEMINI.md"})
```
To:
```python
_ZONE2_FILES = frozenset({"CLAUDE.md", "AGENTS.md", "GEMINI.md", "OPENCODE.md"})
```

**Step 2: Update `_RULE_FILE_NAMES` in `klir/workspace/init.py`**

Change line 159:
```python
_RULE_FILE_NAMES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")
```
To:
```python
_RULE_FILE_NAMES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "OPENCODE.md")
```

**Step 3: Update `_handle_zone2_file` to create OPENCODE.md mirror**

In `klir/workspace/init.py`, change lines 105-110:

```python
    # Auto-create mirrors for every CLAUDE.md (AGENTS.md + GEMINI.md)
    if entry.name == "CLAUDE.md":
        for mirror_name in ("AGENTS.md", "GEMINI.md"):
            mirror_target = dst / mirror_name
            _copy_with_symlink_check(entry, mirror_target)
            logger.debug("Zone 2 copy: %s", mirror_target)
```

To:

```python
    # Auto-create mirrors for every CLAUDE.md (AGENTS.md + GEMINI.md + OPENCODE.md)
    if entry.name == "CLAUDE.md":
        for mirror_name in ("AGENTS.md", "GEMINI.md", "OPENCODE.md"):
            mirror_target = dst / mirror_name
            _copy_with_symlink_check(entry, mirror_target)
            logger.debug("Zone 2 copy: %s", mirror_target)
```

**Step 4: Update `RulesSelector` in `klir/workspace/rules_selector.py`**

Add OpenCode auth detection. Change the `__init__` method (lines 37-55) to also check opencode:

After line 55 (`self._gemini_authenticated = ...`), add:

```python
        opencode_result = auth.get("opencode")
        self._opencode_authenticated = (
            opencode_result.status == AuthStatus.AUTHENTICATED if opencode_result else False
        )
```

Update `_authenticated_count` property (lines 57-66) to include opencode:

```python
    @property
    def _authenticated_count(self) -> int:
        """Number of authenticated providers."""
        return sum(
            (
                self._claude_authenticated,
                self._codex_authenticated,
                self._gemini_authenticated,
                self._opencode_authenticated,
            )
        )
```

Update `get_variant_suffix` (lines 68-84): add opencode-only case. The existing logic returns `"all-clis"` if 2+ providers are authenticated, which already covers opencode correctly. No change needed for the variant selection since OpenCode uses the same rule templates.

Update `deploy_rules` (after line 194), add OPENCODE.md deployment:

After the GEMINI.md block:
```python
                # Deploy OPENCODE.md if OpenCode is authenticated
                if self._opencode_authenticated:
                    opencode_dst = dst_dir / "OPENCODE.md"
                    shutil.copy2(template, opencode_dst)
                    deployed_count += 1
                    logger.debug("Deployed: %s -> OPENCODE.md", template.name)
```

Update the log line (line 199-205) to include opencode:

```python
        logger.info(
            "Deployed %d rule files (Claude=%s, Codex=%s, Gemini=%s, OpenCode=%s)",
            deployed_count,
            self._claude_authenticated,
            self._codex_authenticated,
            self._gemini_authenticated,
            self._opencode_authenticated,
        )
```

Update `_cleanup_stale_files` (lines 210-223) to include opencode:

Add to the stale list:
```python
        if not self._opencode_authenticated:
            stale.append(("OPENCODE.md", "OpenCode"))
```

**Step 5: Run existing tests to verify no regressions**

```bash
uv run pytest tests/ -v -k "workspace or rules"
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add klir/workspace/init.py klir/workspace/rules_selector.py
git commit -m "feat(workspace): Add OPENCODE.md rules deployment and sync"
```

---

### Task 8: Cron Task Rule Files for OpenCode

**Files:**
- Modify: `klir/workspace/cron_tasks.py:16` (add `OPENCODE.md` to `_RULE_FILENAMES`)

The cron task folder creation and `ensure_task_rule_files` function uses a hardcoded tuple of rule filenames that does not include `OPENCODE.md`.

**Step 1: Update the tuple**

Change line 16 in `klir/workspace/cron_tasks.py`:

```python
_RULE_FILENAMES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")
```

To:

```python
_RULE_FILENAMES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "OPENCODE.md")
```

**Step 2: Run tests**

```bash
uv run pytest tests/ -v -k "cron_task"
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add klir/workspace/cron_tasks.py
git commit -m "feat(workspace): Include OPENCODE.md in cron task rule files"
```

---

### Task 9: Skill Sync for OpenCode

**Files:**
- Modify: `klir/workspace/skill_sync.py:70-86` (`_cli_skill_dirs`)

The skill sync system creates symlinks between `~/.klir/workspace/skills`, `~/.claude/skills`, `~/.codex/skills`, and `~/.gemini/skills`. OpenCode is missing. Its home directory is `~/.config/opencode` (XDG-based), so the skills directory would be `~/.config/opencode/skills` if OpenCode supports skills.

**Step 1: Add OpenCode to `_cli_skill_dirs`**

In `klir/workspace/skill_sync.py`, update `_cli_skill_dirs()` (lines 70-86). After the gemini block (line 85), add:

```python
    opencode_base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    opencode_home = opencode_base / "opencode"
    if opencode_home.is_dir():
        dirs["opencode"] = opencode_home / "skills"
```

Also update the priority order in `sync_skills` (line 238):

Change:
```python
    priority = ("klir", "claude", "codex", "gemini")
```

To:
```python
    priority = ("klir", "claude", "codex", "gemini", "opencode")
```

**Step 2: Run tests**

```bash
uv run pytest tests/ -v -k "skill"
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add klir/workspace/skill_sync.py
git commit -m "feat(workspace): Add OpenCode to skill directory sync"
```

---

### Task 10: Model Selector Fix for OpenCode

**Files:**
- Modify: `klir/orchestrator/selectors/model_selector.py:396-428` (`_handle_model_selected`)

When an OpenCode model is selected in the model selector wizard, `_handle_model_selected` checks if the provider is `"claude"` or `"gemini"` (direct switch), otherwise falls through to Codex reasoning-effort logic. This means selecting an OpenCode model shows a "Thinking level" prompt which is wrong for OpenCode.

**Step 1: Fix `_handle_model_selected`**

In `klir/orchestrator/selectors/model_selector.py`, change lines 402-407:

```python
    if provider in ("claude", "gemini"):
        result = await switch_model(orch, key, model_id)
        return SelectorResponse(text=result)
```

To:

```python
    if provider in ("claude", "gemini", "opencode"):
        result = await switch_model(orch, key, model_id)
        return SelectorResponse(text=result)
```

**Step 2: Run tests**

```bash
uv run pytest tests/orchestrator/test_model_selector.py -v
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add klir/orchestrator/selectors/model_selector.py
git commit -m "fix(orchestrator): Route OpenCode model selection correctly"
```

---

### Task 11: Final Validation

**Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All PASS, no regressions.

**Step 2: Run linting and type checks**

```bash
uv run ruff format .
uv run ruff check .
uv run mypy klir
```

Expected: Clean output.

**Step 3: Fix any issues found**

Address any linting, formatting, or type errors.

**Step 4: Final commit if needed**

```bash
git add -u
git commit -m "style: Fix formatting from OpenCode parity changes"
```
