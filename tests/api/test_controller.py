"""Tests for DashboardController business logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from klir.api.controller import DashboardController
from klir.cron.run_log import CronRunLogEntry, RunLogPage

# ── Fake domain objects ───────────────────────────────────────────────


@dataclass
class FakeSession:
    chat_id: int = 100
    topic_id: int | None = None
    user_id: int | None = None
    topic_name: str = ""
    provider: str = "claude"
    model: str = "opus"
    session_id: str = "s1"
    message_count: int = 5
    total_cost_usd: float = 0.01
    total_tokens: int = 1000
    created_at: float = 1.0
    last_active: float = 2.0
    thinking_level: str | None = None


@dataclass
class FakeNamedSession:
    name: str = "bg1"
    chat_id: int = 100
    provider: str = "claude"
    model: str = "opus"
    session_id: str = "ns1"
    prompt_preview: str = "hello"
    status: str = "running"
    created_at: float = 1.0
    message_count: int = 3


@dataclass
class FakeAgentHealth:
    status: str = "healthy"
    uptime_seconds: float = 600.0
    restart_count: int = 0
    last_crash_time: float | None = None
    last_crash_error: str | None = None


@dataclass
class FakeCronJob:
    id: str = "cj1"
    title: str = "daily check"
    schedule: str = "0 9 * * *"
    enabled: bool = True
    consecutive_errors: int = 0
    last_error: str | None = None
    last_duration_ms: int | None = None
    provider: str = "claude"
    model: str = "opus"


@dataclass
class FakeTaskEntry:
    task_id: str = "t1"
    chat_id: int = 100
    parent_agent: str = "main"
    name: str = "test task"
    prompt_preview: str = "do stuff"
    provider: str = "claude"
    model: str = "opus"
    status: str = "running"
    created_at: float = 1.0
    completed_at: float | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None
    num_turns: int = 1
    question_count: int = 0
    last_question: str | None = None


@dataclass
class FakeProcess:
    pid: int = 123


@dataclass
class FakeTrackedProcess:
    chat_id: int = 100
    label: str = "claude"
    process: FakeProcess | None = None
    registered_at: float = 1.0

    def __post_init__(self) -> None:
        if self.process is None:
            self.process = FakeProcess()


@dataclass
class FakeResult:
    text: str = "response text"


@dataclass
class FakeToolActivity:
    """Mimics ToolActivity for streaming tests."""

    name: str = "search"
    file_path: str | None = None
    command: str | None = None

    def display_label(self) -> str:
        detail = self.file_path or self.command
        if detail is None:
            return self.name
        return f"{self.name}: {detail}"


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def controller() -> DashboardController:
    session_mgr = MagicMock()
    session_mgr.list_all = AsyncMock(return_value=[FakeSession()])

    named_registry = MagicMock()
    named_registry.list_all_active = MagicMock(return_value=[FakeNamedSession()])

    cron_mgr = MagicMock()
    cron_mgr.list_jobs = MagicMock(return_value=[FakeCronJob()])
    cron_mgr.get_job = MagicMock(return_value=FakeCronJob())
    cron_mgr.set_enabled = MagicMock(return_value=True)

    task_registry = MagicMock()
    task_registry.list_all = MagicMock(return_value=[FakeTaskEntry()])
    task_registry.delete = MagicMock(return_value=True)

    process_registry = MagicMock()
    process_registry.list_all_active = MagicMock(return_value=[FakeTrackedProcess()])

    message_handler = AsyncMock(return_value=FakeResult())
    abort_handler = AsyncMock(return_value=2)

    history_store = MagicMock()
    history_store.query = AsyncMock(return_value=([{"ts": 1.0, "text": "hi"}], False))

    dashboard_hub = MagicMock()
    dashboard_hub.client_count = 3

    observer_status_getter = MagicMock(return_value={"cron": "running"})
    config_summary_getter = MagicMock(return_value={"provider": "claude"})
    agent_health_getter = MagicMock(return_value={"main": FakeAgentHealth()})

    db = MagicMock()

    task_cancel = AsyncMock(return_value=True)

    return DashboardController(
        session_mgr=session_mgr,
        named_registry=named_registry,
        cron_mgr=cron_mgr,
        task_registry_getter=lambda: task_registry,
        process_registry=process_registry,
        task_cancel=task_cancel,
        message_handler=message_handler,
        abort_handler=abort_handler,
        history_store=history_store,
        dashboard_hub=dashboard_hub,
        observer_status_getter=observer_status_getter,
        config_summary_getter=config_summary_getter,
        agent_health_getter=agent_health_getter,
        db=db,
    )


# ── Tests ─────────────────────────────────────────────────────────────


class TestListSessions:
    async def test_returns_all(self, controller: DashboardController) -> None:
        result = await controller.list_sessions()
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["chat_id"] == 100

    async def test_filters_by_chat_id(self, controller: DashboardController) -> None:
        result = await controller.list_sessions(chat_id=999)
        assert result["sessions"] == []

    async def test_filters_matching_chat_id(self, controller: DashboardController) -> None:
        result = await controller.list_sessions(chat_id=100)
        assert len(result["sessions"]) == 1


class TestListNamedSessions:
    async def test_returns_all(self, controller: DashboardController) -> None:
        result = await controller.list_named_sessions()
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["name"] == "bg1"

    async def test_filters_by_status(self, controller: DashboardController) -> None:
        result = await controller.list_named_sessions(status="stopped")
        assert result["sessions"] == []

    async def test_filters_by_chat_id(self, controller: DashboardController) -> None:
        result = await controller.list_named_sessions(chat_id=999)
        assert result["sessions"] == []


class TestListAgents:
    async def test_returns_agents_list(self, controller: DashboardController) -> None:
        result = await controller.list_agents()
        assert isinstance(result["agents"], list)
        assert len(result["agents"]) == 1
        assert result["agents"][0]["name"] == "main"
        assert result["agents"][0]["status"] == "healthy"


class TestListCronJobs:
    async def test_returns_jobs(self, controller: DashboardController) -> None:
        result = await controller.list_cron_jobs()
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["id"] == "cj1"


class TestListTasks:
    async def test_returns_all(self, controller: DashboardController) -> None:
        result = await controller.list_tasks()
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task_id"] == "t1"

    async def test_filters_by_status(self, controller: DashboardController) -> None:
        result = await controller.list_tasks(status="completed")
        assert result["tasks"] == []

    async def test_filters_by_agent(self, controller: DashboardController) -> None:
        result = await controller.list_tasks(agent="sub1")
        assert result["tasks"] == []

    async def test_no_registry_returns_empty(self, controller: DashboardController) -> None:
        controller._task_registry_getter = lambda: None
        result = await controller.list_tasks()
        assert result["tasks"] == []


class TestListProcesses:
    async def test_returns_processes(self, controller: DashboardController) -> None:
        result = await controller.list_processes()
        assert len(result["processes"]) == 1
        assert result["processes"][0]["pid"] == 123


class TestGetHistory:
    async def test_returns_messages(self, controller: DashboardController) -> None:
        result = await controller.get_history(100)
        assert result["messages"] == [{"ts": 1.0, "text": "hi"}]
        assert result["has_more"] is False
        assert "next_cursor" not in result

    async def test_passes_pagination_params(self, controller: DashboardController) -> None:
        await controller.get_history(100, topic_id=5, limit=10, before=99.0, origin="user")
        controller._history_store.query.assert_awaited_once_with(  # type: ignore[attr-defined]
            100, topic_id=5, limit=10, before=99.0, origin="user"
        )

    async def test_clamps_limit_low(self, controller: DashboardController) -> None:
        await controller.get_history(100, limit=-5)
        controller._history_store.query.assert_awaited_once_with(  # type: ignore[attr-defined]
            100, topic_id=None, limit=1, before=None, origin=None
        )

    async def test_clamps_limit_high(self, controller: DashboardController) -> None:
        await controller.get_history(100, limit=999)
        controller._history_store.query.assert_awaited_once_with(  # type: ignore[attr-defined]
            100, topic_id=None, limit=200, before=None, origin=None
        )

    async def test_next_cursor_when_has_more(self, controller: DashboardController) -> None:
        controller._history_store.query = AsyncMock(  # type: ignore[method-assign]
            return_value=([{"ts": 5.0}, {"ts": 3.0}], True)
        )
        result = await controller.get_history(100)
        assert result["has_more"] is True
        assert result["next_cursor"] == 3.0


class TestGetCronHistory:
    @patch("klir.api.controller.read_run_log_page")
    async def test_returns_runs(
        self, mock_read: AsyncMock, controller: DashboardController
    ) -> None:
        entry = CronRunLogEntry(
            ts=1.0,
            job_id="cj1",
            status="ok",
            error=None,
            summary="done",
            duration_ms=100,
            delivery_status="sent",
            provider="claude",
            model="opus",
            input_tokens=50,
            output_tokens=80,
        )
        mock_read.return_value = RunLogPage(
            entries=[entry], total=1, offset=0, limit=20, has_more=False
        )
        result = await controller.get_cron_history("cj1")
        assert len(result["runs"]) == 1
        assert result["runs"][0]["status"] == "ok"
        mock_read.assert_awaited_once_with(controller._db, job_id="cj1", limit=20)

    async def test_unknown_job_returns_empty(self, controller: DashboardController) -> None:
        controller._cron_mgr.get_job = MagicMock(return_value=None)  # type: ignore[method-assign]
        result = await controller.get_cron_history("nonexistent")
        assert result["runs"] == []

    @patch("klir.api.controller.read_run_log_page")
    async def test_clamps_limit(
        self, mock_read: AsyncMock, controller: DashboardController
    ) -> None:
        mock_read.return_value = RunLogPage(
            entries=[], total=0, offset=0, limit=100, has_more=False
        )
        await controller.get_cron_history("cj1", limit=999)
        mock_read.assert_awaited_once_with(controller._db, job_id="cj1", limit=100)


class TestGetHealth:
    async def test_returns_health(self, controller: DashboardController) -> None:
        result = await controller.get_health()
        assert result["status"] == "ok"
        assert result["connections"]["dashboard_clients"] == 3
        assert result["observers"] == {"cron": "running"}


class TestToggleCronJob:
    async def test_toggles(self, controller: DashboardController) -> None:
        result = await controller.toggle_cron_job("cj1", enabled=False)
        assert result["ok"] is True
        assert result["job_id"] == "cj1"
        assert result["enabled"] is False
        controller._cron_mgr.set_enabled.assert_called_once_with(  # type: ignore[attr-defined]
            "cj1", enabled=False
        )

    async def test_unknown_job(self, controller: DashboardController) -> None:
        controller._cron_mgr.set_enabled = MagicMock(return_value=False)  # type: ignore[method-assign]
        result = await controller.toggle_cron_job("bad", enabled=True)
        assert result["ok"] is False


class TestCancelTask:
    async def test_cancels(self, controller: DashboardController) -> None:
        result = await controller.cancel_task("t1")
        assert result["ok"] is True
        assert result["task_id"] == "t1"
        controller._task_cancel.assert_awaited_once_with("t1")  # type: ignore[attr-defined]

    async def test_cancel_returns_false(self, controller: DashboardController) -> None:
        controller._task_cancel = AsyncMock(return_value=False)
        result = await controller.cancel_task("t1")
        assert result["ok"] is False
        assert result["task_id"] == "t1"


class TestAbortChat:
    async def test_aborts(self, controller: DashboardController) -> None:
        result = await controller.abort_chat(100)
        assert result["ok"] is True
        assert result["killed"] == 2


class TestSendMessage:
    async def test_success(self, controller: DashboardController) -> None:
        result = await controller.send_message(100, "hello")
        assert result["ok"] is True
        assert result["result"]["text"] == "response text"

    async def test_with_topic_id(self, controller: DashboardController) -> None:
        await controller.send_message(100, "hello", topic_id=5)
        from klir.session.key import SessionKey

        call_args = controller._message_handler.call_args  # type: ignore[attr-defined]
        assert call_args[0][0] == SessionKey(chat_id=100, topic_id=5)

    async def test_exception_returns_error(self, controller: DashboardController) -> None:
        controller._message_handler = AsyncMock(side_effect=RuntimeError("boom"))
        result = await controller.send_message(100, "hello")
        assert result["ok"] is False
        assert result["error"] == "internal_error"


class TestSendMessageStreaming:
    async def test_yields_sse_events(self, controller: DashboardController) -> None:
        async def fake_handler(
            _key: Any,
            _text: str,
            **kwargs: Any,
        ) -> FakeResult:
            # Simulate streaming callbacks (must await — real orchestrator does)
            await kwargs["on_text_delta"]("hel")
            await kwargs["on_text_delta"]("lo")
            await kwargs["on_tool_activity"](FakeToolActivity(name="searching"))
            await kwargs["on_system_status"]("thinking")
            return FakeResult(text="hello")

        controller._message_handler = fake_handler

        events = [e async for e in controller.send_message_stream(100, "hi")]

        assert len(events) == 5
        assert events[0].startswith("event: text_delta\n")
        assert '"delta": "hel"' in events[0]
        assert events[1].startswith("event: text_delta\n")
        assert events[2].startswith("event: tool_activity\n")
        assert '"activity": "searching"' in events[2]
        assert events[3].startswith("event: system_status\n")
        assert events[4].startswith("event: result\n")
        assert '"text": "hello"' in events[4]

    async def test_correct_sse_format(self, controller: DashboardController) -> None:
        async def fake_handler(_key: Any, _text: str, **kwargs: Any) -> FakeResult:
            await kwargs["on_text_delta"]("x")
            return FakeResult(text="x")

        controller._message_handler = fake_handler

        events = [e async for e in controller.send_message_stream(100, "hi")]

        # Each SSE event must end with double newline
        for event in events:
            assert event.endswith("\n\n")
            lines = event.strip().split("\n")
            assert lines[0].startswith("event: ")
            assert lines[1].startswith("data: ")

    async def test_error_yields_error_result(self, controller: DashboardController) -> None:
        async def failing_handler(_key: Any, _text: str, **_kwargs: Any) -> FakeResult:
            msg = "boom"
            raise RuntimeError(msg)

        controller._message_handler = failing_handler

        events = [e async for e in controller.send_message_stream(100, "hi")]

        assert len(events) == 1
        assert events[0].startswith("event: result\n")
        assert '"error": "internal_error"' in events[0]
