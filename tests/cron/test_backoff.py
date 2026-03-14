"""Tests for cron backoff: transient error detection and exponential backoff."""

from __future__ import annotations

from klir.cron.backoff import (
    DEFAULT_MAX_RETRIES,
    compute_backoff_seconds,
    is_transient_error,
    should_auto_disable,
)


class TestIsTransientError:
    def test_rate_limit(self) -> None:
        assert is_transient_error("rate limit exceeded") is True

    def test_overloaded(self) -> None:
        assert is_transient_error("server is overloaded") is True

    def test_network_error(self) -> None:
        assert is_transient_error("network error occurred") is True

    def test_timeout(self) -> None:
        assert is_transient_error("request timed out") is True

    def test_503(self) -> None:
        assert is_transient_error("HTTP 503 Service Unavailable") is True

    def test_502(self) -> None:
        assert is_transient_error("502 Bad Gateway") is True

    def test_500(self) -> None:
        assert is_transient_error("500 internal server error") is True

    def test_connection_refused(self) -> None:
        assert is_transient_error("connection refused") is True

    def test_non_transient_error(self) -> None:
        assert is_transient_error("syntax error in script") is False

    def test_permission_error(self) -> None:
        assert is_transient_error("permission denied") is False

    def test_case_insensitive(self) -> None:
        assert is_transient_error("RATE LIMIT") is True


class TestComputeBackoffSeconds:
    def test_zero_errors_returns_zero(self) -> None:
        assert compute_backoff_seconds(0) == 0.0

    def test_one_error_returns_30(self) -> None:
        assert compute_backoff_seconds(1) == 30.0

    def test_two_errors_returns_60(self) -> None:
        assert compute_backoff_seconds(2) == 60.0

    def test_three_errors_returns_300(self) -> None:
        assert compute_backoff_seconds(3) == 300.0

    def test_four_errors_returns_900(self) -> None:
        assert compute_backoff_seconds(4) == 900.0

    def test_five_errors_returns_3600(self) -> None:
        assert compute_backoff_seconds(5) == 3600.0

    def test_many_errors_caps_at_3600(self) -> None:
        assert compute_backoff_seconds(100) == 3600.0


class TestShouldAutoDisable:
    def test_zero_errors_no_disable(self) -> None:
        assert should_auto_disable(0) is False

    def test_below_threshold_no_disable(self) -> None:
        assert should_auto_disable(2) is False

    def test_at_default_threshold_disables(self) -> None:
        assert should_auto_disable(DEFAULT_MAX_RETRIES) is True

    def test_above_threshold_disables(self) -> None:
        assert should_auto_disable(10) is True

    def test_custom_max_retries(self) -> None:
        assert should_auto_disable(5, max_retries=6) is False
        assert should_auto_disable(6, max_retries=6) is True
