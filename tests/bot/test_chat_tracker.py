"""Tests for ChatTracker persistence and record management."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from klir.bot.chat_tracker import ChatRecord, ChatTracker
from klir.infra.db import KlirDB


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[KlirDB]:
    instance = KlirDB(tmp_path / "klir.db")
    await instance.open()
    yield instance
    await instance.close()


class TestChatTracker:
    """ChatTracker: record, persist, load, get_all."""

    async def test_record_join_creates_entry(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1001, "supergroup", "Dev Group", allowed=True)

        records = tracker.get_all()
        assert len(records) == 1
        assert records[0].chat_id == -1001
        assert records[0].chat_type == "supergroup"
        assert records[0].title == "Dev Group"
        assert records[0].status == "active"
        assert records[0].allowed is True

    async def test_record_join_updates_existing(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1001, "group", "Old Name", allowed=True)
        await tracker.record_join(-1001, "supergroup", "New Name", allowed=True)

        records = tracker.get_all()
        assert len(records) == 1
        assert records[0].chat_type == "supergroup"
        assert records[0].title == "New Name"

    async def test_record_leave(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1001, "group", "Group", allowed=True)
        await tracker.record_leave(-1001, "kicked")

        records = tracker.get_all()
        assert records[0].status == "kicked"

    async def test_record_leave_unknown_chat(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_leave(-9999, "left")

        records = tracker.get_all()
        assert len(records) == 1
        assert records[0].status == "left"

    async def test_record_rejected(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_rejected(-1001, "group", "Spam Group")
        await tracker.record_rejected(-1001, "group", "Spam Group")

        records = tracker.get_all()
        assert len(records) == 1
        assert records[0].rejected_count == 2
        assert records[0].allowed is False

    async def test_persistence_roundtrip(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1001, "supergroup", "Persistent Group", allowed=True)
        await tracker.record_rejected(-2002, "group", "Bad Group")

        # Load a fresh tracker from the same DB
        tracker2 = await ChatTracker.create(db)
        records = tracker2.get_all()
        assert len(records) == 2
        ids = {r.chat_id for r in records}
        assert ids == {-1001, -2002}

    async def test_get_all_sorted_by_last_seen(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1, "group", "First", allowed=True)
        await tracker.record_join(-2, "group", "Second", allowed=True)

        # Manually set different timestamps to guarantee order
        tracker._records[-1].last_seen = "2025-01-01T00:00:00+00:00"
        tracker._records[-2].last_seen = "2025-01-01T00:00:01+00:00"

        records = tracker.get_all()
        assert records[0].chat_id == -2  # newer
        assert records[1].chat_id == -1  # older

    async def test_empty_db_loads_cleanly(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        assert tracker.get_all() == []


class TestChatTrackerMigration:
    """One-time migration from chat_activity.json."""

    async def test_migrates_legacy_json(self, db: KlirDB, tmp_path: Path) -> None:
        json_path = tmp_path / "chat_activity.json"
        json_path.write_text(
            json.dumps(
                {
                    "records": {
                        "-1001": {
                            "chat_id": -1001,
                            "chat_type": "supergroup",
                            "title": "Dev Group",
                            "first_seen": "2025-01-01T00:00:00+00:00",
                            "last_seen": "2025-03-01T10:00:00+00:00",
                            "status": "active",
                            "allowed": True,
                            "rejected_count": 0,
                        },
                        "-2002": {
                            "chat_id": -2002,
                            "chat_type": "group",
                            "title": "Spam",
                            "first_seen": "2025-02-01T00:00:00+00:00",
                            "last_seen": "2025-02-15T00:00:00+00:00",
                            "status": "rejected",
                            "allowed": False,
                            "rejected_count": 5,
                        },
                    }
                }
            )
        )

        tracker = await ChatTracker.create(db, legacy_json_path=json_path)
        records = tracker.get_all()
        assert len(records) == 2

        # Verify fields preserved
        dev = next(r for r in records if r.chat_id == -1001)
        assert dev.chat_type == "supergroup"
        assert dev.title == "Dev Group"
        assert dev.allowed is True

        spam = next(r for r in records if r.chat_id == -2002)
        assert spam.rejected_count == 5
        assert spam.allowed is False

        # JSON file renamed
        assert not json_path.exists()
        assert json_path.with_suffix(".json.migrated").exists()

    async def test_skips_migration_when_db_has_data(self, db: KlirDB, tmp_path: Path) -> None:
        # Pre-populate the DB
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1, "group", "Existing", allowed=True)

        # Create legacy JSON
        json_path = tmp_path / "chat_activity.json"
        json_path.write_text(
            json.dumps(
                {
                    "records": {
                        "-9999": {
                            "chat_id": -9999,
                            "chat_type": "group",
                            "title": "Should Not Appear",
                            "first_seen": "2025-01-01T00:00:00+00:00",
                            "last_seen": "2025-01-01T00:00:00+00:00",
                            "status": "active",
                            "allowed": True,
                            "rejected_count": 0,
                        }
                    }
                }
            )
        )

        # Create a fresh tracker — should NOT migrate since DB has data
        tracker2 = await ChatTracker.create(db, legacy_json_path=json_path)
        ids = {r.chat_id for r in tracker2.get_all()}
        assert -9999 not in ids
        assert -1 in ids

        # JSON file untouched
        assert json_path.exists()


class TestChatTrackerRetention:
    """Retention-based cleanup via prune_inactive."""

    async def test_prune_inactive(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1, "group", "Recent", allowed=True)
        await tracker.record_join(-2, "group", "Old", allowed=True)

        # Make one record very old
        tracker._records[-2].last_seen = "2020-01-01T00:00:00+00:00"
        await tracker._upsert(tracker._records[-2])

        pruned = await tracker.prune_inactive(90)
        assert pruned == 1
        assert len(tracker.get_all()) == 1
        assert tracker.get_all()[0].chat_id == -1

        # Verify DB is also cleaned
        tracker2 = await ChatTracker.create(db)
        assert len(tracker2.get_all()) == 1

    async def test_prune_nothing_when_all_recent(self, db: KlirDB) -> None:
        tracker = await ChatTracker.create(db)
        await tracker.record_join(-1, "group", "Recent", allowed=True)

        pruned = await tracker.prune_inactive(90)
        assert pruned == 0
        assert len(tracker.get_all()) == 1


class TestChatRecord:
    """ChatRecord dataclass defaults."""

    def test_defaults(self) -> None:
        rec = ChatRecord(chat_id=42)
        assert rec.chat_type == "private"
        assert rec.title == ""
        assert rec.status == "active"
        assert rec.allowed is True
        assert rec.rejected_count == 0
