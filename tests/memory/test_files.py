"""Tests for memory file manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from klir.memory.files import MemoryFile, MemoryFileManager
from klir.memory.store import MemoryStore


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    d = tmp_path / "memory_system"
    d.mkdir()
    return d


@pytest.fixture
def store(memory_dir: Path) -> MemoryStore:
    return MemoryStore(memory_dir / "index.db")


@pytest.fixture
def mgr(memory_dir: Path, store: MemoryStore) -> MemoryFileManager:
    return MemoryFileManager(memory_dir, store)


def test_write_and_read(mgr: MemoryFileManager) -> None:
    """Write a memory file and read it back."""
    mf = MemoryFile(
        category="preferences",
        slug="testing-style",
        abstract="User prefers pytest",
        content="Always use pytest with strict markers.",
    )
    mgr.write(mf)
    loaded = mgr.read("preferences", "testing-style")
    assert loaded is not None
    assert loaded.abstract == "User prefers pytest"
    assert loaded.content == "Always use pytest with strict markers."


def test_write_indexes_into_store(mgr: MemoryFileManager, store: MemoryStore) -> None:
    """Writing a memory file also indexes it in the FTS5 store."""
    mf = MemoryFile(
        category="cases",
        slug="auth-fix",
        abstract="Fixed auth token expiry",
        content="Token refresh was missing.",
    )
    mgr.write(mf)
    results = store.search("auth token")
    assert len(results) >= 1
    assert "auth-fix" in results[0].uri


def test_delete_removes_file_and_index(
    mgr: MemoryFileManager,
    store: MemoryStore,
) -> None:
    """Deleting a memory removes both the file and the index entry."""
    mf = MemoryFile(
        category="patterns",
        slug="tdd",
        abstract="TDD workflow",
        content="Red green refactor.",
    )
    mgr.write(mf)
    mgr.delete("patterns", "tdd")
    assert mgr.read("patterns", "tdd") is None
    assert store.search("TDD") == []


def test_rebuild_index(mgr: MemoryFileManager, store: MemoryStore, memory_dir: Path) -> None:
    """Rebuild re-indexes all files on disk into a fresh store."""
    # Write files directly (bypassing index)
    cat_dir = memory_dir / "user" / "preferences"
    cat_dir.mkdir(parents=True)
    (cat_dir / "vim.md").write_text(
        "---\nabstract: User uses vim\ncategory: preferences\n---\nVim keybindings everywhere.",
        encoding="utf-8",
    )
    mgr.rebuild_index()
    results = store.search("vim keybindings")
    assert len(results) >= 1


def test_list_all(mgr: MemoryFileManager) -> None:
    """list_all returns all memory files."""
    mgr.write(MemoryFile(category="profile", slug="main", abstract="A", content="A"))
    mgr.write(MemoryFile(category="cases", slug="x", abstract="B", content="B"))
    all_mems = mgr.list_all()
    assert len(all_mems) == 2


def test_profile_path(mgr: MemoryFileManager, memory_dir: Path) -> None:
    """Profile category writes to user/profile.md (special case)."""
    mgr.write(
        MemoryFile(
            category="profile",
            slug="main",
            abstract="Staff eng",
            content="Staff backend engineer.",
        )
    )
    assert (memory_dir / "user" / "profile.md").exists()
