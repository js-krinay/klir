"""Tests for channel ID config."""

from __future__ import annotations


class TestChannelConfig:
    def test_default_empty(self) -> None:
        from ductor_bot.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.allowed_channel_ids == []

    def test_set_channel_ids(self) -> None:
        from ductor_bot.config import AgentConfig

        cfg = AgentConfig(
            telegram_token="test:token",
            allowed_channel_ids=[-1001234567890],
        )
        assert -1001234567890 in cfg.allowed_channel_ids
