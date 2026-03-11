"""Tests for ApprovalService."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_config(
    enabled: bool = True,
    timeout: int = 5,
    auto_approve: list[str] | None = None,
) -> MagicMock:
    cfg = MagicMock()
    cfg.approval.enabled = enabled
    cfg.approval.approver_ids = [100]
    cfg.approval.timeout_seconds = timeout
    cfg.approval.target = "dm"
    cfg.approval.auto_approve_tools = auto_approve or []
    cfg.approval.auto_deny_on_timeout = True
    return cfg


class TestApprovalService:
    async def test_request_creates_pending(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config())
        req_id = svc.request_approval(
            tool_name="Write",
            tool_id="tool_1",
            chat_id=42,
            parameters={"path": "/tmp/test.py"},
        )

        assert req_id is not None
        assert svc.has_pending(req_id)

    async def test_approve_resolves_future(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config())
        req_id = svc.request_approval(
            tool_name="Write", tool_id="tool_1", chat_id=42,
        )

        result = svc.resolve(req_id, approved=True)
        assert result is True
        assert not svc.has_pending(req_id)

    async def test_deny_resolves_future(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config())
        req_id = svc.request_approval(
            tool_name="Write", tool_id="tool_1", chat_id=42,
        )

        result = svc.resolve(req_id, approved=False)
        assert result is True
        assert not svc.has_pending(req_id)

    async def test_auto_approve_tool(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config(auto_approve=["Read", "Glob"]))
        assert svc.is_auto_approved("Read") is True
        assert svc.is_auto_approved("Write") is False

    async def test_disabled_service_auto_approves_all(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config(enabled=False))
        assert svc.is_auto_approved("Write") is True

    def test_list_pending(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config())
        svc.request_approval(tool_name="Write", tool_id="t1", chat_id=42)
        svc.request_approval(tool_name="Bash", tool_id="t2", chat_id=42)

        pending = svc.list_pending()
        assert len(pending) == 2

    def test_resolve_unknown_id_returns_false(self) -> None:
        from klir.approval import ApprovalService

        svc = ApprovalService(_make_config())
        assert svc.resolve("nonexistent", approved=True) is False
