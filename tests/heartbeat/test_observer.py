"""Tests for the heartbeat observer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import time_machine

from klir.config import AgentConfig, HeartbeatConfig, HeartbeatGroupTarget
from klir.heartbeat.observer import HeartbeatObserver
from klir.orchestrator.flows import _strip_ack_token
from klir.utils.quiet_hours import is_quiet_hour

# ---------------------------------------------------------------------------
# Quiet hour logic
# ---------------------------------------------------------------------------


class TestIsQuietHour:
    def test_within_evening_quiet(self) -> None:
        # quiet 21-08: 22 is quiet
        assert is_quiet_hour(22, 21, 8) is True

    def test_within_morning_quiet(self) -> None:
        # quiet 21-08: 3 is quiet
        assert is_quiet_hour(3, 21, 8) is True

    def test_boundary_start_is_quiet(self) -> None:
        assert is_quiet_hour(21, 21, 8) is True

    def test_boundary_end_is_not_quiet(self) -> None:
        # end is exclusive
        assert is_quiet_hour(8, 21, 8) is False

    def test_daytime_is_not_quiet(self) -> None:
        assert is_quiet_hour(14, 21, 8) is False

    def test_no_wrap_quiet_window(self) -> None:
        # quiet 2-6: 4 is quiet, 1 is not
        assert is_quiet_hour(4, 2, 6) is True
        assert is_quiet_hour(1, 2, 6) is False
        assert is_quiet_hour(7, 2, 6) is False

    def test_midnight_in_wrap_window(self) -> None:
        assert is_quiet_hour(0, 21, 8) is True

    def test_same_start_end_means_never_quiet(self) -> None:
        assert is_quiet_hour(12, 8, 8) is False
        assert is_quiet_hour(8, 8, 8) is False


# ---------------------------------------------------------------------------
# ACK token stripping
# ---------------------------------------------------------------------------


class TestStripAckToken:
    def test_exact_token(self) -> None:
        assert _strip_ack_token("HEARTBEAT_OK", "HEARTBEAT_OK") == ""

    def test_token_with_whitespace(self) -> None:
        assert _strip_ack_token("  HEARTBEAT_OK  ", "HEARTBEAT_OK") == ""

    def test_leading_token(self) -> None:
        assert _strip_ack_token("HEARTBEAT_OK Some extra text", "HEARTBEAT_OK") == "Some extra text"

    def test_trailing_token(self) -> None:
        assert _strip_ack_token("Some text HEARTBEAT_OK", "HEARTBEAT_OK") == "Some text"

    def test_no_token(self) -> None:
        assert _strip_ack_token("Hello world", "HEARTBEAT_OK") == "Hello world"

    def test_empty_input(self) -> None:
        assert _strip_ack_token("", "HEARTBEAT_OK") == ""

    def test_token_in_middle_not_stripped(self) -> None:
        result = _strip_ack_token("Before HEARTBEAT_OK After", "HEARTBEAT_OK")
        # Leading strip removes HEARTBEAT_OK, leaving trailing intact
        assert "Before" not in result or "After" in result


# ---------------------------------------------------------------------------
# Observer lifecycle
# ---------------------------------------------------------------------------


def _make_config(*, enabled: bool = True, interval: int = 30) -> AgentConfig:
    return AgentConfig(
        heartbeat=HeartbeatConfig(enabled=enabled, interval_minutes=interval),
        allowed_user_ids=[100, 200],
    )


class TestHeartbeatObserverSetup:
    async def test_disabled_does_not_start_task(self) -> None:
        config = _make_config(enabled=False)
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock())
        await obs.start()
        assert obs._task is None
        await obs.stop()

    async def test_enabled_starts_task(self) -> None:
        config = _make_config(enabled=True)
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock())
        await obs.start()
        assert obs._task is not None
        await obs.stop()
        assert obs._task is None

    async def test_no_handler_does_not_start(self) -> None:
        config = _make_config(enabled=True)
        obs = HeartbeatObserver(config)
        await obs.start()
        assert obs._task is None


class TestHeartbeatObserverTick:
    async def test_tick_calls_handler_for_each_user(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value=None)
        obs.set_heartbeat_handler(handler)

        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick()

        assert handler.call_count == 2
        handler.assert_any_await(100, None, None)
        handler.assert_any_await(200, None, None)

    async def test_tick_skips_busy_chat(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value=None)
        obs.set_heartbeat_handler(handler)
        obs.set_busy_check(lambda cid: cid == 100)

        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick()

        handler.assert_awaited_once_with(200, None, None)

    async def test_tick_delivers_alert(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock(return_value="Hey, check this out!"))
        result_handler = AsyncMock()
        obs.set_result_handler(result_handler)

        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick()

        assert result_handler.call_count == 2
        result_handler.assert_any_await(100, "Hey, check this out!", None)
        result_handler.assert_any_await(200, "Hey, check this out!", None)

    async def test_tick_suppresses_none_result(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock(return_value=None))
        result_handler = AsyncMock()
        obs.set_result_handler(result_handler)

        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick()

        result_handler.assert_not_awaited()

    @pytest.mark.parametrize("hour", [21, 22, 23, 0, 1, 7])
    async def test_tick_skips_during_quiet_hours(self, hour: int) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value=None)
        obs.set_heartbeat_handler(handler)

        with time_machine.travel(datetime(2026, 1, 15, hour, 30, tzinfo=UTC)):
            await obs._tick()

        handler.assert_not_awaited()

    async def test_tick_runs_during_active_hours(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value=None)
        obs.set_heartbeat_handler(handler)

        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick()

        assert handler.call_count == 2

    async def test_handler_exception_does_not_crash(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock(side_effect=RuntimeError("boom")))

        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick()

    async def test_tick_propagates_cancelled_from_stale_cleanup(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock(return_value=None))
        obs.set_stale_cleanup(AsyncMock(side_effect=asyncio.CancelledError()))

        with (
            time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)),
            pytest.raises(asyncio.CancelledError),
        ):
            await obs._tick()

    async def test_run_for_chat_propagates_cancelled_from_handler(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock(side_effect=asyncio.CancelledError()))

        with pytest.raises(asyncio.CancelledError):
            await obs._run_for_chat(100)

    async def test_run_for_chat_propagates_cancelled_from_result_handler(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock(return_value="alert"))
        obs.set_result_handler(AsyncMock(side_effect=asyncio.CancelledError()))

        with pytest.raises(asyncio.CancelledError):
            await obs._run_for_chat(100)


# ---------------------------------------------------------------------------
# HeartbeatGroupTarget config validation
# ---------------------------------------------------------------------------


class TestHeartbeatGroupTargetConfig:
    def test_valid_group_target(self) -> None:
        cfg = HeartbeatConfig(
            enabled=True,
            group_targets=[
                HeartbeatGroupTarget(chat_id=-1001, topic_id=5, interval_minutes=10),
                HeartbeatGroupTarget(chat_id=-1002, prompt="Custom prompt"),
            ],
        )
        assert len(cfg.group_targets) == 2

    def test_duplicate_targets_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate heartbeat target"):
            HeartbeatConfig(
                enabled=True,
                group_targets=[
                    HeartbeatGroupTarget(chat_id=-1001, topic_id=5),
                    HeartbeatGroupTarget(chat_id=-1001, topic_id=5),
                ],
            )

    def test_same_chat_different_topic_allowed(self) -> None:
        cfg = HeartbeatConfig(
            enabled=True,
            group_targets=[
                HeartbeatGroupTarget(chat_id=-1001, topic_id=5),
                HeartbeatGroupTarget(chat_id=-1001, topic_id=10),
            ],
        )
        assert len(cfg.group_targets) == 2

    def test_quiet_hours_inherit_global(self) -> None:
        t = HeartbeatGroupTarget(chat_id=-1001)
        assert t.quiet_start is None
        assert t.quiet_end is None

    def test_disabled_target(self) -> None:
        t = HeartbeatGroupTarget(chat_id=-1001, enabled=False)
        assert not t.enabled


# ---------------------------------------------------------------------------
# Chat validation cache
# ---------------------------------------------------------------------------


class TestChatValidationCache:
    async def test_reachable_chat_cached(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        validator = AsyncMock(return_value=True)
        obs.set_chat_validator(validator)

        assert await obs._is_chat_reachable(100)
        assert await obs._is_chat_reachable(100)
        # Second call should use cache
        validator.assert_awaited_once_with(100)

    async def test_unreachable_chat_not_cached(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        validator = AsyncMock(return_value=False)
        obs.set_chat_validator(validator)

        assert not await obs._is_chat_reachable(100)
        assert not await obs._is_chat_reachable(100)
        assert validator.await_count == 2

    async def test_no_validator_always_reachable(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        assert await obs._is_chat_reachable(100)

    async def test_validator_exception_returns_false(self) -> None:
        config = _make_config()
        obs = HeartbeatObserver(config)
        obs.set_chat_validator(AsyncMock(side_effect=RuntimeError("net err")))
        assert not await obs._is_chat_reachable(100)


# ---------------------------------------------------------------------------
# Group target tick
# ---------------------------------------------------------------------------


def _make_target_config(
    *,
    target_chat_id: int = -1001,
    target_topic_id: int | None = 5,
    target_prompt: str = "Check status",
) -> AgentConfig:
    return AgentConfig(
        heartbeat=HeartbeatConfig(
            enabled=True,
            group_targets=[
                HeartbeatGroupTarget(
                    chat_id=target_chat_id,
                    topic_id=target_topic_id,
                    prompt=target_prompt,
                    interval_minutes=5,
                ),
            ],
        ),
        allowed_user_ids=[100, 200],
    )


class TestGroupTargetTick:
    async def test_tick_target_fires_handler_with_prompt(self) -> None:
        config = _make_target_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value="Server down!")
        obs.set_heartbeat_handler(handler)
        result_handler = AsyncMock()
        obs.set_result_handler(result_handler)

        target = config.heartbeat.group_targets[0]
        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick_target(target)

        handler.assert_awaited_once_with(-1001, 5, "Check status")
        result_handler.assert_awaited_once_with(-1001, "Server down!", 5)

    async def test_tick_target_quiet_hours_skip(self) -> None:
        config = _make_target_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value=None)
        obs.set_heartbeat_handler(handler)

        target = config.heartbeat.group_targets[0]
        with time_machine.travel(datetime(2026, 1, 15, 23, 0, tzinfo=UTC)):
            await obs._tick_target(target)

        handler.assert_not_awaited()

    async def test_tick_target_fallback_on_unreachable(self) -> None:
        config = _make_target_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value="Alert!")
        obs.set_heartbeat_handler(handler)
        result_handler = AsyncMock()
        obs.set_result_handler(result_handler)
        # Target chat unreachable, fallback chat reachable
        obs.set_chat_validator(AsyncMock(side_effect=lambda cid: cid != -1001))

        target = config.heartbeat.group_targets[0]
        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick_target(target)

        # Should fallback to private chat (100), topic_id=None
        handler.assert_awaited_once_with(100, None, "Check status")
        result_handler.assert_awaited_once_with(100, "Alert!", None)

    async def test_tick_target_no_fallback_available(self) -> None:
        config = AgentConfig(
            heartbeat=HeartbeatConfig(
                enabled=True,
                group_targets=[
                    HeartbeatGroupTarget(chat_id=-1001, interval_minutes=5),
                ],
            ),
            allowed_user_ids=[],
        )
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value="Alert!")
        obs.set_heartbeat_handler(handler)
        obs.set_chat_validator(AsyncMock(return_value=False))

        target = config.heartbeat.group_targets[0]
        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick_target(target)

        handler.assert_not_awaited()

    async def test_tick_target_skips_busy_chat(self) -> None:
        config = _make_target_config()
        obs = HeartbeatObserver(config)
        handler = AsyncMock(return_value="Alert!")
        obs.set_heartbeat_handler(handler)
        obs.set_busy_check(lambda _cid: True)

        target = config.heartbeat.group_targets[0]
        with time_machine.travel(datetime(2026, 1, 15, 14, 0, tzinfo=UTC)):
            await obs._tick_target(target)

        handler.assert_not_awaited()


# ---------------------------------------------------------------------------
# Reconcile target tasks
# ---------------------------------------------------------------------------


class TestReconcileTargetTasks:
    async def test_reconcile_starts_new_targets(self) -> None:
        config = _make_target_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock())
        obs._running = True

        await obs.reconcile_target_tasks()
        assert len(obs._target_tasks) == 1
        # Cleanup
        for t in obs._target_tasks:
            t.cancel()
        await asyncio.gather(*obs._target_tasks, return_exceptions=True)
        obs._target_tasks.clear()

    async def test_reconcile_clears_when_not_running(self) -> None:
        config = _make_target_config()
        obs = HeartbeatObserver(config)
        obs.set_heartbeat_handler(AsyncMock())
        obs._running = False

        await obs.reconcile_target_tasks()
        assert len(obs._target_tasks) == 0


# ---------------------------------------------------------------------------
# _find_target
# ---------------------------------------------------------------------------


class TestFindTarget:
    def test_find_existing(self) -> None:
        config = _make_target_config(target_chat_id=-1001, target_topic_id=5)
        obs = HeartbeatObserver(config)
        found = obs._find_target(-1001, 5)
        assert found is not None
        assert found.chat_id == -1001

    def test_find_nonexistent(self) -> None:
        config = _make_target_config(target_chat_id=-1001, target_topic_id=5)
        obs = HeartbeatObserver(config)
        assert obs._find_target(-9999, 5) is None

    def test_find_topic_mismatch(self) -> None:
        config = _make_target_config(target_chat_id=-1001, target_topic_id=5)
        obs = HeartbeatObserver(config)
        assert obs._find_target(-1001, 99) is None
