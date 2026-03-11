"""Tests for conflict detection wiring in TelegramBot."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestConflictWiring:
    def test_telegram_bot_has_conflict_detector(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")

        with (
            patch("klir.bot.app.create_bot_session", return_value=None),
            patch("klir.bot.app.resolve_proxy_url", return_value=None),
            patch("klir.bot.app.Bot"),
            patch("klir.bot.app.Dispatcher"),
            patch("klir.bot.app.ReactionService"),
        ):
            from klir.bot.app import TelegramBot

            bot = TelegramBot(cfg)
            assert hasattr(bot, "_conflict_detector")

            from klir.bot.conflict_detector import ConflictDetector

            assert isinstance(bot._conflict_detector, ConflictDetector)
