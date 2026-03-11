"""Tests for TopicNameCache binding metadata."""

from __future__ import annotations

from datetime import UTC, datetime

import time_machine

from klir.bot.topic import BindingMeta, TopicNameCache


class TestBindingMeta:
    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_set_stores_metadata(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "test topic")
        meta = cache.get_meta(-100, 42)
        assert meta is not None
        assert meta.name == "test topic"
        assert meta.created_at == datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
        assert meta.last_active_at == datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_get_meta_returns_none_for_unknown(self) -> None:
        cache = TopicNameCache()
        assert cache.get_meta(-100, 99) is None

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    def test_set_overwrites_name_preserves_created_at(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "old name")
        old_meta = cache.get_meta(-100, 42)
        assert old_meta is not None
        original_created = old_meta.created_at

        with time_machine.travel("2026-03-10 13:00:00", tick=False):
            cache.set(-100, 42, "new name")
            meta = cache.get_meta(-100, 42)
            assert meta is not None
            assert meta.name == "new name"
            assert meta.created_at == original_created
            assert meta.last_active_at == datetime(2026, 3, 10, 13, 0, 0, tzinfo=UTC)

    def test_get_still_works(self) -> None:
        """Existing get() API returns str | None unchanged."""
        cache = TopicNameCache()
        cache.set(-100, 42, "test")
        assert cache.get(-100, 42) == "test"
        assert cache.get(-100, 99) is None

    def test_resolve_still_works(self) -> None:
        """Existing resolve() API unchanged."""
        cache = TopicNameCache()
        cache.set(-100, 42, "test")
        assert cache.resolve(-100, 42) == "test"
        assert cache.resolve(-100, 99) == "Topic #99"

    def test_find_by_name_still_works(self) -> None:
        """Existing find_by_name() API unchanged."""
        cache = TopicNameCache()
        cache.set(-100, 42, "Test Topic")
        assert cache.find_by_name(-100, "test topic") == 42
        assert cache.find_by_name(-100, "nope") is None
