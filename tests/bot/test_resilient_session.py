"""Tests for ResilientSession wrapping aiogram AiohttpSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramServerError


class TestCreateBotSession:
    def test_no_proxy_no_resilience_returns_none(self) -> None:
        from klir.bot.session_factory import create_bot_session

        result = create_bot_session(proxy_url=None, resilience_config=None)
        assert result is None

    def test_with_resilience_returns_resilient_session(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.session_factory import create_bot_session

        cfg = ResilienceConfig()
        result = create_bot_session(proxy_url=None, resilience_config=cfg)
        assert result is not None
        assert type(result).__name__ == "ResilientSession"

    def test_with_proxy_and_resilience(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.session_factory import create_bot_session

        cfg = ResilienceConfig()
        with patch("klir.bot.session_factory.AiohttpSession.__init__", return_value=None):
            result = create_bot_session(proxy_url="http://proxy:8080", resilience_config=cfg)
        assert result is not None
        assert type(result).__name__ == "ResilientSession"

    def test_with_proxy_no_resilience_returns_aiohttp_session(self) -> None:
        from klir.bot.session_factory import create_bot_session

        with patch("klir.bot.session_factory.AiohttpSession") as MockSession:
            mock_instance = MagicMock()
            MockSession.return_value = mock_instance
            result = create_bot_session(proxy_url="http://proxy:8080", resilience_config=None)
            assert result is mock_instance


class TestResilientSession:
    def test_instantiation(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.session_factory import ResilientSession

        cfg = ResilienceConfig(max_retries=5)
        session = ResilientSession(resilience_config=cfg)
        assert session._resilience_config.max_retries == 5

    def test_instantiation_with_proxy(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.session_factory import ResilientSession

        cfg = ResilienceConfig()
        with patch("klir.bot.session_factory.AiohttpSession.__init__", return_value=None):
            session = ResilientSession(resilience_config=cfg, proxy="http://proxy:8080")
        assert session._resilience_config is cfg
