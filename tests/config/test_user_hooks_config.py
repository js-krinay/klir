"""Tests for user message hook configuration models."""

from __future__ import annotations

import pytest

from klir.config import AgentConfig, UserMessageHookConfig


def test_default_config_has_empty_hooks() -> None:
    cfg = AgentConfig()
    assert cfg.message_hooks == []


def test_hook_config_parses_minimal() -> None:
    hook = UserMessageHookConfig(name="greet", phase="pre", action="prepend", text="Hello: ")
    assert hook.name == "greet"
    assert hook.phase == "pre"
    assert hook.action == "prepend"
    assert hook.text == "Hello: "
    assert hook.condition == "always"


def test_hook_config_parses_regex_condition() -> None:
    hook = UserMessageHookConfig(
        name="code",
        phase="pre",
        action="prepend",
        text="[code] ",
        condition="regex",
        pattern=r"^/code\s",
    )
    assert hook.condition == "regex"
    assert hook.pattern == r"^/code\s"


def test_hook_config_parses_provider_condition() -> None:
    hook = UserMessageHookConfig(
        name="claude-only",
        phase="post",
        action="append",
        text="\n---",
        condition="provider",
        provider="claude",
    )
    assert hook.condition == "provider"
    assert hook.provider == "claude"


def test_hook_config_rejects_invalid_phase() -> None:
    with pytest.raises(ValueError, match="phase"):
        UserMessageHookConfig(name="bad", phase="middle", action="prepend", text="x")  # type: ignore[arg-type]


def test_hook_config_rejects_invalid_action() -> None:
    with pytest.raises(ValueError, match="action"):
        UserMessageHookConfig(name="bad", phase="pre", action="delete", text="x")  # type: ignore[arg-type]


def test_config_round_trips_hooks() -> None:
    raw = {
        "message_hooks": [
            {"name": "h1", "phase": "pre", "action": "prepend", "text": "PREFIX: "},
        ]
    }
    cfg = AgentConfig(**raw)  # type: ignore[arg-type]
    assert len(cfg.message_hooks) == 1
    assert cfg.message_hooks[0].name == "h1"
