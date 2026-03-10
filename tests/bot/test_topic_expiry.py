"""Tests for TopicNameCache.expired_bindings() lifecycle checks."""

from __future__ import annotations

from datetime import UTC, datetime

import time_machine

from ductor_bot.bot.topic import TopicNameCache
from ductor_bot.config import ThreadBindingConfig


class TestExpiredBindings:
    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_no_expired_when_fresh(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "fresh")
        cfg = ThreadBindingConfig(idle_timeout_minutes=60, max_age_minutes=1440)
        expired = cache.expired_bindings(cfg)
        assert expired == []

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_idle_timeout_expires_binding(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "idle")
        cfg = ThreadBindingConfig(idle_timeout_minutes=60, max_age_minutes=1440)

        with time_machine.travel("2026-03-10 13:01:00", tick=False):
            expired = cache.expired_bindings(cfg)
            assert len(expired) == 1
            assert expired[0] == (-100, 42)

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_max_age_expires_binding(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "old")
        cfg = ThreadBindingConfig(idle_timeout_minutes=60, max_age_minutes=120)

        with time_machine.travel("2026-03-10 14:01:00", tick=False):
            # Touch to keep it non-idle, but max_age should still expire it
            cache.touch(-100, 42)
            expired = cache.expired_bindings(cfg)
            assert len(expired) == 1
            assert expired[0] == (-100, 42)

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_active_binding_not_expired(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "active")
        cfg = ThreadBindingConfig(idle_timeout_minutes=60, max_age_minutes=1440)

        with time_machine.travel("2026-03-10 12:30:00", tick=False):
            cache.touch(-100, 42)
            expired = cache.expired_bindings(cfg)
            assert expired == []

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_mixed_fresh_and_expired(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "old")
        cfg = ThreadBindingConfig(idle_timeout_minutes=60, max_age_minutes=1440)

        with time_machine.travel("2026-03-10 14:00:00", tick=False):
            cache.set(-100, 99, "new")
            expired = cache.expired_bindings(cfg)
            assert (-100, 42) in expired
            assert (-100, 99) not in expired

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_disabled_returns_empty(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "old")
        cfg = ThreadBindingConfig(enabled=False, idle_timeout_minutes=0, max_age_minutes=0)

        with time_machine.travel("2026-03-11 12:00:00", tick=False):
            expired = cache.expired_bindings(cfg)
            assert expired == []

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_zero_timeout_means_no_idle_check(self) -> None:
        """idle_timeout_minutes=0 disables idle check, only max_age applies."""
        cache = TopicNameCache()
        cache.set(-100, 42, "no-idle-check")
        cfg = ThreadBindingConfig(idle_timeout_minutes=0, max_age_minutes=1440)

        with time_machine.travel("2026-03-10 23:00:00", tick=False):
            expired = cache.expired_bindings(cfg)
            assert expired == []

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_zero_max_age_means_no_age_check(self) -> None:
        """max_age_minutes=0 disables max age check, only idle applies."""
        cache = TopicNameCache()
        cache.set(-100, 42, "no-age-check")
        cfg = ThreadBindingConfig(idle_timeout_minutes=60, max_age_minutes=0)

        with time_machine.travel("2026-03-12 12:00:00", tick=False):
            # Not idle because we'll touch it
            cache.touch(-100, 42)
            expired = cache.expired_bindings(cfg)
            assert expired == []
