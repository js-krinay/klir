"""Tests for Telegram API error classification and retry logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramConflictError,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
)


class TestClassifyError:
    def test_bad_request_is_permanent(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramBadRequest(method=None, message="Bad Request")
        assert classify_error(err) is ErrorClass.PERMANENT

    def test_forbidden_is_permanent(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramForbiddenError(method=None, message="Forbidden")
        assert classify_error(err) is ErrorClass.PERMANENT

    def test_not_found_is_permanent(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramNotFound(method=None, message="Not Found")
        assert classify_error(err) is ErrorClass.PERMANENT

    def test_conflict_is_conflict(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramConflictError(method=None, message="Conflict")
        assert classify_error(err) is ErrorClass.CONFLICT

    def test_retry_after_is_rate_limited(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramRetryAfter(method=None, message="Retry After", retry_after=5)
        assert classify_error(err) is ErrorClass.RATE_LIMITED

    def test_server_error_is_recoverable(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramServerError(method=None, message="Internal Server Error")
        assert classify_error(err) is ErrorClass.RECOVERABLE

    def test_network_error_is_recoverable(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        err = TelegramNetworkError(method=None, message="Network Error")
        assert classify_error(err) is ErrorClass.RECOVERABLE

    def test_unknown_exception_is_permanent(self) -> None:
        from klir.bot.retry import ErrorClass, classify_error

        assert classify_error(ValueError("unexpected")) is ErrorClass.PERMANENT


class TestComputeBackoff:
    def test_exponential_growth(self) -> None:
        from klir.bot.retry import compute_backoff

        b0 = compute_backoff(attempt=0, base=1.0, maximum=30.0, jitter=False)
        b1 = compute_backoff(attempt=1, base=1.0, maximum=30.0, jitter=False)
        b2 = compute_backoff(attempt=2, base=1.0, maximum=30.0, jitter=False)
        assert b0 == 1.0
        assert b1 == 2.0
        assert b2 == 4.0

    def test_capped_at_maximum(self) -> None:
        from klir.bot.retry import compute_backoff

        result = compute_backoff(attempt=10, base=1.0, maximum=30.0, jitter=False)
        assert result == 30.0

    def test_jitter_stays_in_range(self) -> None:
        from klir.bot.retry import compute_backoff

        for _ in range(50):
            result = compute_backoff(attempt=0, base=1.0, maximum=30.0, jitter=True)
            assert 0.0 <= result <= 1.0

    def test_custom_base(self) -> None:
        from klir.bot.retry import compute_backoff

        result = compute_backoff(attempt=0, base=2.0, maximum=60.0, jitter=False)
        assert result == 2.0


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(return_value="ok")
        result = await retry_async(fn, config=ResilienceConfig())
        assert result == "ok"
        fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_on_recoverable_then_succeeds(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(
            side_effect=[
                TelegramServerError(method=None, message="err"),
                "ok",
            ]
        )
        cfg = ResilienceConfig(base_backoff_seconds=0.01, max_backoff_seconds=0.1)
        result = await retry_async(fn, config=cfg)
        assert result == "ok"
        assert fn.await_count == 2

    @pytest.mark.asyncio
    async def test_raises_permanent_immediately(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(
            side_effect=TelegramBadRequest(method=None, message="Bad Request")
        )
        cfg = ResilienceConfig(max_retries=3)
        with pytest.raises(TelegramBadRequest):
            await retry_async(fn, config=cfg)
        fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exhausts_retries_then_raises(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(
            side_effect=TelegramServerError(method=None, message="err")
        )
        cfg = ResilienceConfig(
            max_retries=2, base_backoff_seconds=0.01, max_backoff_seconds=0.1
        )
        with pytest.raises(TelegramServerError):
            await retry_async(fn, config=cfg)
        assert fn.await_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_rate_limited_uses_retry_after(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(
            side_effect=[
                TelegramRetryAfter(method=None, message="Rate", retry_after=0.01),
                "ok",
            ]
        )
        cfg = ResilienceConfig(base_backoff_seconds=0.01, max_backoff_seconds=0.1)
        result = await retry_async(fn, config=cfg)
        assert result == "ok"
        assert fn.await_count == 2

    @pytest.mark.asyncio
    async def test_conflict_raises_immediately(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(
            side_effect=TelegramConflictError(method=None, message="Conflict")
        )
        cfg = ResilienceConfig(max_retries=3)
        with pytest.raises(TelegramConflictError):
            await retry_async(fn, config=cfg)
        fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_network_error_retried(self) -> None:
        from klir.config import ResilienceConfig
        from klir.bot.retry import retry_async

        fn = AsyncMock(
            side_effect=[
                TelegramNetworkError(method=None, message="timeout"),
                TelegramNetworkError(method=None, message="timeout"),
                "ok",
            ]
        )
        cfg = ResilienceConfig(
            max_retries=3, base_backoff_seconds=0.01, max_backoff_seconds=0.1
        )
        result = await retry_async(fn, config=cfg)
        assert result == "ok"
        assert fn.await_count == 3
