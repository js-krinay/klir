"""Tests for ChatConfigResolver."""

from __future__ import annotations

import pytest


def _make_config(**kwargs: object):
    from ductor_bot.config import AgentConfig

    defaults = {"telegram_token": "test:token", "provider": "claude", "model": "opus"}
    defaults.update(kwargs)
    return AgentConfig(**defaults)


class TestChatConfigResolver:
    def test_no_overrides_returns_global(self) -> None:
        from ductor_bot.config_resolver import ChatConfigResolver

        cfg = _make_config()
        resolver = ChatConfigResolver(cfg)

        assert resolver.provider(chat_id=123) == "claude"
        assert resolver.model(chat_id=123) == "opus"

    def test_wildcard_override(self) -> None:
        from ductor_bot.config_resolver import ChatConfigResolver

        cfg = _make_config(chat_overrides={"*": {"model": "sonnet"}})
        resolver = ChatConfigResolver(cfg)

        assert resolver.model(chat_id=999) == "sonnet"
        assert resolver.provider(chat_id=999) == "claude"  # not overridden

    def test_specific_chat_overrides_wildcard(self) -> None:
        from ductor_bot.config_resolver import ChatConfigResolver

        cfg = _make_config(
            chat_overrides={
                "*": {"model": "sonnet"},
                "-100555": {"model": "flash", "provider": "gemini"},
            },
        )
        resolver = ChatConfigResolver(cfg)

        # Specific chat
        assert resolver.model(chat_id=-100555) == "flash"
        assert resolver.provider(chat_id=-100555) == "gemini"

        # Other chat gets wildcard
        assert resolver.model(chat_id=999) == "sonnet"
        assert resolver.provider(chat_id=999) == "claude"

    def test_enabled_false_disables_chat(self) -> None:
        from ductor_bot.config_resolver import ChatConfigResolver

        cfg = _make_config(
            chat_overrides={"-100666": {"enabled": False}},
        )
        resolver = ChatConfigResolver(cfg)

        assert resolver.is_enabled(chat_id=-100666) is False
        assert resolver.is_enabled(chat_id=123) is True

    def test_group_mention_only_override(self) -> None:
        from ductor_bot.config_resolver import ChatConfigResolver

        cfg = _make_config(
            group_mention_only=False,
            chat_overrides={"-100777": {"group_mention_only": True}},
        )
        resolver = ChatConfigResolver(cfg)

        assert resolver.group_mention_only(chat_id=-100777) is True
        assert resolver.group_mention_only(chat_id=123) is False

    def test_reload_updates_overrides(self) -> None:
        from ductor_bot.config_resolver import ChatConfigResolver

        cfg = _make_config()
        resolver = ChatConfigResolver(cfg)
        assert resolver.model(chat_id=1) == "opus"

        cfg2 = _make_config(chat_overrides={"1": {"model": "haiku"}})
        resolver.reload(cfg2)
        assert resolver.model(chat_id=1) == "haiku"
