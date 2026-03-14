"""Tests for klir.history.store.MessageHistory."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from klir.bus.envelope import Envelope, Origin
from klir.history.store import MessageHistory, ResponseRecord
from klir.infra.db import KlirDB


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[KlirDB]:
    instance = KlirDB(tmp_path / "klir.db")
    await instance.open()
    yield instance
    await instance.close()


@pytest.fixture
def history(db: KlirDB) -> MessageHistory:
    return MessageHistory(db)


# ── record_inbound ───────────────────────────────────────────────────


async def test_record_inbound_returns_id(history: MessageHistory) -> None:
    msg_id = await history.record_inbound(
        chat_id=123, text="hello", provider="claude", model="opus"
    )
    assert isinstance(msg_id, str)
    assert len(msg_id) == 16  # secrets.token_hex(8)


async def test_record_inbound_persists(history: MessageHistory, db: KlirDB) -> None:
    await history.record_inbound(
        chat_id=42, topic_id=7, text="test msg", provider="gemini", model="pro"
    )
    row = await db.fetch_one("SELECT * FROM messages WHERE chat_id = ?", (42,))
    assert row is not None
    assert row["direction"] == "inbound"
    assert row["origin"] == "user"
    assert row["text"] == "test msg"
    assert row["topic_id"] == 7
    assert row["provider"] == "gemini"
    assert row["model"] == "pro"


# ── record_outbound ─────────────────────────────────────────────────


async def test_record_outbound_from_envelope(history: MessageHistory, db: KlirDB) -> None:
    env = Envelope(
        origin=Origin.CRON,
        chat_id=100,
        topic_id=5,
        result_text="cron output",
        provider="claude",
        model="sonnet",
        session_id="sid-abc",
        session_name="daily-check",
        elapsed_seconds=1.5,
        is_error=False,
        metadata={"title": "my cron"},
    )
    msg_id = await history.record_outbound(env, cost_usd=0.01, tokens=500)
    assert isinstance(msg_id, str)

    row = await db.fetch_one("SELECT * FROM messages WHERE id = ?", (msg_id,))
    assert row is not None
    assert row["direction"] == "outbound"
    assert row["origin"] == "cron"
    assert row["text"] == "cron output"
    assert row["provider"] == "claude"
    assert row["session_id"] == "sid-abc"
    assert row["cost_usd"] == 0.01
    assert row["tokens"] == 500
    assert row["elapsed_seconds"] == 1.5
    assert row["is_error"] == 0


async def test_record_outbound_error_flag(history: MessageHistory, db: KlirDB) -> None:
    env = Envelope(
        origin=Origin.BACKGROUND,
        chat_id=200,
        result_text="error occurred",
        is_error=True,
    )
    msg_id = await history.record_outbound(env)
    row = await db.fetch_one("SELECT * FROM messages WHERE id = ?", (msg_id,))
    assert row is not None
    assert row["is_error"] == 1


# ── record_response ─────────────────────────────────────────────────


async def test_record_response(history: MessageHistory, db: KlirDB) -> None:
    record = ResponseRecord(
        chat_id=300,
        topic_id=10,
        text="response text",
        provider="claude",
        model="opus",
        session_id="sid-xyz",
        cost_usd=0.05,
        tokens=1000,
        elapsed_seconds=2.3,
    )
    msg_id = await history.record_response(record)
    assert isinstance(msg_id, str)

    row = await db.fetch_one("SELECT * FROM messages WHERE id = ?", (msg_id,))
    assert row is not None
    assert row["direction"] == "outbound"
    assert row["text"] == "response text"
    assert row["cost_usd"] == 0.05
    assert row["tokens"] == 1000


# ── query ────────────────────────────────────────────────────────────


async def test_query_returns_messages_for_chat(history: MessageHistory) -> None:
    await history.record_inbound(chat_id=10, text="msg1")
    await history.record_inbound(chat_id=10, text="msg2")
    await history.record_inbound(chat_id=20, text="other")

    msgs, has_more = await history.query(10)
    assert len(msgs) == 2
    assert not has_more


async def test_query_respects_limit(history: MessageHistory) -> None:
    for i in range(5):
        await history.record_inbound(chat_id=10, text=f"msg{i}")

    msgs, has_more = await history.query(10, limit=3)
    assert len(msgs) == 3
    assert has_more


async def test_query_cursor_pagination(history: MessageHistory) -> None:
    for i in range(5):
        await history.record_inbound(chat_id=10, text=f"msg{i}")

    page1, has_more1 = await history.query(10, limit=3)
    assert len(page1) == 3
    assert has_more1

    oldest_ts = page1[-1]["ts"]
    assert isinstance(oldest_ts, (int, float))
    page2, has_more2 = await history.query(10, limit=3, before=float(oldest_ts))
    assert len(page2) == 2
    assert not has_more2


async def test_query_filter_by_topic(history: MessageHistory) -> None:
    await history.record_inbound(chat_id=10, topic_id=1, text="topic1")
    await history.record_inbound(chat_id=10, topic_id=2, text="topic2")
    await history.record_inbound(chat_id=10, text="no topic")

    msgs, _ = await history.query(10, topic_id=1)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "topic1"


async def test_query_filter_by_origin(history: MessageHistory) -> None:
    await history.record_inbound(chat_id=10, text="user msg")
    env = Envelope(origin=Origin.CRON, chat_id=10, result_text="cron output")
    await history.record_outbound(env)

    msgs, _ = await history.query(10, origin="cron")
    assert len(msgs) == 1
    assert msgs[0]["origin"] == "cron"


async def test_query_ordered_by_ts_desc(history: MessageHistory) -> None:
    await history.record_inbound(chat_id=10, text="first")
    await history.record_inbound(chat_id=10, text="second")

    msgs, _ = await history.query(10)
    assert msgs[0]["text"] == "second"
    assert msgs[1]["text"] == "first"


# ── cleanup ──────────────────────────────────────────────────────────


async def test_cleanup_deletes_old_messages(history: MessageHistory, db: KlirDB) -> None:
    old_ts = time.time() - 40 * 86400  # 40 days ago
    await db.execute(
        "INSERT INTO messages (id, ts, origin, chat_id, direction, text) VALUES (?, ?, ?, ?, ?, ?)",
        ("old1", old_ts, "user", 10, "inbound", "old message"),
    )
    await history.record_inbound(chat_id=10, text="recent message")

    deleted = await history.cleanup(retention_days=30)
    assert deleted == 1

    msgs, _ = await history.query(10)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "recent message"


async def test_cleanup_returns_zero_when_nothing_to_delete(
    history: MessageHistory,
) -> None:
    await history.record_inbound(chat_id=10, text="recent")
    deleted = await history.cleanup(retention_days=30)
    assert deleted == 0
