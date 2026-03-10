"""Tests for TopicNameCache.remove_bindings() cleanup."""

from __future__ import annotations

from ductor_bot.bot.topic import TopicNameCache


class TestRemoveBindings:
    def test_remove_single_binding(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "doomed")
        cache.set(-100, 99, "safe")
        removed = cache.remove_bindings([(-100, 42)])
        assert removed == 1
        assert cache.get(-100, 42) is None
        assert cache.get(-100, 99) == "safe"

    def test_remove_multiple_bindings(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 1, "a")
        cache.set(-100, 2, "b")
        cache.set(-100, 3, "c")
        removed = cache.remove_bindings([(-100, 1), (-100, 3)])
        assert removed == 2
        assert cache.get(-100, 1) is None
        assert cache.get(-100, 2) == "b"
        assert cache.get(-100, 3) is None

    def test_remove_nonexistent_is_safe(self) -> None:
        cache = TopicNameCache()
        removed = cache.remove_bindings([(-100, 999)])
        assert removed == 0

    def test_remove_empty_list(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "safe")
        removed = cache.remove_bindings([])
        assert removed == 0
        assert cache.get(-100, 42) == "safe"

    def test_remove_clears_metadata(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "doomed")
        cache.remove_bindings([(-100, 42)])
        assert cache.get_meta(-100, 42) is None
