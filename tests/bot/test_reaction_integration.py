"""Integration tests for reaction wiring in TelegramBot."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestReactionWiring:
    def test_telegram_bot_has_reaction_service(self) -> None:
        """TelegramBot creates a ReactionService on init."""
        from klir.bot.reactions import ReactionService
        from klir.config import AgentConfig

        config = AgentConfig(telegram_token="test:token")

        with patch("klir.bot.app.Bot"):
            from klir.bot.app import TelegramBot

            bot = TelegramBot(config)
            assert isinstance(bot._reactions, ReactionService)
