"""Tests for forward context integration in _on_message."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestForwardResolve:
    def test_prepend_context_modifies_text(self) -> None:
        """Verify the prepend function composes correctly."""
        from klir.bot.forward_context import prepend_forward_context

        ctx = "[Forwarded from Alice (user 100) at 2026-03-10T12:00:00]"
        text = "My reply about this"
        result = prepend_forward_context(ctx, text)

        assert result.startswith("[Forwarded from Alice")
        assert "My reply about this" in result
        # Context and text are separated by blank line
        assert "\n\n" in result

    def test_forward_context_with_empty_text(self) -> None:
        from klir.bot.forward_context import extract_forward_context

        origin = MagicMock()
        origin.type = "user"
        origin.sender_user.full_name = "Bob"
        origin.sender_user.id = 50
        origin.date.isoformat.return_value = "2026-03-10T12:00:00"

        message = MagicMock()
        message.forward_origin = origin
        message.text = None
        message.caption = None

        result = extract_forward_context(message)
        assert result is not None
        assert "Bob" in result
        # No trailing newline when text is empty
        assert not result.endswith("\n")
