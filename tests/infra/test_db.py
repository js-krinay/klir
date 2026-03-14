from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from klir.infra.db import KlirDB

EXPECTED_TABLES = {"messages", "cron_runs", "tasks", "sessions", "chat_activity"}


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[KlirDB]:
    instance = KlirDB(tmp_path / "sub" / "klir.db")
    await instance.open()
    yield instance
    await instance.close()


# ── Migration runner tests ─────────────────────────────────────────


async def test_open_creates_db_file(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "klir.db"
    instance = KlirDB(db_path)
    await instance.open()
    assert db_path.exists()
    assert db_path.parent.is_dir()
    await instance.close()


async def test_wal_mode_enabled(db: KlirDB) -> None:
    row = await db.fetch_one("PRAGMA journal_mode")
    assert row is not None
    assert row["journal_mode"] == "wal"


async def test_initial_migration_creates_tables(db: KlirDB) -> None:
    rows = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_%' ESCAPE '\\'"
    )
    table_names = {r["name"] for r in rows}
    assert EXPECTED_TABLES.issubset(table_names)


async def test_schema_version_set(db: KlirDB) -> None:
    row = await db.fetch_one("SELECT version FROM _schema_version")
    assert row is not None
    assert row["version"] == 1


async def test_migration_is_idempotent(db: KlirDB) -> None:
    await db.open()
    row = await db.fetch_one("SELECT version FROM _schema_version")
    assert row is not None
    assert row["version"] == 1

    rows = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_%' ESCAPE '\\'"
    )
    table_names = {r["name"] for r in rows}
    assert EXPECTED_TABLES.issubset(table_names)


async def test_incremental_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    real_001 = (
        Path(__file__).resolve().parents[2]  # noqa: ASYNC240
        / "klir"
        / "infra"
        / "migrations"
        / "001_initial.sql"
    )
    (migrations_dir / "001_initial.sql").write_text(real_001.read_text())

    monkeypatch.setattr(KlirDB, "_migrations_dir", lambda _self: migrations_dir)

    db_path = tmp_path / "klir.db"
    instance = KlirDB(db_path)
    await instance.open()

    row = await instance.fetch_one("SELECT version FROM _schema_version")
    assert row is not None
    assert row["version"] == 1

    # Add a 002 migration
    (migrations_dir / "002_add_column.sql").write_text(
        "ALTER TABLE chat_activity ADD COLUMN notes TEXT DEFAULT '';\n"
    )

    await instance.close()

    instance2 = KlirDB(db_path)
    await instance2.open()

    row = await instance2.fetch_one("SELECT version FROM _schema_version")
    assert row is not None
    assert row["version"] == 2

    all_cols = await instance2.fetch_all("PRAGMA table_info(chat_activity)")
    col_names = {r["name"] for r in all_cols}
    assert "notes" in col_names

    await instance2.close()


# ── CRUD tests ─────────────────────────────────────────────────────


async def test_execute_insert_and_fetch_one(db: KlirDB) -> None:
    await db.execute(
        "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
        (1, 100.0, 200.0),
    )
    row = await db.fetch_one("SELECT * FROM chat_activity WHERE chat_id = ?", (1,))
    assert row is not None
    assert row["chat_id"] == 1
    assert row["first_seen"] == 100.0
    assert row["last_seen"] == 200.0


async def test_fetch_one_returns_none(db: KlirDB) -> None:
    row = await db.fetch_one("SELECT * FROM chat_activity WHERE chat_id = ?", (999,))
    assert row is None


async def test_fetch_all_returns_list(db: KlirDB) -> None:
    for i in range(3):
        await db.execute(
            "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
            (i, float(i), float(i)),
        )
    rows = await db.fetch_all("SELECT * FROM chat_activity ORDER BY chat_id")
    assert len(rows) == 3
    assert [r["chat_id"] for r in rows] == [0, 1, 2]


async def test_fetch_all_empty(db: KlirDB) -> None:
    rows = await db.fetch_all("SELECT * FROM chat_activity")
    assert rows == []


async def test_executemany(db: KlirDB) -> None:
    params = [(i, float(i), float(i)) for i in range(5)]
    await db.executemany(
        "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
        params,
    )
    rows = await db.fetch_all("SELECT * FROM chat_activity ORDER BY chat_id")
    assert len(rows) == 5


async def test_row_as_dict(db: KlirDB) -> None:
    await db.execute(
        "INSERT INTO chat_activity (chat_id, title, type, first_seen, last_seen) "
        "VALUES (?, ?, ?, ?, ?)",
        (42, "Test Chat", "group", 1.0, 2.0),
    )
    row = await db.fetch_one("SELECT * FROM chat_activity WHERE chat_id = ?", (42,))
    assert row is not None
    assert isinstance(row, dict)
    assert row["chat_id"] == 42
    assert row["title"] == "Test Chat"
    assert row["type"] == "group"


# ── Lifecycle tests ────────────────────────────────────────────────


async def test_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "klir.db"
    instance = KlirDB(db_path)
    await instance.open()

    await instance.execute(
        "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
        (7, 1.0, 2.0),
    )
    await instance.close()

    instance2 = KlirDB(db_path)
    await instance2.open()
    row = await instance2.fetch_one("SELECT * FROM chat_activity WHERE chat_id = ?", (7,))
    assert row is not None
    assert row["chat_id"] == 7
    await instance2.close()


async def test_failed_write_rolls_back(db: KlirDB) -> None:
    await db.execute(
        "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
        (1, 1.0, 2.0),
    )
    # Duplicate primary key triggers IntegrityError; the write must roll back.
    with pytest.raises(sqlite3.IntegrityError):
        await db.execute(
            "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
            (1, 3.0, 4.0),
        )
    # Original row is untouched.
    row = await db.fetch_one("SELECT * FROM chat_activity WHERE chat_id = ?", (1,))
    assert row is not None
    assert row["first_seen"] == 1.0


async def test_concurrent_writes(db: KlirDB) -> None:
    async def insert(chat_id: int) -> None:
        await db.execute(
            "INSERT INTO chat_activity (chat_id, first_seen, last_seen) VALUES (?, ?, ?)",
            (chat_id, float(chat_id), float(chat_id)),
        )

    await asyncio.gather(*(insert(i) for i in range(20)))

    rows = await db.fetch_all("SELECT * FROM chat_activity")
    assert len(rows) == 20
    ids = sorted(r["chat_id"] for r in rows)  # type: ignore[type-var]
    assert ids == list(range(20))
