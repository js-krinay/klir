"""Tests for BindingCleanupObserver."""

from __future__ import annotations

import time_machine

from ductor_bot.bot.binding_cleanup import BindingCleanupObserver
from ductor_bot.bot.topic import TopicNameCache
from ductor_bot.config import AgentConfig, ThreadBindingConfig


class TestBindingCleanupObserver:
    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    async def test_cleanup_removes_expired_bindings(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "old")
        cfg = AgentConfig(
            thread_binding=ThreadBindingConfig(
                idle_timeout_minutes=60,
                max_age_minutes=1440,
                cleanup_interval_minutes=1,
            ),
        )
        observer = BindingCleanupObserver(config=cfg, topic_cache=cache)

        with time_machine.travel("2026-03-10 13:01:00", tick=False):
            removed = observer.run_cleanup()
            assert removed == 1
            assert cache.get(-100, 42) is None

    @time_machine.travel("2026-03-10 12:00:00", tick=False)
    async def test_cleanup_keeps_fresh_bindings(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "fresh")
        cfg = AgentConfig(
            thread_binding=ThreadBindingConfig(
                idle_timeout_minutes=60,
                max_age_minutes=1440,
            ),
        )
        observer = BindingCleanupObserver(config=cfg, topic_cache=cache)

        removed = observer.run_cleanup()
        assert removed == 0
        assert cache.get(-100, 42) == "fresh"

    async def test_cleanup_disabled_is_noop(self) -> None:
        cache = TopicNameCache()
        cache.set(-100, 42, "test")
        cfg = AgentConfig(
            thread_binding=ThreadBindingConfig(enabled=False),
        )
        observer = BindingCleanupObserver(config=cfg, topic_cache=cache)

        removed = observer.run_cleanup()
        assert removed == 0

    async def test_start_does_not_start_when_disabled(self) -> None:
        cache = TopicNameCache()
        cfg = AgentConfig(
            thread_binding=ThreadBindingConfig(enabled=False),
        )
        observer = BindingCleanupObserver(config=cfg, topic_cache=cache)
        await observer.start()
        assert observer.running is False

    async def test_start_stop_lifecycle(self) -> None:
        cache = TopicNameCache()
        cfg = AgentConfig(
            thread_binding=ThreadBindingConfig(enabled=True),
        )
        observer = BindingCleanupObserver(config=cfg, topic_cache=cache)
        await observer.start()
        assert observer.running is True
        await observer.stop()
        assert observer.running is False
