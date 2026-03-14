"""Tests for reply_to_mode configuration."""

from __future__ import annotations

import pytest


class TestReplyToModeConfig:
    def test_default_is_first(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig()
        assert cfg.reply_to_mode == "first"

    def test_accepts_off(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(reply_to_mode="off")
        assert cfg.reply_to_mode == "off"

    def test_accepts_all(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(reply_to_mode="all")
        assert cfg.reply_to_mode == "all"

    def test_rejects_invalid_value(self) -> None:
        from pydantic import ValidationError

        from klir.config import AgentConfig

        with pytest.raises(ValidationError):
            AgentConfig(reply_to_mode="invalid")  # type: ignore[arg-type]


class TestChatOverridesReplyToMode:
    def test_default_is_none(self) -> None:
        from klir.config import ChatOverrides

        overrides = ChatOverrides()
        assert overrides.reply_to_mode is None

    def test_accepts_valid_mode(self) -> None:
        from klir.config import ChatOverrides

        overrides = ChatOverrides(reply_to_mode="all")
        assert overrides.reply_to_mode == "all"

    def test_rejects_invalid_value(self) -> None:
        from pydantic import ValidationError

        from klir.config import ChatOverrides

        with pytest.raises(ValidationError):
            ChatOverrides(reply_to_mode="invalid")  # type: ignore[arg-type]
