"""Tests for the technical footer module."""

from __future__ import annotations

from klir.bot.footer import (
    _FALLBACK_PRICE,
    FooterData,
    _price_per_million,
    build_footer_html,
    build_footer_markdown,
)


def _make_footer(**kwargs: object) -> FooterData:
    defaults = {
        "model_id": "claude-sonnet-4-5",
        "input_tokens": 1000,
        "output_tokens": 234,
        "cost_usd": 0.0023,
        "duration_ms": 4200.0,
    }
    defaults.update(kwargs)
    return FooterData(**defaults)  # type: ignore[arg-type]


class TestBuildFooterHtml:
    def test_all_fields(self) -> None:
        html = build_footer_html(_make_footer())
        assert "claude-sonnet-4-5" in html
        assert "1,234 tok" in html
        assert "$0.0023" in html
        assert "4.2s" in html
        assert "<i>" in html
        assert "─" in html

    def test_no_data_returns_empty(self) -> None:
        data = FooterData(
            model_id="",
            input_tokens=0,
            output_tokens=0,
            cost_usd=None,
            duration_ms=None,
        )
        assert build_footer_html(data) == ""

    def test_cost_fallback_estimate(self) -> None:
        data = _make_footer(cost_usd=None)
        html = build_footer_html(data)
        assert "$" in html
        assert "tok" in html

    def test_model_only(self) -> None:
        data = FooterData(
            model_id="claude-opus-4",
            input_tokens=0,
            output_tokens=0,
            cost_usd=None,
            duration_ms=None,
        )
        html = build_footer_html(data)
        assert "claude-opus-4" in html

    def test_duration_formatting(self) -> None:
        data = _make_footer(duration_ms=12345.0)
        html = build_footer_html(data)
        assert "12.3s" in html


class TestBuildFooterMarkdown:
    def test_all_fields(self) -> None:
        md = build_footer_markdown(_make_footer())
        assert "claude-sonnet-4-5" in md
        assert "1,234 tok" in md
        assert "$0.0023" in md
        assert "4.2s" in md
        assert "─" in md
        assert md.startswith("\n\n─\n_")
        assert md.endswith("_")

    def test_no_data_returns_empty(self) -> None:
        data = FooterData(
            model_id="",
            input_tokens=0,
            output_tokens=0,
            cost_usd=None,
            duration_ms=None,
        )
        assert build_footer_markdown(data) == ""


class TestPricing:
    def test_known_claude_model(self) -> None:
        assert _price_per_million("claude-sonnet-4-5") == 6.00

    def test_known_gemini_model(self) -> None:
        assert _price_per_million("gemini-2.5-pro-preview") == 7.00

    def test_unknown_model_uses_fallback(self) -> None:
        assert _price_per_million("gpt-4o") == _FALLBACK_PRICE

    def test_case_insensitive(self) -> None:
        assert _price_per_million("Claude-Opus-4-latest") == 30.00
