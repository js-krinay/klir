"""Tests for MAINMEMORY.md migration to hierarchical structure."""

from __future__ import annotations

from pathlib import Path

import pytest

from klir.memory.migrate import migrate_mainmemory
from klir.memory.store import MemoryStore


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    d = tmp_path / "memory_system"
    d.mkdir()
    return d


def test_migrate_populated_mainmemory(memory_dir: Path) -> None:
    """Populated MAINMEMORY.md creates a profile memory."""
    mainmemory = memory_dir / "MAINMEMORY.md"
    mainmemory.write_text(
        "# Main Memory\n\n"
        "## About the User\n\n"
        "Senior engineer at Acme Corp. Prefers Python.\n\n"
        "## Learned Facts\n\n"
        "Project X uses PostgreSQL 15.\n\n"
        "## Decisions and Preferences\n\n"
        "Always use type hints.\n",
        encoding="utf-8",
    )
    store = MemoryStore(memory_dir / "index.db")
    migrated = migrate_mainmemory(mainmemory, memory_dir, store)
    assert migrated is True
    assert (memory_dir / "user" / "profile.md").exists()
    # Original file should be renamed to backup
    assert (memory_dir / "MAINMEMORY.md.bak").exists()
    store.close()


def test_migrate_empty_mainmemory(memory_dir: Path) -> None:
    """Empty MAINMEMORY.md is skipped."""
    mainmemory = memory_dir / "MAINMEMORY.md"
    mainmemory.write_text(
        "# Main Memory\n\n"
        "## About the User\n\n"
        "(Empty -- will be populated as you learn about your human.)\n\n"
        "## Learned Facts\n\n"
        "(Empty -- will be populated as the agent learns.)\n\n"
        "## Decisions and Preferences\n\n"
        "(Empty -- record important decisions and their reasoning here.)\n",
        encoding="utf-8",
    )
    store = MemoryStore(memory_dir / "index.db")
    migrated = migrate_mainmemory(mainmemory, memory_dir, store)
    assert migrated is False
    store.close()


def test_migrate_already_done(memory_dir: Path) -> None:
    """Migration is idempotent: skip if .bak backup already exists."""
    mainmemory = memory_dir / "MAINMEMORY.md"
    mainmemory.write_text("# Main Memory\n\nSome content\n", encoding="utf-8")
    # Simulate a completed previous migration
    (memory_dir / "MAINMEMORY.md.bak").write_text("backup", encoding="utf-8")
    store = MemoryStore(memory_dir / "index.db")
    migrated = migrate_mainmemory(mainmemory, memory_dir, store)
    assert migrated is False  # Already migrated
    store.close()
