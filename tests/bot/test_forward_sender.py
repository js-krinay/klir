"""Tests for forward/copy message sender."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestForwardSender:
    async def test_forward_message(self) -> None:
        from klir.bot.forward_parser import ForwardDirective
        from klir.bot.forward_sender import send_forward

        bot = AsyncMock()
        bot.forward_message.return_value = MagicMock(message_id=99)

        directive = ForwardDirective(mode="forward", chat_id=200, message_id=10)
        allowed = {200, 300}

        result = await send_forward(bot, from_chat_id=100, directive=directive, allowed_targets=allowed)
        bot.forward_message.assert_called_once_with(
            chat_id=200, from_chat_id=100, message_id=10,
        )
        assert result is not None

    async def test_copy_message(self) -> None:
        from klir.bot.forward_parser import ForwardDirective
        from klir.bot.forward_sender import send_forward

        bot = AsyncMock()
        bot.copy_message.return_value = MagicMock(message_id=99)

        directive = ForwardDirective(mode="copy", chat_id=200, message_id=10)
        allowed = {200}

        result = await send_forward(bot, from_chat_id=100, directive=directive, allowed_targets=allowed)
        bot.copy_message.assert_called_once_with(
            chat_id=200, from_chat_id=100, message_id=10,
        )
        assert result is not None

    async def test_unauthorized_target_blocked(self) -> None:
        from klir.bot.forward_parser import ForwardDirective
        from klir.bot.forward_sender import send_forward

        bot = AsyncMock()
        directive = ForwardDirective(mode="forward", chat_id=999, message_id=10)
        allowed = {200, 300}

        result = await send_forward(bot, from_chat_id=100, directive=directive, allowed_targets=allowed)
        bot.forward_message.assert_not_called()
        bot.copy_message.assert_not_called()
        assert result is None

    async def test_api_error_swallowed(self) -> None:
        from klir.bot.forward_parser import ForwardDirective
        from klir.bot.forward_sender import send_forward

        bot = AsyncMock()
        bot.forward_message.side_effect = Exception("API error")
        directive = ForwardDirective(mode="forward", chat_id=200, message_id=10)

        result = await send_forward(bot, from_chat_id=100, directive=directive, allowed_targets={200})
        assert result is None

    async def test_empty_allowed_targets_blocks_all(self) -> None:
        from klir.bot.forward_parser import ForwardDirective
        from klir.bot.forward_sender import send_forward

        bot = AsyncMock()
        directive = ForwardDirective(mode="forward", chat_id=200, message_id=10)

        result = await send_forward(bot, from_chat_id=100, directive=directive, allowed_targets=set())
        bot.forward_message.assert_not_called()
        assert result is None
