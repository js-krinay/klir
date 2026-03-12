"""Tests for OpenCode CLI provider wrapper."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from klir.cli.base import CLIConfig
from klir.cli.opencode_provider import OpenCodeCLI, _StreamState
from klir.cli.stream_events import (
    AssistantTextDelta,
    ResultEvent,
    StreamEvent,
    SystemInitEvent,
)
from klir.cli.types import CLIResponse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli() -> OpenCodeCLI:
    with patch.object(OpenCodeCLI, "_find_cli", return_value="/usr/bin/opencode"):
        return OpenCodeCLI(CLIConfig(provider="opencode", model="anthropic/claude-sonnet-4"))


@pytest.fixture
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


@pytest.fixture
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

    def test_last_session_id_wins(self) -> None:
        state = _StreamState()
        state.track(SystemInitEvent(type="system", subtype="init", session_id="first"))
        state.track(SystemInitEvent(type="system", subtype="init", session_id="second"))
        assert state.session_id == "second"


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
        expected_events = [
            SystemInitEvent(type="system", subtype="init", session_id="s-1"),
            AssistantTextDelta(type="assistant", text="hello"),
            ResultEvent(type="result", result="hello", session_id="s-1"),
        ]

        async def mock_streaming(
            **_kw: object,
        ) -> AsyncGenerator[StreamEvent, None]:
            for event in expected_events:
                yield event

        with patch(
            "klir.cli.opencode_provider.run_streaming_subprocess",
            side_effect=mock_streaming,
        ):
            collected = [event async for event in cli.send_streaming("prompt")]

        assert len(collected) == 3
        assert isinstance(collected[0], SystemInitEvent)
        assert isinstance(collected[1], AssistantTextDelta)
        assert isinstance(collected[2], ResultEvent)
