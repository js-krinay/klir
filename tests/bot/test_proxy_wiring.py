"""Test that proxy is wired into Bot creation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestProxyWiring:
    def test_bot_created_with_proxy_session(self) -> None:
        from klir.config import AgentConfig, ProxyConfig
        from klir.bot.session_factory import ResilientSession

        config = AgentConfig(
            telegram_token="test:token",
            proxy=ProxyConfig(url="http://proxy:8080"),
        )

        with (
            patch("klir.bot.app.Bot") as MockBot,
            patch("klir.bot.session_factory.AiohttpSession.__init__", return_value=None),
        ):
            from klir.bot.app import TelegramBot

            bot = TelegramBot(config)

            # Bot should have been created with a ResilientSession
            call_kwargs = MockBot.call_args.kwargs
            assert isinstance(call_kwargs.get("session"), ResilientSession)

    def test_bot_created_without_proxy(self) -> None:
        from klir.config import AgentConfig
        from klir.bot.session_factory import ResilientSession

        config = AgentConfig(telegram_token="test:token")

        with patch("klir.bot.app.Bot") as MockBot:
            from klir.bot.app import TelegramBot

            bot = TelegramBot(config)

            # Resilience is always enabled, so a ResilientSession is used even without proxy
            call_kwargs = MockBot.call_args.kwargs
            assert isinstance(call_kwargs.get("session"), ResilientSession)
