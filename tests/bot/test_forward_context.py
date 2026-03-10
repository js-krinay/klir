"""Tests for inbound forward origin context extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestForwardContext:
    def test_extract_user_forward_origin(self) -> None:
        from ductor_bot.bot.forward_context import extract_forward_context

        origin = MagicMock()
        origin.type = "user"
        origin.sender_user.full_name = "Alice"
        origin.sender_user.id = 123
        origin.date.isoformat.return_value = "2026-03-10T12:00:00"

        message = MagicMock()
        message.forward_origin = origin
        message.text = "Hello world"

        result = extract_forward_context(message)
        assert result is not None
        assert "Alice" in result
        assert "123" in result
        assert "Hello world" not in result  # body is not included, only metadata header

    def test_extract_channel_forward_origin(self) -> None:
        from ductor_bot.bot.forward_context import extract_forward_context

        origin = MagicMock()
        origin.type = "channel"
        origin.chat.title = "News Channel"
        origin.chat.id = -1001234567890
        origin.message_id = 42
        origin.date.isoformat.return_value = "2026-03-10T12:00:00"

        message = MagicMock()
        message.forward_origin = origin
        message.text = "Breaking news"

        result = extract_forward_context(message)
        assert result is not None
        assert "News Channel" in result
        assert "-1001234567890" in result
        assert "42" in result

    def test_extract_hidden_user_forward_origin(self) -> None:
        from ductor_bot.bot.forward_context import extract_forward_context

        origin = MagicMock()
        origin.type = "hidden_user"
        origin.sender_user_name = "Hidden Name"
        origin.date.isoformat.return_value = "2026-03-10T12:00:00"

        message = MagicMock()
        message.forward_origin = origin
        message.text = "Secret message"

        result = extract_forward_context(message)
        assert result is not None
        assert "Hidden Name" in result

    def test_no_forward_origin_returns_none(self) -> None:
        from ductor_bot.bot.forward_context import extract_forward_context

        message = MagicMock()
        message.forward_origin = None

        result = extract_forward_context(message)
        assert result is None

    def test_prepend_forward_context_to_text(self) -> None:
        from ductor_bot.bot.forward_context import prepend_forward_context

        context = "[Forwarded from Alice (user 123) at 2026-03-10T12:00:00]"
        text = "User said something"

        result = prepend_forward_context(context, text)
        assert result.startswith("[Forwarded from")
        assert "User said something" in result
