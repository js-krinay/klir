"""Tests for ForwardingConfig defaults and AgentConfig integration."""

from __future__ import annotations


class TestForwardingConfig:
    def test_default_disabled(self) -> None:
        from ductor_bot.config import ForwardingConfig

        cfg = ForwardingConfig()
        assert cfg.enabled is False

    def test_agent_config_has_forwarding(self) -> None:
        from ductor_bot.config import AgentConfig

        cfg = AgentConfig()
        assert cfg.forwarding.enabled is False

    def test_allowed_forward_targets_from_agent_config(self) -> None:
        from ductor_bot.config import AgentConfig

        cfg = AgentConfig(
            allowed_user_ids=[100],
            allowed_group_ids=[-200],
            allowed_channel_ids=[-300],
        )
        targets = cfg.allowed_forward_targets
        assert targets == {100, -200, -300}

    def test_allowed_forward_targets_empty(self) -> None:
        from ductor_bot.config import AgentConfig

        cfg = AgentConfig()
        assert cfg.allowed_forward_targets == set()
