"""Integration: user hooks fire through normal flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from klir.cli.types import AgentResponse
from klir.config import UserMessageHookConfig
from klir.orchestrator.core import Orchestrator
from klir.orchestrator.flows import normal
from klir.session.key import SessionKey


def _resp(**kw: object) -> AgentResponse:
    defaults: dict[str, object] = {
        "result": "AI says hello",
        "session_id": "s1",
        "is_error": False,
        "cost_usd": 0.01,
        "total_tokens": 100,
    }
    defaults.update(kw)
    return AgentResponse(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def orch_with_hooks(orch: Orchestrator) -> Orchestrator:
    """Orchestrator with a pre-hook configured."""
    orch._config.message_hooks = [
        UserMessageHookConfig(name="tag", phase="pre", action="prepend", text="[USER] "),
    ]
    orch._rebuild_user_hooks()
    return orch


async def test_pre_hook_modifies_prompt(orch_with_hooks: Orchestrator) -> None:
    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch_with_hooks._cli_service, "execute", mock_exec)

    await normal(orch_with_hooks, SessionKey(chat_id=1), "hello")

    request = mock_exec.call_args[0][0]
    assert request.prompt.startswith("[USER] hello")
