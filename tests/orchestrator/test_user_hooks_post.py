"""Post-hook modifies CLI response text."""

from __future__ import annotations

from unittest.mock import AsyncMock

from klir.cli.types import AgentResponse
from klir.config import UserMessageHookConfig
from klir.orchestrator.core import Orchestrator
from klir.orchestrator.flows import normal
from klir.session.key import SessionKey


def _resp(**kw: object) -> AgentResponse:
    defaults: dict[str, object] = {
        "result": "AI response",
        "session_id": "s1",
        "is_error": False,
        "cost_usd": 0.01,
        "total_tokens": 100,
    }
    defaults.update(kw)
    return AgentResponse(**defaults)  # type: ignore[arg-type]


async def test_post_hook_appends_to_response(orch: Orchestrator) -> None:
    orch._config.message_hooks = [
        UserMessageHookConfig(name="footer", phase="post", action="append", text="\n---"),
    ]
    orch._rebuild_user_hooks()

    mock_exec = AsyncMock(return_value=_resp())
    object.__setattr__(orch._cli_service, "execute", mock_exec)

    result = await normal(orch, SessionKey(chat_id=1), "hello")
    assert result.text.endswith("\n---")
