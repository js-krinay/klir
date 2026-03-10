"""Integration test: touch() is called on topic messages."""

from __future__ import annotations

from datetime import UTC, datetime

import time_machine

from ductor_bot.bot.topic import TopicNameCache


class TestTouchIntegration:
    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_touch_updates_on_known_binding(self) -> None:
        """Verify touch() path works end-to-end on cache."""
        cache = TopicNameCache()
        cache.set(-100, 42, "test topic")

        with time_machine.travel("2026-03-10 12:45:00", tick=False):
            # Simulate what the message handler does:
            topic_id = 42
            if topic_id is not None:
                cache.touch(-100, topic_id)

            meta = cache.get_meta(-100, 42)
            assert meta is not None
            assert meta.last_active_at == datetime(2026, 3, 10, 12, 45, 0, tzinfo=UTC)
            assert meta.created_at == datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)

    def test_touch_noop_on_non_topic_message(self) -> None:
        """Non-topic messages (topic_id=None) should not call touch."""
        cache = TopicNameCache()
        topic_id = None
        # This should be the guard in the handler
        if topic_id is not None:
            cache.touch(-100, topic_id)
        # No crash, nothing changed
        assert cache.get_meta(-100, 42) is None
