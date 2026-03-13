"""Tests for the memory store (SQLite FTS5 index)."""

from __future__ import annotations

from pathlib import Path

import pytest

from klir.memory.store import MemoryEntry, MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "index.db")


def test_add_and_search(store: MemoryStore) -> None:
    """Added memories are found by BM25 search."""
    store.upsert(
        MemoryEntry(
            uri="user/preferences/testing.md",
            abstract="User prefers pytest with strict markers",
            category="preferences",
            content="Always use pytest --strict-markers and 100% coverage.",
        )
    )
    results = store.search("pytest strict markers")
    assert len(results) >= 1
    assert results[0].uri == "user/preferences/testing.md"


def test_search_returns_empty_when_no_match(store: MemoryStore) -> None:
    """Search returns empty list when nothing matches."""
    store.upsert(
        MemoryEntry(
            uri="user/preferences/testing.md",
            abstract="User prefers pytest",
            category="preferences",
            content="pytest only.",
        )
    )
    results = store.search("kubernetes deployment helm")
    assert results == []


def test_upsert_updates_existing(store: MemoryStore) -> None:
    """Upserting same URI updates the entry."""
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Senior engineer",
            category="profile",
            content="Senior backend engineer.",
        )
    )
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Staff engineer",
            category="profile",
            content="Staff backend engineer.",
        )
    )
    results = store.search("staff engineer")
    assert len(results) == 1
    assert results[0].abstract == "Staff engineer"


def test_delete(store: MemoryStore) -> None:
    """Deleted entries are not returned by search."""
    store.upsert(
        MemoryEntry(
            uri="agent/cases/auth-fix.md",
            abstract="Fixed auth token expiry bug",
            category="cases",
            content="Token was not refreshed.",
        )
    )
    store.delete("agent/cases/auth-fix.md")
    results = store.search("auth token")
    assert results == []


def test_search_limit(store: MemoryStore) -> None:
    """Search respects the limit parameter."""
    for i in range(20):
        store.upsert(
            MemoryEntry(
                uri=f"agent/patterns/pattern-{i}.md",
                abstract=f"Pattern {i} for testing search limit",
                category="patterns",
                content=f"Pattern {i} content about testing.",
            )
        )
    results = store.search("pattern testing", limit=5)
    assert len(results) == 5


def test_list_by_category(store: MemoryStore) -> None:
    """List returns all entries for a given category."""
    store.upsert(
        MemoryEntry(
            uri="user/preferences/a.md",
            abstract="A",
            category="preferences",
            content="A",
        )
    )
    store.upsert(
        MemoryEntry(
            uri="user/preferences/b.md",
            abstract="B",
            category="preferences",
            content="B",
        )
    )
    store.upsert(
        MemoryEntry(
            uri="agent/cases/c.md",
            abstract="C",
            category="cases",
            content="C",
        )
    )
    results = store.list_category("preferences")
    assert len(results) == 2
    uris = {r.uri for r in results}
    assert uris == {"user/preferences/a.md", "user/preferences/b.md"}


def test_all_abstracts(store: MemoryStore) -> None:
    """all_abstracts returns URI+abstract pairs for index building."""
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Staff eng",
            category="profile",
            content="...",
        )
    )
    store.upsert(
        MemoryEntry(
            uri="agent/cases/x.md",
            abstract="Fixed X",
            category="cases",
            content="...",
        )
    )
    abstracts = store.all_abstracts()
    assert len(abstracts) == 2
    assert ("user/profile.md", "Staff eng") in abstracts


def test_empty_query_returns_empty(store: MemoryStore) -> None:
    """Empty or whitespace-only queries return empty results."""
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="test",
            category="profile",
            content="test",
        )
    )
    assert store.search("") == []
    assert store.search("   ") == []


def test_persistence_across_instances(tmp_path: Path) -> None:
    """Data survives closing and reopening the store."""
    db_path = tmp_path / "index.db"
    store1 = MemoryStore(db_path)
    store1.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Persistent",
            category="profile",
            content="Data",
        )
    )
    store1.close()

    store2 = MemoryStore(db_path)
    results = store2.search("persistent")
    assert len(results) == 1
    store2.close()


def test_search_with_quotes_in_query(store: MemoryStore) -> None:
    """Queries containing double quotes don't crash."""
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Test entry",
            category="profile",
            content="Some content here.",
        )
    )
    # Should not raise, should fall back gracefully
    results = store.search('he said "hello" to me')
    assert isinstance(results, list)


def test_search_with_fts5_operators(store: MemoryStore) -> None:
    """FTS5 operators in user input don't break search."""
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Test entry",
            category="profile",
            content="Some content here.",
        )
    )
    for query in ["NOT something", "this AND that", "foo OR bar", "NEAR(a b)"]:
        results = store.search(query)
        assert isinstance(results, list)


def test_search_with_special_characters(store: MemoryStore) -> None:
    """Special characters in queries are handled."""
    store.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Test entry",
            category="profile",
            content="Some content here.",
        )
    )
    for query in ["(parens)", "asterisk*", "colon:", "back\\slash"]:
        results = store.search(query)
        assert isinstance(results, list)
