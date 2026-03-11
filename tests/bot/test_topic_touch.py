"""Tests for TopicNameCache.touch() activity tracking."""

from __future__ import annotations

from datetime import UTC, datetime

import time_machine

from klir.bot.topic import TopicNameCache


class TestTopicNameCacheTouch:
    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_touch_updates_last_active(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "test")
        meta_before = cache.get_meta(-100, 42)
        assert meta_before is not None
        assert meta_before.last_active_at == datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)

        with time_machine.travel("2026-03-10 12:30:00", tick=False):
            cache.touch(-100, 42)
            meta_after = cache.get_meta(-100, 42)
            assert meta_after is not None
            assert meta_after.last_active_at == datetime(2026, 3, 10, 12, 30, 0, tzinfo=UTC)
            assert meta_after.created_at == datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)

    def test_touch_unknown_binding_is_noop(self) -> None:
        cache = TopicNameCache()
        # Should not raise
        cache.touch(-100, 99)
        assert cache.get_meta(-100, 99) is None

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_touch_does_not_change_name(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "original")
        with time_machine.travel("2026-03-10 13:00:00", tick=False):
            cache.touch(-100, 42)
        assert cache.get(-100, 42) == "original"
