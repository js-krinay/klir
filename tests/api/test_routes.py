"""Tests for the dashboard REST API route layer (klir/api/routes.py)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiohttp import web

from klir.api.routes import register_dashboard_routes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_controller() -> AsyncMock:
    """Return a mock controller with all methods used by routes."""
    ctrl = AsyncMock()
    ctrl.list_sessions.return_value = []
    ctrl.get_history.return_value = []
    ctrl.list_named_sessions.return_value = []
    ctrl.list_agents.return_value = []
    ctrl.list_cron_jobs.return_value = []
    ctrl.get_cron_history.return_value = []
    ctrl.toggle_cron_job.return_value = {"ok": True}
    ctrl.list_tasks.return_value = []
    ctrl.cancel_task.return_value = {"ok": True}
    ctrl.list_processes.return_value = []
    ctrl.send_message.return_value = {"text": "ok"}
    ctrl.get_health.return_value = {"status": "ok"}
    ctrl.abort_chat.return_value = {"killed": 0}

    async def _fake_stream(**_kwargs: Any) -> AsyncGenerator[str, None]:
        yield "data: chunk1\n\n"
        yield "data: chunk2\n\n"

    ctrl.send_message_stream = _fake_stream
    return ctrl


def _make_app(
    *,
    auth_ok: bool = True,
    ctrl: AsyncMock | None = None,
) -> web.Application:
    """Build a test app with dashboard routes registered."""
    app = web.Application()
    controller = ctrl or _make_controller()
    verify_bearer = lambda _req: auth_ok  # noqa: E731
    register_dashboard_routes(app, controller, verify_bearer)
    return app


@pytest.fixture
async def authed_client(aiohttp_client: Any) -> Any:
    """Client where auth always succeeds."""
    return await aiohttp_client(_make_app(auth_ok=True))


@pytest.fixture
async def unauthed_client(aiohttp_client: Any) -> Any:
    """Client where auth always fails."""
    return await aiohttp_client(_make_app(auth_ok=False))


# ---------------------------------------------------------------------------
# Auth rejection — every endpoint returns 401 when verify_bearer is False
# ---------------------------------------------------------------------------

_ALL_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/sessions"),
    ("GET", "/api/sessions/1/history"),
    ("GET", "/api/named-sessions"),
    ("GET", "/api/agents"),
    ("GET", "/api/cron"),
    ("GET", "/api/cron/job1/history"),
    ("PATCH", "/api/cron/job1"),
    ("GET", "/api/tasks"),
    ("POST", "/api/tasks/t1/cancel"),
    ("GET", "/api/processes"),
    ("POST", "/api/sessions/1/message"),
    ("GET", "/api/health"),
    ("POST", "/api/abort"),
]


class TestAuthRejection:
    @pytest.mark.parametrize(("method", "path"), _ALL_ENDPOINTS)
    async def test_401_when_unauthed(self, unauthed_client: Any, method: str, path: str) -> None:
        resp = await unauthed_client.request(method, path)
        assert resp.status == 401
        body = await resp.json()
        assert body["error"] == "unauthorized"


# ---------------------------------------------------------------------------
# Input validation — _validate_message_body
# ---------------------------------------------------------------------------


class TestMessageBodyValidation:
    async def test_missing_text(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/sessions/1/message", json={"not_text": "hi"})
        assert resp.status == 400
        assert "text" in (await resp.json())["error"]

    async def test_empty_text(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/sessions/1/message", json={"text": "  "})
        assert resp.status == 400
        assert "non-empty" in (await resp.json())["error"]

    async def test_non_string_text(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/sessions/1/message", json={"text": 42})
        assert resp.status == 400
        assert "non-empty" in (await resp.json())["error"]

    async def test_non_integer_topic_id(self, authed_client: Any) -> None:
        resp = await authed_client.post(
            "/api/sessions/1/message",
            json={"text": "hello", "topic_id": "abc"},
        )
        assert resp.status == 400
        assert "topic_id" in (await resp.json())["error"]

    async def test_valid_body_returns_200(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/sessions/1/message", json={"text": "hello"})
        assert resp.status == 200

    async def test_valid_body_with_topic_and_stream(self, aiohttp_client: Any) -> None:
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))
        resp = await client.post(
            "/api/sessions/1/message",
            json={"text": "hi", "topic_id": 5, "stream": True},
        )
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "text/event-stream"


# ---------------------------------------------------------------------------
# Query param parsing errors
# ---------------------------------------------------------------------------


class TestQueryParamErrors:
    async def test_sessions_bad_chat_id(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/sessions", params={"chat_id": "abc"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]

    async def test_history_bad_limit(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/sessions/1/history", params={"limit": "xyz"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]

    async def test_history_bad_before(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/sessions/1/history", params={"before": "not-a-float"})
        assert resp.status == 400
        assert "number" in (await resp.json())["error"]

    async def test_history_bad_topic_id(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/sessions/1/history", params={"topic_id": "abc"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]

    async def test_named_sessions_bad_chat_id(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/named-sessions", params={"chat_id": "abc"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]

    async def test_cron_history_bad_limit(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/cron/job1/history", params={"limit": "nope"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]


# ---------------------------------------------------------------------------
# JSON body errors
# ---------------------------------------------------------------------------


class TestJsonBodyErrors:
    async def test_toggle_cron_invalid_json(self, authed_client: Any) -> None:
        resp = await authed_client.patch(
            "/api/cron/job1",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        assert "invalid JSON" in (await resp.json())["error"]

    async def test_send_message_invalid_json(self, authed_client: Any) -> None:
        resp = await authed_client.post(
            "/api/sessions/1/message",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        assert "invalid JSON" in (await resp.json())["error"]

    async def test_abort_invalid_json(self, authed_client: Any) -> None:
        resp = await authed_client.post(
            "/api/abort",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        assert "invalid JSON" in (await resp.json())["error"]


# ---------------------------------------------------------------------------
# Toggle cron validation
# ---------------------------------------------------------------------------


class TestToggleCronValidation:
    async def test_missing_enabled(self, authed_client: Any) -> None:
        resp = await authed_client.patch("/api/cron/job1", json={})
        assert resp.status == 400
        assert "enabled" in (await resp.json())["error"]

    async def test_non_boolean_enabled(self, authed_client: Any) -> None:
        resp = await authed_client.patch("/api/cron/job1", json={"enabled": "yes"})
        assert resp.status == 400
        assert "boolean" in (await resp.json())["error"]

    async def test_valid_toggle(self, authed_client: Any) -> None:
        resp = await authed_client.patch("/api/cron/job1", json={"enabled": True})
        assert resp.status == 200


# ---------------------------------------------------------------------------
# Abort validation
# ---------------------------------------------------------------------------


class TestAbortValidation:
    async def test_missing_chat_id(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/abort", json={})
        assert resp.status == 400
        assert "chat_id" in (await resp.json())["error"]

    async def test_non_integer_chat_id(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/abort", json={"chat_id": "abc"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]

    async def test_valid_abort(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/abort", json={"chat_id": 123})
        assert resp.status == 200


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------


class TestSSEStreaming:
    async def test_stream_response_headers(self, aiohttp_client: Any) -> None:
        """When stream=true, response has SSE content-type headers."""
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))

        resp = await client.post(
            "/api/sessions/1/message",
            json={"text": "hello", "stream": True},
        )
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "text/event-stream"
        assert resp.headers["Cache-Control"] == "no-cache"
        assert resp.headers["Connection"] == "keep-alive"

    async def test_non_stream_returns_json(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/sessions/1/message", json={"text": "hello"})
        assert resp.status == 200
        assert "application/json" in resp.headers["Content-Type"]


# ---------------------------------------------------------------------------
# Path param validation
# ---------------------------------------------------------------------------


class TestPathParamValidation:
    async def test_history_bad_chat_id_path(self, authed_client: Any) -> None:
        resp = await authed_client.get("/api/sessions/abc/history")
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]

    async def test_message_bad_chat_id_path(self, authed_client: Any) -> None:
        resp = await authed_client.post("/api/sessions/abc/message", json={"text": "hi"})
        assert resp.status == 400
        assert "integer" in (await resp.json())["error"]


# ---------------------------------------------------------------------------
# Controller delegation — verify kwargs forwarded correctly
# ---------------------------------------------------------------------------


class TestControllerDelegation:
    async def test_list_sessions_passes_chat_id(self, aiohttp_client: Any) -> None:
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))
        await client.get("/api/sessions", params={"chat_id": "42"})
        ctrl.list_sessions.assert_awaited_once_with(chat_id=42)

    async def test_get_history_passes_all_kwargs(self, aiohttp_client: Any) -> None:
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))
        await client.get(
            "/api/sessions/1/history",
            params={
                "topic_id": "5",
                "limit": "10",
                "before": "1.5",
                "origin": "user",
            },
        )
        ctrl.get_history.assert_awaited_once_with(
            chat_id=1, topic_id=5, limit=10, before=1.5, origin="user"
        )

    async def test_toggle_cron_passes_args(self, aiohttp_client: Any) -> None:
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))
        await client.patch("/api/cron/myjob", json={"enabled": False})
        ctrl.toggle_cron_job.assert_awaited_once_with("myjob", enabled=False)

    async def test_abort_passes_chat_id(self, aiohttp_client: Any) -> None:
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))
        await client.post("/api/abort", json={"chat_id": 99})
        ctrl.abort_chat.assert_awaited_once_with(99)

    async def test_send_message_passes_kwargs(self, aiohttp_client: Any) -> None:
        ctrl = _make_controller()
        client = await aiohttp_client(_make_app(ctrl=ctrl))
        await client.post(
            "/api/sessions/7/message",
            json={"text": "hi", "topic_id": 3},
        )
        ctrl.send_message.assert_awaited_once_with(chat_id=7, text="hi", topic_id=3)
