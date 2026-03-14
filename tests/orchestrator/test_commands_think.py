"""Tests for /think command."""

from __future__ import annotations

from unittest.mock import AsyncMock

from klir.cli.types import AgentResponse
from klir.orchestrator.commands import THINKING_LEVELS, cmd_think
from klir.orchestrator.core import Orchestrator
from klir.orchestrator.flows import normal
from klir.session.key import SessionKey


def _resp(**kw: object) -> AgentResponse:
    defaults: dict[str, object] = {
        "result": "OK",
        "session_id": "s1",
        "is_error": False,
        "cost_usd": 0.01,
        "total_tokens": 100,
    }
    defaults.update(kw)
    return AgentResponse(**defaults)  # type: ignore[arg-type]


async def test_think_shows_current_level(orch: Orchestrator) -> None:
    """No arg shows current thinking level."""
    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch._cli_service, "execute", mock_exec)
    await normal(orch, SessionKey(chat_id=1), "hello")

    result = await cmd_think(orch, SessionKey(chat_id=1), "/think")
    assert result is not None
    assert "thinking" in result.text.lower()


async def test_think_sets_level(orch: Orchestrator) -> None:
    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch._cli_service, "execute", mock_exec)
    await normal(orch, SessionKey(chat_id=1), "hello")

    result = await cmd_think(orch, SessionKey(chat_id=1), "/think high")
    assert result is not None
    assert "high" in result.text.lower()

    # Verify session was updated
    session = await orch._sessions.get_active(SessionKey(chat_id=1))
    assert session is not None
    assert session.thinking_level == "high"


async def test_think_rejects_invalid_level(orch: Orchestrator) -> None:
    result = await cmd_think(orch, SessionKey(chat_id=1), "/think turbo")
    assert result is not None
    assert "invalid" in result.text.lower() or "valid" in result.text.lower()


async def test_think_off_clears_level(orch: Orchestrator) -> None:
    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch._cli_service, "execute", mock_exec)
    await normal(orch, SessionKey(chat_id=1), "hello")

    await cmd_think(orch, SessionKey(chat_id=1), "/think high")
    await cmd_think(orch, SessionKey(chat_id=1), "/think off")

    session = await orch._sessions.get_active(SessionKey(chat_id=1))
    assert session is not None
    assert session.thinking_level is None


async def test_thinking_levels_constant() -> None:
    """THINKING_LEVELS contains expected values."""
    assert "high" in THINKING_LEVELS
    assert "low" in THINKING_LEVELS
    assert "off" in THINKING_LEVELS
