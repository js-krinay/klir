"""Tests for ReactionConfig defaults and validation."""

from __future__ import annotations

import pytest


class TestReactionConfig:
    def test_default_level_is_ack(self) -> None:
        from klir.config import ReactionConfig

        cfg = ReactionConfig()
        assert cfg.level == "ack"

    def test_valid_levels(self) -> None:
        from klir.config import ReactionConfig

        for level in ("off", "ack"):
            cfg = ReactionConfig(level=level)
            assert cfg.level == level

    def test_invalid_level_rejected(self) -> None:
        from klir.config import ReactionConfig

        with pytest.raises(ValueError):
            ReactionConfig(level="invalid")

    def test_default_emojis(self) -> None:
        from klir.config import ReactionConfig

        cfg = ReactionConfig()
        assert cfg.ack_emoji == "👀"
        assert cfg.done_emoji == "✅"
        assert cfg.error_emoji == "❌"

    def test_agent_config_includes_reactions(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.reactions.level == "ack"
