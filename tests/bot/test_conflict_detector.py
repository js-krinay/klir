"""Tests for 409 conflict detection during polling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramConflictError


class TestConflictDetector:
    def test_initial_state(self) -> None:
        from klir.bot.conflict_detector import ConflictDetector

        detector = ConflictDetector()
        assert detector.conflict_detected is False
        assert detector.conflict_count == 0

    def test_record_conflict(self) -> None:
        from klir.bot.conflict_detector import ConflictDetector

        detector = ConflictDetector()
        err = TelegramConflictError(method=None, message="Conflict")  # type: ignore[arg-type]
        detector.record(err)
        assert detector.conflict_detected is True
        assert detector.conflict_count == 1

    def test_multiple_conflicts(self) -> None:
        from klir.bot.conflict_detector import ConflictDetector

        detector = ConflictDetector()
        err = TelegramConflictError(method=None, message="Conflict")  # type: ignore[arg-type]
        detector.record(err)
        detector.record(err)
        assert detector.conflict_count == 2

    def test_reset(self) -> None:
        from klir.bot.conflict_detector import ConflictDetector

        detector = ConflictDetector()
        err = TelegramConflictError(method=None, message="Conflict")  # type: ignore[arg-type]
        detector.record(err)
        detector.reset()
        assert detector.conflict_detected is False
        assert detector.conflict_count == 0

    @pytest.mark.asyncio
    async def test_on_conflict_callback_called(self) -> None:
        from klir.bot.conflict_detector import ConflictDetector

        callback = AsyncMock()
        detector = ConflictDetector(on_conflict=callback)
        err = TelegramConflictError(method=None, message="Conflict")  # type: ignore[arg-type]
        await detector.record_async(err)
        callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_conflict_callback_not_called_for_other_errors(self) -> None:
        from klir.bot.conflict_detector import ConflictDetector

        callback = AsyncMock()
        detector = ConflictDetector(on_conflict=callback)
        err = ValueError("not a conflict")
        await detector.record_async(err)
        callback.assert_not_awaited()
        assert detector.conflict_count == 0
