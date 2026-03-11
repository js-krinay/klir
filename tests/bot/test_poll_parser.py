"""Tests for PollParser directive extraction."""

from __future__ import annotations

import pytest


class TestPollParser:
    def test_parse_basic_poll(self) -> None:
        from klir.bot.poll_parser import PollDirective, parse_polls

        text = "Here's a poll: [poll:What's your favorite color?|Red|Blue|Green]"
        polls = parse_polls(text)

        assert len(polls) == 1
        assert polls[0].question == "What's your favorite color?"
        assert polls[0].options == ["Red", "Blue", "Green"]

    def test_parse_no_poll(self) -> None:
        from klir.bot.poll_parser import parse_polls

        text = "Just a regular message with no polls."
        polls = parse_polls(text)
        assert len(polls) == 0

    def test_parse_multiple_polls(self) -> None:
        from klir.bot.poll_parser import parse_polls

        text = (
            "[poll:Q1?|A|B|C]\n"
            "Some text in between\n"
            "[poll:Q2?|X|Y]"
        )
        polls = parse_polls(text)
        assert len(polls) == 2

    def test_minimum_two_options_required(self) -> None:
        from klir.bot.poll_parser import parse_polls

        text = "[poll:Question?|OnlyOneOption]"
        polls = parse_polls(text)
        assert len(polls) == 0  # Needs at least 2 options

    def test_strip_whitespace(self) -> None:
        from klir.bot.poll_parser import parse_polls

        text = "[poll: What?  | Option A | Option B ]"
        polls = parse_polls(text)
        assert len(polls) == 1
        assert polls[0].question == "What?"
        assert polls[0].options == ["Option A", "Option B"]

    def test_strip_directives_from_text(self) -> None:
        from klir.bot.poll_parser import strip_polls

        text = "Before [poll:Q?|A|B] After"
        cleaned = strip_polls(text)
        assert cleaned.strip() == "Before  After"

    def test_max_10_options(self) -> None:
        """Telegram limits polls to 10 options."""
        from klir.bot.poll_parser import parse_polls

        opts = "|".join(f"Opt{i}" for i in range(15))
        text = f"[poll:Q?|{opts}]"
        polls = parse_polls(text)
        assert len(polls) == 1
        assert len(polls[0].options) == 10  # Truncated to Telegram limit

    def test_poll_with_config_flags(self) -> None:
        from klir.bot.poll_parser import parse_polls

        text = "[poll:multi:Q?|A|B|C]"
        polls = parse_polls(text)
        assert len(polls) == 1
        assert polls[0].allows_multiple is True
