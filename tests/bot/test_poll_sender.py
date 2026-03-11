"""Tests for PollSender."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestPollSender:
    async def test_send_poll(self) -> None:
        from klir.bot.poll_parser import PollDirective
        from klir.bot.poll_sender import send_poll

        bot = AsyncMock()
        bot.send_poll.return_value = MagicMock(poll=MagicMock(id="poll_123"))

        directive = PollDirective(
            question="Favorite color?",
            options=["Red", "Blue", "Green"],
        )

        result = await send_poll(bot, chat_id=42, directive=directive)
        bot.send_poll.assert_called_once()
        call_kwargs = bot.send_poll.call_args.kwargs
        assert call_kwargs["chat_id"] == 42
        assert call_kwargs["question"] == "Favorite color?"
        assert call_kwargs["options"] == ["Red", "Blue", "Green"]

    async def test_send_poll_with_thread(self) -> None:
        from klir.bot.poll_parser import PollDirective
        from klir.bot.poll_sender import send_poll

        bot = AsyncMock()
        bot.send_poll.return_value = MagicMock(poll=MagicMock(id="poll_123"))

        directive = PollDirective(question="Q?", options=["A", "B"])

        await send_poll(bot, chat_id=42, directive=directive, thread_id=99)
        call_kwargs = bot.send_poll.call_args.kwargs
        assert call_kwargs["message_thread_id"] == 99

    async def test_send_poll_anonymous_config(self) -> None:
        from klir.bot.poll_parser import PollDirective
        from klir.bot.poll_sender import send_poll

        bot = AsyncMock()
        bot.send_poll.return_value = MagicMock(poll=MagicMock(id="poll_123"))

        directive = PollDirective(question="Q?", options=["A", "B"])

        await send_poll(bot, chat_id=42, directive=directive, is_anonymous=False)
        call_kwargs = bot.send_poll.call_args.kwargs
        assert call_kwargs["is_anonymous"] is False

    async def test_send_poll_failure_swallowed(self) -> None:
        from klir.bot.poll_parser import PollDirective
        from klir.bot.poll_sender import send_poll

        bot = AsyncMock()
        bot.send_poll.side_effect = Exception("API error")

        directive = PollDirective(question="Q?", options=["A", "B"])

        # Should not raise
        result = await send_poll(bot, chat_id=42, directive=directive)
        assert result is None
