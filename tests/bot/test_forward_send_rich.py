"""Tests for forward/copy directive integration in send_rich."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestForwardInSendRich:
    async def test_forward_directive_extracted_and_sent(self) -> None:
        from ductor_bot.bot.sender import SendRichOpts, send_rich

        bot = AsyncMock()
        bot.send_message.return_value = MagicMock(message_id=1)
        bot.forward_message.return_value = MagicMock(message_id=2)

        text = "Here you go [forward:200:10]"
        opts = SendRichOpts(
            forwarding_enabled=True,
            forwarding_targets={200, 300},
        )

        await send_rich(bot, chat_id=100, text=text, opts=opts)
        bot.forward_message.assert_called_once_with(
            chat_id=200, from_chat_id=100, message_id=10,
        )

    async def test_forward_stripped_from_text(self) -> None:
        from ductor_bot.bot.sender import SendRichOpts, send_rich

        bot = AsyncMock()
        bot.send_message.return_value = MagicMock(message_id=1)
        bot.forward_message.return_value = MagicMock(message_id=2)

        text = "Message [forward:200:10] here"
        opts = SendRichOpts(
            forwarding_enabled=True,
            forwarding_targets={200},
        )

        await send_rich(bot, chat_id=100, text=text, opts=opts)
        # The text sent to the chat should not contain the directive
        call_args = bot.send_message.call_args
        assert "[forward:" not in call_args.kwargs.get("text", call_args[1] if len(call_args) > 1 else "")

    async def test_forwarding_disabled_ignores_directives(self) -> None:
        from ductor_bot.bot.sender import SendRichOpts, send_rich

        bot = AsyncMock()
        bot.send_message.return_value = MagicMock(message_id=1)

        text = "Message [forward:200:10]"
        opts = SendRichOpts(forwarding_enabled=False)

        await send_rich(bot, chat_id=100, text=text, opts=opts)
        bot.forward_message.assert_not_called()
