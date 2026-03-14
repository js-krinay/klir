"""Tests for structured error logging in retry logic."""

from __future__ import annotations

import logging

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramServerError


class TestRetryLogging:
    @pytest.mark.asyncio
    async def test_recoverable_error_logs_context(self, caplog: pytest.LogCaptureFixture) -> None:
        from unittest.mock import AsyncMock

        from klir.bot.retry import retry_async
        from klir.config import ResilienceConfig

        fn = AsyncMock(
            side_effect=[
                TelegramServerError(method=None, message="Internal Error"),  # type: ignore[arg-type]
                "ok",
            ]
        )
        cfg = ResilienceConfig(base_backoff_seconds=0.01, max_backoff_seconds=0.1)

        with caplog.at_level(logging.WARNING, logger="klir.bot.retry"):
            await retry_async(fn, config=cfg, context="sendMessage")

        assert any("sendMessage" in r.message for r in caplog.records)
        assert any("attempt 1/" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_exhausted_retries_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        from unittest.mock import AsyncMock

        from klir.bot.retry import retry_async
        from klir.config import ResilienceConfig

        fn = AsyncMock(side_effect=TelegramNetworkError(method=None, message="timeout"))  # type: ignore[arg-type]
        cfg = ResilienceConfig(max_retries=1, base_backoff_seconds=0.01, max_backoff_seconds=0.1)

        with (
            caplog.at_level(logging.ERROR, logger="klir.bot.retry"),
            pytest.raises(TelegramNetworkError),
        ):
            await retry_async(fn, config=cfg, context="getUpdates")

        assert any("Retries exhausted" in r.message for r in caplog.records)
        assert any("getUpdates" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_conflict_logs_error_with_instance_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from unittest.mock import AsyncMock

        from aiogram.exceptions import TelegramConflictError

        from klir.bot.retry import retry_async
        from klir.config import ResilienceConfig

        fn = AsyncMock(side_effect=TelegramConflictError(method=None, message="Conflict"))  # type: ignore[arg-type]
        cfg = ResilienceConfig()

        with (
            caplog.at_level(logging.ERROR, logger="klir.bot.retry"),
            pytest.raises(TelegramConflictError),
        ):
            await retry_async(fn, config=cfg, context="getUpdates")

        assert any("another bot instance" in r.message for r in caplog.records)
