"""Tests: thinking_level flows through to CLI request."""

from __future__ import annotations

from unittest.mock import AsyncMock

from klir.cli.types import AgentResponse
from klir.orchestrator.commands import cmd_think
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


async def test_thinking_level_passed_in_request(orch: Orchestrator) -> None:
    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch._cli_service, "execute", mock_exec)

    # Create session and set thinking level
    await normal(orch, SessionKey(chat_id=1), "hello")
    await cmd_think(orch, SessionKey(chat_id=1), "/think high")

    # Next message should carry thinking_level
    await normal(orch, SessionKey(chat_id=1), "think hard")
    last_request = mock_exec.call_args_list[-1][0][0]
    assert last_request.thinking_level == "high"


async def test_no_thinking_level_when_off(orch: Orchestrator) -> None:
    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch._cli_service, "execute", mock_exec)

    await normal(orch, SessionKey(chat_id=1), "hello")
    last_request = mock_exec.call_args[0][0]
    assert last_request.thinking_level is None
