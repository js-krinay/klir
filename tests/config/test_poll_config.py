"""Tests for PollConfig."""

from __future__ import annotations


class TestPollConfig:
    def test_default_disabled(self) -> None:
        from klir.config import PollConfig

        cfg = PollConfig()
        assert cfg.enabled is False

    def test_default_anonymous(self) -> None:
        from klir.config import PollConfig

        cfg = PollConfig()
        assert cfg.is_anonymous is True

    def test_agent_config_includes_polls(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.polls.enabled is False
