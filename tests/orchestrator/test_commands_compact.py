"""Tests for /compact command."""

from __future__ import annotations

from unittest.mock import AsyncMock

from klir.cli.types import AgentResponse
from klir.orchestrator.commands import cmd_compact
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


async def test_compact_no_session(orch: Orchestrator) -> None:
    """Compact with no active session returns helpful message."""
    result = await cmd_compact(orch, SessionKey(chat_id=1), "/compact")
    assert result is not None
    assert "no active session" in result.text.lower()


async def test_compact_dispatches_to_cli(orch: Orchestrator) -> None:
    """Compact sends a summarization prompt to the active session."""
    mock_exec = AsyncMock(return_value=_resp(result="Session compacted."))
    object.__setattr__(orch._cli_service, "execute", mock_exec)

    # Create a session first
    await normal(orch, SessionKey(chat_id=1), "hello")

    result = await cmd_compact(orch, SessionKey(chat_id=1), "/compact")
    assert result is not None
    # The compact command should have called execute with the summarization prompt
    last_call = mock_exec.call_args_list[-1]
    request = last_call[0][0]
    assert "compact" in request.prompt.lower() or "summar" in request.prompt.lower()
