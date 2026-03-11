"""Integration test: reply_to_mode resolves from config and reaches dispatch."""

from __future__ import annotations


class TestReplyToModeResolution:
    def test_resolve_mode_global_default(self) -> None:
        """Global config reply_to_mode is used when no chat override exists."""
        from klir.config import AgentConfig

        cfg = AgentConfig(reply_to_mode="all")
        assert cfg.reply_to_mode == "all"

    def test_resolve_mode_chat_override(self) -> None:
        """ChatOverrides.reply_to_mode takes precedence over global."""
        from klir.config import AgentConfig, ChatOverrides

        cfg = AgentConfig(reply_to_mode="first")
        override = ChatOverrides(reply_to_mode="off")
        resolved = override.reply_to_mode if override.reply_to_mode is not None else cfg.reply_to_mode
        assert resolved == "off"

    def test_resolve_mode_chat_override_none_falls_back(self) -> None:
        """When ChatOverrides.reply_to_mode is None, global config is used."""
        from klir.config import AgentConfig, ChatOverrides

        cfg = AgentConfig(reply_to_mode="all")
        override = ChatOverrides()
        resolved = override.reply_to_mode if override.reply_to_mode is not None else cfg.reply_to_mode
        assert resolved == "all"

    def test_resolver_returns_global_when_no_override(self) -> None:
        """ChatConfigResolver.reply_to_mode falls back to AgentConfig."""
        from klir.config import AgentConfig
        from klir.config_resolver import ChatConfigResolver

        cfg = AgentConfig(reply_to_mode="off")
        resolver = ChatConfigResolver(cfg)
        assert resolver.reply_to_mode(chat_id=999) == "off"

    def test_resolver_returns_override_when_set(self) -> None:
        """ChatConfigResolver.reply_to_mode returns per-chat override."""
        from klir.config import AgentConfig
        from klir.config_resolver import ChatConfigResolver

        cfg = AgentConfig(
            reply_to_mode="first",
            chat_overrides={"42": {"reply_to_mode": "all"}},
        )
        resolver = ChatConfigResolver(cfg)
        assert resolver.reply_to_mode(chat_id=42) == "all"
        assert resolver.reply_to_mode(chat_id=999) == "first"
