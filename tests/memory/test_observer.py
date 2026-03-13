"""Tests for memory extraction observer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from klir.memory.files import MemoryFileManager
from klir.memory.observer import _abstracts_match, extract_and_store, extract_from_exchanges
from klir.memory.store import MemoryStore


@pytest.fixture
def memory_setup(tmp_path: Path) -> tuple[MemoryFileManager, MemoryStore]:
    memory_dir = tmp_path / "memory_system"
    memory_dir.mkdir()
    store = MemoryStore(memory_dir / "index.db")
    mgr = MemoryFileManager(memory_dir, store)
    return mgr, store


# --- _abstracts_match tests ---


def test_abstracts_match_exact() -> None:
    assert _abstracts_match("User prefers tabs", "User prefers tabs") is True


def test_abstracts_match_case_insensitive() -> None:
    assert _abstracts_match("User Prefers Tabs", "user prefers tabs") is True


def test_abstracts_match_containment() -> None:
    assert _abstracts_match("User prefers tabs", "User prefers tabs over spaces") is True
    assert _abstracts_match("User prefers tabs over spaces", "User prefers tabs") is True


def test_abstracts_match_different() -> None:
    assert _abstracts_match("User prefers tabs", "Fixed Redis timeout") is False


# --- extract_and_store tests ---


@pytest.mark.asyncio
async def test_extract_and_store_happy_path(
    memory_setup: tuple[MemoryFileManager, MemoryStore],
) -> None:
    """Extraction stores new memories and returns count."""
    mgr, store = memory_setup
    fake_response = """
```memory
abstract: User prefers dark mode
category: preferences
---
User has explicitly requested dark mode for all editors.
```
"""
    run_extraction = AsyncMock(return_value=fake_response)
    stored = await extract_and_store("some summary", store, mgr, run_extraction)
    assert stored == 1
    assert store.count() == 1
    results = store.search("dark mode")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_extract_and_store_dedup(
    memory_setup: tuple[MemoryFileManager, MemoryStore],
) -> None:
    """Duplicate memories are skipped."""
    mgr, store = memory_setup
    from klir.memory.files import MemoryFile

    mgr.write(
        MemoryFile(
            category="preferences",
            slug="tabs",
            abstract="User prefers tabs over spaces",
            content="Tabs always.",
        )
    )
    fake_response = """
```memory
abstract: User prefers tabs over spaces
category: preferences
---
Tabs always.
```
"""
    run_extraction = AsyncMock(return_value=fake_response)
    stored = await extract_and_store("summary", store, mgr, run_extraction)
    assert stored == 0
    assert store.count() == 1  # no new entry


@pytest.mark.asyncio
async def test_extract_and_store_error_returns_zero(
    memory_setup: tuple[MemoryFileManager, MemoryStore],
) -> None:
    """CLI extraction failure returns 0."""
    mgr, store = memory_setup
    run_extraction = AsyncMock(side_effect=RuntimeError("CLI failed"))
    stored = await extract_and_store("summary", store, mgr, run_extraction)
    assert stored == 0


@pytest.mark.asyncio
async def test_extract_and_store_no_memories(
    memory_setup: tuple[MemoryFileManager, MemoryStore],
) -> None:
    """No memories to extract returns 0."""
    mgr, store = memory_setup
    run_extraction = AsyncMock(return_value="No memories to extract.")
    stored = await extract_and_store("summary", store, mgr, run_extraction)
    assert stored == 0


# --- extract_from_exchanges tests ---


@pytest.mark.asyncio
async def test_extract_from_exchanges_happy_path(
    memory_setup: tuple[MemoryFileManager, MemoryStore],
) -> None:
    """Exchange extraction stores memories from conversation pairs."""
    mgr, store = memory_setup
    fake_response = """
```memory
abstract: User prefers FastAPI for new projects
category: preferences
---
When asked about framework choice, user consistently picks FastAPI.
```
"""
    run_extraction = AsyncMock(return_value=fake_response)
    exchanges = [
        ("What framework should I use?", "I'd recommend FastAPI for this project."),
        ("Why FastAPI?", "It has great async support and auto-docs."),
    ]
    stored = await extract_from_exchanges(exchanges, store, mgr, run_extraction)
    assert stored == 1
    assert store.count() == 1


@pytest.mark.asyncio
async def test_extract_from_exchanges_empty(
    memory_setup: tuple[MemoryFileManager, MemoryStore],
) -> None:
    """Empty exchanges list returns 0 without calling extraction."""
    mgr, store = memory_setup
    run_extraction = AsyncMock()
    stored = await extract_from_exchanges([], store, mgr, run_extraction)
    assert stored == 0
    run_extraction.assert_not_called()
