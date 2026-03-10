"""Tests for scoped command sync at startup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSyncCommands:
    async def test_sets_private_and_group_scopes(self) -> None:
        """_sync_commands should call set_my_commands for both scopes."""
        from ductor_bot.config import AgentConfig

        config = AgentConfig(telegram_token="test:token")

        with patch("ductor_bot.bot.app.Bot") as MockBot:
            mock_bot = MockBot.return_value
            mock_bot.get_my_commands = AsyncMock(return_value=[])
            mock_bot.set_my_commands = AsyncMock()
            mock_bot.delete_my_commands = AsyncMock()

            from ductor_bot.bot.app import TelegramBot

            bot = TelegramBot(config)
            bot._bot = mock_bot
            await bot._sync_commands()

            # Should have called set_my_commands at least twice (private + group)
            assert mock_bot.set_my_commands.call_count >= 2

    async def test_group_scope_has_fewer_commands(self) -> None:
        """Group scope should have fewer commands than private scope."""
        from ductor_bot.commands import BOT_COMMANDS, GROUP_COMMANDS

        assert len(GROUP_COMMANDS) < len(BOT_COMMANDS)

    async def test_shutdown_deletes_commands(self) -> None:
        """shutdown() should call delete_my_commands for clean state."""
        from ductor_bot.config import AgentConfig

        config = AgentConfig(telegram_token="test:token")

        with patch("ductor_bot.bot.app.Bot") as MockBot:
            mock_bot = MockBot.return_value
            mock_bot.delete_my_commands = AsyncMock()
            mock_bot.delete_webhook = AsyncMock()
            mock_bot.session = MagicMock()
            mock_bot.session.close = AsyncMock()

            from ductor_bot.bot.app import TelegramBot

            bot = TelegramBot(config)
            bot._bot = mock_bot
            bot._orchestrator = MagicMock()
            bot._orchestrator.shutdown = AsyncMock()
            await bot.shutdown()

            mock_bot.delete_my_commands.assert_called()
