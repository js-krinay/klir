"""Tests for allowed_tools / disallowed_tools configuration."""

from __future__ import annotations

from klir.cli.service import CLIServiceConfig
from klir.config import AgentConfig


def test_allowed_tools_defaults_empty() -> None:
    cfg = AgentConfig()
    assert cfg.allowed_tools == []


def test_disallowed_tools_defaults_empty() -> None:
    cfg = AgentConfig()
    assert cfg.disallowed_tools == []


def test_allowed_tools_from_dict() -> None:
    cfg = AgentConfig(allowed_tools=["Read", "Grep", "Write"])
    assert cfg.allowed_tools == ["Read", "Grep", "Write"]


def test_disallowed_tools_from_dict() -> None:
    cfg = AgentConfig(disallowed_tools=["Bash"])
    assert cfg.disallowed_tools == ["Bash"]


def test_cli_service_config_stores_tool_filters() -> None:
    svc = CLIServiceConfig(
        working_dir="/workspace",
        default_model="sonnet",
        provider="claude",
        max_turns=10,
        max_budget_usd=None,
        permission_mode="normal",
        allowed_tools=("Read", "Grep"),
        disallowed_tools=("Bash",),
    )
    assert svc.allowed_tools == ("Read", "Grep")
    assert svc.disallowed_tools == ("Bash",)


def test_cli_service_config_tool_filters_default_empty() -> None:
    svc = CLIServiceConfig(
        working_dir="/workspace",
        default_model="sonnet",
        provider="claude",
        max_turns=10,
        max_budget_usd=None,
        permission_mode="normal",
    )
    assert svc.allowed_tools == ()
    assert svc.disallowed_tools == ()
