"""Tests for forward/copy directive parsing."""

from __future__ import annotations

import pytest


class TestForwardParser:
    def test_parse_forward_directive(self) -> None:
        from ductor_bot.bot.forward_parser import ForwardDirective, parse_forwards

        text = "Check this out [forward:123:456]"
        directives = parse_forwards(text)

        assert len(directives) == 1
        assert directives[0].chat_id == 123
        assert directives[0].message_id == 456
        assert directives[0].mode == "forward"

    def test_parse_copy_directive(self) -> None:
        from ductor_bot.bot.forward_parser import parse_forwards

        text = "Clean copy: [copy:123:456]"
        directives = parse_forwards(text)

        assert len(directives) == 1
        assert directives[0].mode == "copy"

    def test_parse_no_directives(self) -> None:
        from ductor_bot.bot.forward_parser import parse_forwards

        text = "Just a regular message."
        assert parse_forwards(text) == []

    def test_parse_multiple_directives(self) -> None:
        from ductor_bot.bot.forward_parser import parse_forwards

        text = "[forward:100:1] some text [copy:200:2]"
        directives = parse_forwards(text)
        assert len(directives) == 2
        assert directives[0].mode == "forward"
        assert directives[1].mode == "copy"

    def test_parse_negative_chat_id(self) -> None:
        from ductor_bot.bot.forward_parser import parse_forwards

        text = "[forward:-1001234567890:42]"
        directives = parse_forwards(text)

        assert len(directives) == 1
        assert directives[0].chat_id == -1001234567890
        assert directives[0].message_id == 42

    def test_invalid_non_numeric_ignored(self) -> None:
        from ductor_bot.bot.forward_parser import parse_forwards

        text = "[forward:abc:def]"
        assert parse_forwards(text) == []

    def test_strip_forwards(self) -> None:
        from ductor_bot.bot.forward_parser import strip_forwards

        text = "Before [forward:123:456] middle [copy:789:10] after"
        cleaned = strip_forwards(text)
        assert "[forward:" not in cleaned
        assert "[copy:" not in cleaned
        assert "Before" in cleaned
        assert "middle" in cleaned
        assert "after" in cleaned

    def test_parse_message_id_only(self) -> None:
        """Incomplete directives with missing parts are ignored."""
        from ductor_bot.bot.forward_parser import parse_forwards

        text = "[forward:123]"
        assert parse_forwards(text) == []
