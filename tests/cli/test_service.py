"""Tests for CLIService gateway."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from klir.cli.process_registry import ProcessRegistry
from klir.cli.service import CLIService, CLIServiceConfig
from klir.cli.stream_events import StreamEvent
from klir.cli.types import AgentRequest, CLIResponse
from klir.config import ModelRegistry


def _make_service(**overrides: Any) -> CLIService:
    config = CLIServiceConfig(
        working_dir=overrides.pop("working_dir", "/tmp"),
        default_model=overrides.pop("default_model", "opus"),
        provider=overrides.pop("provider", "claude"),
        max_turns=overrides.pop("max_turns", None),
        max_budget_usd=overrides.pop("max_budget_usd", None),
        permission_mode=overrides.pop("permission_mode", "bypassPermissions"),
    )
    models = ModelRegistry()

    return CLIService(
        config=config,
        models=models,
        available_providers=frozenset({"claude"}),
        process_registry=ProcessRegistry(),
    )


async def test_execute_returns_agent_response() -> None:
    svc = _make_service()
    mock_response = CLIResponse(
        result="Hello!",
        session_id="sess-1",
        total_cost_usd=0.05,
        usage={"input_tokens": 500, "output_tokens": 200},
    )
    with patch("klir.cli.service.create_cli") as mock_create:
        mock_cli = AsyncMock()
        mock_cli.send.return_value = mock_response
        mock_create.return_value = mock_cli

        resp = await svc.execute(AgentRequest(prompt="hello", chat_id=1))

    assert resp.result == "Hello!"
    assert resp.session_id == "sess-1"
    assert resp.cost_usd == 0.05
    assert resp.is_error is False


async def test_execute_error_response() -> None:
    svc = _make_service()
    mock_response = CLIResponse(result="Error occurred", is_error=True)
    with patch("klir.cli.service.create_cli") as mock_create:
        mock_cli = AsyncMock()
        mock_cli.send.return_value = mock_response
        mock_create.return_value = mock_cli

        resp = await svc.execute(AgentRequest(prompt="fail", chat_id=1))

    assert resp.is_error is True
    assert resp.result == "Error occurred"


async def test_execute_streaming_success() -> None:
    svc = _make_service()

    from klir.cli.stream_events import AssistantTextDelta, ResultEvent

    async def fake_stream(*_args: Any, **_kwargs: Any) -> AsyncGenerator[StreamEvent, None]:
        yield AssistantTextDelta(type="assistant", text="Hello ")
        yield AssistantTextDelta(type="assistant", text="world!")
        yield ResultEvent(
            type="result",
            session_id="sess-1",
            result="Hello world!",
            total_cost_usd=0.03,
            usage={"input_tokens": 100, "output_tokens": 50},
        )

    deltas: list[str] = []

    async def on_delta(text: str) -> None:
        deltas.append(text)

    with patch("klir.cli.service.create_cli") as mock_create:
        mock_cli = MagicMock()
        mock_cli.send_streaming = fake_stream
        mock_create.return_value = mock_cli

        resp = await svc.execute_streaming(
            AgentRequest(prompt="hello", chat_id=1),
            on_text_delta=on_delta,
        )

    assert resp.result == "Hello world!"
    assert resp.session_id == "sess-1"
    assert deltas == ["Hello ", "world!"]


async def test_execute_streaming_fallback_on_error() -> None:
    svc = _make_service()

    mock_response = CLIResponse(result="Fallback result", session_id="sess-2")
    with patch("klir.cli.service.create_cli") as mock_create:
        mock_cli = MagicMock()
        mock_cli.send_streaming = MagicMock(side_effect=RuntimeError("Stream broken"))
        mock_cli.send = AsyncMock(return_value=mock_response)
        mock_create.return_value = mock_cli

        resp = await svc.execute_streaming(AgentRequest(prompt="hello", chat_id=1))

    assert resp.stream_fallback is True
    assert resp.result == "Fallback result"


def test_update_default_model() -> None:
    svc = _make_service()
    svc.update_default_model("sonnet")
    assert svc._config.default_model == "sonnet"


def test_update_available_providers() -> None:
    svc = _make_service()
    svc.update_available_providers(frozenset({"claude", "codex"}))
    assert svc._available_providers == frozenset({"claude", "codex"})


async def test_stream_callbacks_detects_tool_loop() -> None:
    from klir.cli.service import _StreamCallbacks
    from klir.cli.stream_events import ToolUseEvent

    from klir.cli.tool_activity import ToolActivity

    tools_seen: list[ToolActivity] = []

    async def on_tool(activity: ToolActivity) -> None:
        tools_seen.append(activity)

    cb = _StreamCallbacks(on_text=None, on_tool=on_tool, on_status=None, loop_threshold=3)

    for _ in range(2):
        _, result = await cb.dispatch(ToolUseEvent(type="assistant", tool_name="Bash"))
        assert result is None

    _, result = await cb.dispatch(ToolUseEvent(type="assistant", tool_name="Bash"))
    assert result is not None
    assert result.is_error is True
    assert "loop" in result.result.lower()
    assert len(tools_seen) == 3  # callback still fires before detection


async def test_stream_callbacks_no_loop_when_disabled() -> None:
    from klir.cli.service import _StreamCallbacks
    from klir.cli.stream_events import ToolUseEvent

    cb = _StreamCallbacks(on_text=None, on_tool=None, on_status=None, loop_threshold=0)

    for _ in range(20):
        _, result = await cb.dispatch(ToolUseEvent(type="assistant", tool_name="Bash"))
        assert result is None
