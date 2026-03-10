"""Tests for PairingService."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest


def _make_config(enabled: bool = True, ttl: int = 60, length: int = 6) -> MagicMock:
    cfg = MagicMock()
    cfg.pairing.enabled = enabled
    cfg.pairing.code_ttl_minutes = ttl
    cfg.pairing.code_length = length
    cfg.pairing.max_active_codes = 10
    return cfg


class TestPairingService:
    def test_generate_code_returns_alphanumeric(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        code = svc.generate_code(admin_user_id=100)

        assert len(code) == 6
        assert code.isalnum()

    def test_generate_code_unique(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        codes = {svc.generate_code(admin_user_id=100) for _ in range(20)}
        # With 6 alphanum chars, collision in 20 codes is astronomically unlikely
        assert len(codes) == 20

    def test_validate_correct_code(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        code = svc.generate_code(admin_user_id=100)

        result = svc.validate(code, user_id=200)
        assert result is True

    def test_validate_wrong_code(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        svc.generate_code(admin_user_id=100)

        result = svc.validate("XXXXXX", user_id=200)
        assert result is False

    def test_code_is_single_use(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        code = svc.generate_code(admin_user_id=100)

        assert svc.validate(code, user_id=200) is True
        assert svc.validate(code, user_id=300) is False  # already consumed

    def test_expired_code_rejected(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config(ttl=0))  # 0 minute TTL = immediate expiry
        code = svc.generate_code(admin_user_id=100)

        # Force expiry by setting created_at to past
        for entry in svc._codes.values():
            entry["created_at"] = time.time() - 1

        result = svc.validate(code, user_id=200)
        assert result is False

    def test_list_active_codes(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        code1 = svc.generate_code(admin_user_id=100)
        code2 = svc.generate_code(admin_user_id=100)

        active = svc.list_active()
        assert len(active) == 2

    def test_revoke_code(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config())
        code = svc.generate_code(admin_user_id=100)

        svc.revoke(code)
        assert svc.validate(code, user_id=200) is False

    def test_disabled_service_rejects(self) -> None:
        from ductor_bot.pairing import PairingService

        svc = PairingService(_make_config(enabled=False))
        code = svc.generate_code(admin_user_id=100)

        result = svc.validate(code, user_id=200)
        assert result is False
