"""Test poll extraction in the sender pipeline."""

from __future__ import annotations

from klir.bot.poll_parser import parse_polls, strip_polls


class TestSenderPollIntegration:
    def test_response_with_poll_is_stripped(self) -> None:
        text = "Here are results:\n[poll:Rate this?|Good|Bad|Meh]\nThanks!"
        polls = parse_polls(text)
        cleaned = strip_polls(text)

        assert len(polls) == 1
        assert "[poll:" not in cleaned
        assert "Here are results:" in cleaned
        assert "Thanks!" in cleaned

    def test_response_without_poll_unchanged(self) -> None:
        text = "Just a normal response."
        polls = parse_polls(text)
        cleaned = strip_polls(text)

        assert len(polls) == 0
        assert cleaned == text
