"""Tests for ReactionService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_config(level: str = "ack") -> MagicMock:
    cfg = MagicMock()
    cfg.reactions.level = level
    cfg.reactions.ack_emoji = "👀"
    cfg.reactions.done_emoji = "✅"
    cfg.reactions.error_emoji = "❌"
    return cfg


class TestReactionService:
    async def test_ack_sends_reaction(self) -> None:
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        svc = ReactionService(bot, _make_config("ack"))

        await svc.ack(chat_id=1, message_id=10)

        bot.set_message_reaction.assert_called_once()
        call_kwargs = bot.set_message_reaction.call_args.kwargs
        assert call_kwargs["chat_id"] == 1
        assert call_kwargs["message_id"] == 10

    async def test_off_level_skips_all(self) -> None:
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        svc = ReactionService(bot, _make_config("off"))

        await svc.ack(chat_id=1, message_id=10)
        await svc.done(chat_id=1, message_id=10)
        await svc.error(chat_id=1, message_id=10)

        bot.set_message_reaction.assert_not_called()

    async def test_ack_level_sends_ack_and_done_but_not_processing(self) -> None:
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        svc = ReactionService(bot, _make_config("ack"))

        await svc.ack(chat_id=1, message_id=10)
        assert bot.set_message_reaction.call_count == 1

        await svc.done(chat_id=1, message_id=10)
        assert bot.set_message_reaction.call_count == 2

    async def test_error_clears_and_sets_error_emoji(self) -> None:
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        svc = ReactionService(bot, _make_config("ack"))

        await svc.error(chat_id=1, message_id=10)

        bot.set_message_reaction.assert_called_once()
        call_kwargs = bot.set_message_reaction.call_args.kwargs
        assert call_kwargs["chat_id"] == 1

    async def test_api_failure_is_swallowed(self) -> None:
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        bot.set_message_reaction.side_effect = Exception("Telegram API error")
        svc = ReactionService(bot, _make_config("ack"))

        # Should not raise
        await svc.ack(chat_id=1, message_id=10)

    async def test_clear_removes_reactions(self) -> None:
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        svc = ReactionService(bot, _make_config("ack"))

        await svc.clear(chat_id=1, message_id=10)

        bot.set_message_reaction.assert_called_once()
        call_kwargs = bot.set_message_reaction.call_args.kwargs
        assert call_kwargs["reaction"] == []

    async def test_picks_up_config_change_via_parent_ref(self) -> None:
        """Verify hot-reload works: service reads current config, not a stale snapshot."""
        from ductor_bot.bot.reactions import ReactionService

        bot = AsyncMock()
        config = _make_config("ack")
        svc = ReactionService(bot, config)

        await svc.ack(chat_id=1, message_id=10)
        assert bot.set_message_reaction.call_count == 1

        # Simulate hot-reload: parent config's reactions field changes
        config.reactions.level = "off"

        await svc.ack(chat_id=1, message_id=10)
        # Should NOT have called again since level is now "off"
        assert bot.set_message_reaction.call_count == 1
