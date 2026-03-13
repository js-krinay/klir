"""Tests for memory retrieval hook."""

from __future__ import annotations

from pathlib import Path

import pytest

from klir.memory.hooks import build_memory_context
from klir.memory.store import MemoryEntry, MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(tmp_path / "index.db")
    s.upsert(
        MemoryEntry(
            uri="user/preferences/testing.md",
            abstract="User prefers pytest with strict markers and 100% coverage",
            category="preferences",
            content="Always use pytest. Never mock the database.",
        )
    )
    s.upsert(
        MemoryEntry(
            uri="agent/cases/auth-fix.md",
            abstract="Fixed auth token expiry in the login endpoint",
            category="cases",
            content="Token refresh logic was missing in middleware.",
        )
    )
    s.upsert(
        MemoryEntry(
            uri="user/profile.md",
            abstract="Senior backend engineer who prefers Python and Go",
            category="profile",
            content="10 years experience. Focuses on API design.",
        )
    )
    return s


def test_build_memory_context_returns_relevant(store: MemoryStore) -> None:
    """build_memory_context returns memories relevant to the prompt."""
    ctx = build_memory_context(store, "write tests for the auth endpoint")
    assert "auth" in ctx.lower()
    assert "token" in ctx.lower() or "login" in ctx.lower()


def test_build_memory_context_includes_profile_on_new_session(store: MemoryStore) -> None:
    """Profile is always included for new sessions."""
    ctx = build_memory_context(store, "hello", is_new_session=True)
    assert "Senior backend engineer" in ctx


def test_build_memory_context_empty_store(tmp_path: Path) -> None:
    """Empty store returns empty context."""
    store = MemoryStore(tmp_path / "empty.db")
    ctx = build_memory_context(store, "anything")
    assert ctx == ""


def test_build_memory_context_limits_size(store: MemoryStore) -> None:
    """Context is bounded to prevent token bloat."""
    # Add many memories
    for i in range(50):
        store.upsert(
            MemoryEntry(
                uri=f"agent/patterns/p{i}.md",
                abstract=f"Pattern {i}: always validate input before processing",
                category="patterns",
                content=f"Detailed content for pattern {i}. " * 20,
            )
        )
    ctx = build_memory_context(store, "validate input")
    # Should be bounded (not all 50 memories dumped)
    assert len(ctx) < 8000


def test_hook_apply_appends_context(store: MemoryStore) -> None:
    """MemoryRetrievalHook.apply appends memory context to prompt."""
    from klir.memory.hooks import MemoryRetrievalHook

    hook = MemoryRetrievalHook(store)
    result = hook.apply("write tests for auth")
    assert "write tests for auth" in result
    assert "## Recalled Memories" in result


def test_build_memory_context_progressive_disclosure(tmp_path: Path) -> None:
    """Top results include content, lower-ranked results are abstract-only."""
    store = MemoryStore(tmp_path / "prog.db")
    # Add enough memories so some are detailed and others are index-only
    for i in range(8):
        store.upsert(
            MemoryEntry(
                uri=f"agent/cases/case-{i}.md",
                abstract=f"Fixed authentication bug variant {i}",
                category="cases",
                content=f"Detailed fix for auth variant {i}. " * 10,
            )
        )
    ctx = build_memory_context(store, "authentication bug fix")
    # Top results should have content (multi-line blocks with **)
    detailed_blocks = [line for line in ctx.split("\n\n") if line.startswith("**[")]
    # Lower results should be abstract-only (single-line with -)
    index_lines = [line for line in ctx.split("\n\n") if line.startswith("- [")]
    # Should have both tiers
    assert len(detailed_blocks) >= 1
    assert len(index_lines) >= 1


def test_hook_apply_no_context_returns_unchanged(tmp_path: Path) -> None:
    """MemoryRetrievalHook.apply returns prompt unchanged when store is empty."""
    from klir.memory.hooks import MemoryRetrievalHook

    empty_store = MemoryStore(tmp_path / "empty.db")
    hook = MemoryRetrievalHook(empty_store)
    result = hook.apply("hello world")
    assert result == "hello world"
