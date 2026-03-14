"""Tests for cron failure alerts with cooldown."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from klir.cron.alerts import (
    DEFAULT_ALERT_AFTER,
    DEFAULT_COOLDOWN_SECONDS,
    format_failure_alert,
    should_alert,
)


class TestShouldAlert:
    def test_no_alert_below_threshold(self) -> None:
        assert should_alert(consecutive_errors=1, last_alert_at=None) is False
        assert should_alert(consecutive_errors=2, last_alert_at=None) is False

    def test_alert_at_threshold_no_prior_alert(self) -> None:
        assert should_alert(consecutive_errors=DEFAULT_ALERT_AFTER, last_alert_at=None) is True

    def test_alert_above_threshold_no_prior_alert(self) -> None:
        assert should_alert(consecutive_errors=10, last_alert_at=None) is True

    def test_no_alert_within_cooldown(self) -> None:
        recent = datetime.now(UTC).isoformat()
        assert should_alert(consecutive_errors=5, last_alert_at=recent) is False

    def test_alert_after_cooldown_expired(self) -> None:
        old_time = (datetime.now(UTC) - timedelta(seconds=DEFAULT_COOLDOWN_SECONDS + 1)).isoformat()
        assert should_alert(consecutive_errors=5, last_alert_at=old_time) is True

    def test_custom_alert_after(self) -> None:
        assert should_alert(consecutive_errors=2, last_alert_at=None, alert_after=2) is True
        assert should_alert(consecutive_errors=1, last_alert_at=None, alert_after=2) is False

    def test_custom_cooldown(self) -> None:
        # 5 seconds ago with 10-second cooldown → still cooling down
        recent = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
        assert (
            should_alert(consecutive_errors=5, last_alert_at=recent, cooldown_seconds=10) is False
        )
        # 5 seconds ago with 3-second cooldown → cooldown expired
        assert should_alert(consecutive_errors=5, last_alert_at=recent, cooldown_seconds=3) is True

    def test_malformed_last_alert_at_triggers_alert(self) -> None:
        assert should_alert(consecutive_errors=5, last_alert_at="not-a-date") is True


class TestFormatFailureAlert:
    def test_contains_job_title(self) -> None:
        msg = format_failure_alert("Daily Report", 3, "timeout error")
        assert "Daily Report" in msg

    def test_contains_error_count(self) -> None:
        msg = format_failure_alert("My Job", 5, "network failure")
        assert "5" in msg

    def test_contains_last_error(self) -> None:
        msg = format_failure_alert("My Job", 3, "connection refused")
        assert "connection refused" in msg
