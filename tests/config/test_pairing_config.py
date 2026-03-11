"""Tests for PairingConfig defaults and validation."""

from __future__ import annotations


class TestPairingConfig:
    def test_default_disabled(self) -> None:
        from klir.config import PairingConfig

        cfg = PairingConfig()
        assert cfg.enabled is False

    def test_default_ttl_one_hour(self) -> None:
        from klir.config import PairingConfig

        cfg = PairingConfig()
        assert cfg.code_ttl_minutes == 60

    def test_code_length_default(self) -> None:
        from klir.config import PairingConfig

        cfg = PairingConfig()
        assert cfg.code_length == 6

    def test_agent_config_includes_pairing(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.pairing.enabled is False
