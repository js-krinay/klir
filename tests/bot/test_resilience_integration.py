"""Integration test: full retry pipeline through ResilientSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramServerError


class TestResilienceIntegration:
    @pytest.mark.asyncio
    async def test_resilient_session_retries_server_error(self) -> None:
        """ResilientSession.make_request retries on 5xx then succeeds."""
        from klir.bot.session_factory import ResilientSession
        from klir.config import ResilienceConfig

        cfg = ResilienceConfig(max_retries=2, base_backoff_seconds=0.01, max_backoff_seconds=0.1)
        session = ResilientSession(resilience_config=cfg)

        mock_response = MagicMock()

        with patch.object(
            type(session).__bases__[0],
            "make_request",
            new=AsyncMock(
                side_effect=[
                    TelegramServerError(method=None, message="500"),  # type: ignore[arg-type]
                    mock_response,
                ]
            ),
        ):
            result: object = await session.make_request(
                bot=MagicMock(), method=MagicMock(), timeout=None
            )
            assert result is mock_response

    @pytest.mark.asyncio
    async def test_resilient_session_raises_after_max_retries(self) -> None:
        """ResilientSession.make_request raises after exhausting retries."""
        from klir.bot.session_factory import ResilientSession
        from klir.config import ResilienceConfig

        cfg = ResilienceConfig(max_retries=1, base_backoff_seconds=0.01, max_backoff_seconds=0.1)
        session = ResilientSession(resilience_config=cfg)

        with (
            patch.object(
                type(session).__bases__[0],
                "make_request",
                new=AsyncMock(side_effect=TelegramNetworkError(method=None, message="timeout")),  # type: ignore[arg-type]
            ),
            pytest.raises(TelegramNetworkError),
        ):
            await session.make_request(bot=MagicMock(), method=MagicMock(), timeout=None)

    def test_full_config_round_trip(self) -> None:
        """Config -> ResilienceConfig -> ResilientSession pipeline."""
        from klir.bot.session_factory import ResilientSession, create_bot_session
        from klir.config import AgentConfig

        cfg = AgentConfig(
            telegram_token="test:token",
            resilience={"max_retries": 5, "base_backoff_seconds": 2.0},  # type: ignore[arg-type]
        )

        session = create_bot_session(proxy_url=None, resilience_config=cfg.resilience)
        assert isinstance(session, ResilientSession)
        assert session._resilience_config.max_retries == 5
        assert session._resilience_config.base_backoff_seconds == 2.0
