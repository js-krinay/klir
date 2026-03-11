"""Tests for ApprovalConfig defaults and validation."""

from __future__ import annotations


class TestApprovalConfig:
    def test_default_disabled(self) -> None:
        from klir.config import ApprovalConfig

        cfg = ApprovalConfig()
        assert cfg.enabled is False

    def test_default_timeout(self) -> None:
        from klir.config import ApprovalConfig

        cfg = ApprovalConfig()
        assert cfg.timeout_seconds == 120

    def test_default_target_dm(self) -> None:
        from klir.config import ApprovalConfig

        cfg = ApprovalConfig()
        assert cfg.target == "dm"

    def test_approver_ids_default_empty(self) -> None:
        from klir.config import ApprovalConfig

        cfg = ApprovalConfig()
        assert cfg.approver_ids == []

    def test_auto_approve_tools_default_empty(self) -> None:
        from klir.config import ApprovalConfig

        cfg = ApprovalConfig()
        assert cfg.auto_approve_tools == []

    def test_agent_config_includes_approval(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.approval.enabled is False
