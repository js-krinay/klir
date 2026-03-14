"""Tests for ChatOverrides Pydantic model."""

from __future__ import annotations


class TestChatOverrides:
    def test_empty_overrides_all_none(self) -> None:
        from klir.config import ChatOverrides

        ov = ChatOverrides()
        assert ov.provider is None
        assert ov.model is None
        assert ov.streaming is None
        assert ov.group_mention_only is None
        assert ov.require_mention is None
        assert ov.enabled is None

    def test_partial_overrides(self) -> None:
        from klir.config import ChatOverrides

        ov = ChatOverrides(provider="gemini", model="flash")
        assert ov.provider == "gemini"
        assert ov.model == "flash"
        assert ov.streaming is None

    def test_enabled_field(self) -> None:
        from klir.config import ChatOverrides

        ov = ChatOverrides(enabled=False)
        assert ov.enabled is False

    def test_from_dict(self) -> None:
        from klir.config import ChatOverrides

        ov = ChatOverrides(provider="codex", model="o4-mini")
        assert ov.provider == "codex"
        assert ov.model == "o4-mini"

    def test_agent_config_chat_overrides_field(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(
            telegram_token="test:token",
            chat_overrides={
                "-100123": {"provider": "gemini"},
                "*": {"model": "sonnet"},
            },
        )
        assert "-100123" in cfg.chat_overrides
        assert "*" in cfg.chat_overrides

    def test_agent_config_default_empty_overrides(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.chat_overrides == {}
