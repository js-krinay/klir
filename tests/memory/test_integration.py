"""Integration test: full memory lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from klir.memory.extractor import parse_extraction_response
from klir.memory.files import MemoryFile, MemoryFileManager
from klir.memory.hooks import build_memory_context
from klir.memory.store import MemoryStore


@pytest.fixture
def setup(tmp_path: Path) -> tuple[MemoryStore, MemoryFileManager]:
    memory_dir = tmp_path / "memory_system"
    memory_dir.mkdir()
    store = MemoryStore(memory_dir / "index.db")
    mgr = MemoryFileManager(memory_dir, store)
    return store, mgr


def test_full_lifecycle(setup: tuple[MemoryStore, MemoryFileManager]) -> None:
    """Write -> search -> retrieve -> inject -> extract cycle."""
    store, mgr = setup

    # Phase 1: Seed initial memories
    mgr.write(
        MemoryFile(
            category="profile",
            slug="main",
            abstract="Backend engineer specializing in Python APIs",
            content="10 years exp. FastAPI, Django, asyncio.",
        )
    )
    mgr.write(
        MemoryFile(
            category="preferences",
            slug="testing",
            abstract="Strict pytest with real database integration tests",
            content="No mocking. Use test containers. 100% coverage target.",
        )
    )
    mgr.write(
        MemoryFile(
            category="cases",
            slug="redis-timeout",
            abstract="Fixed Redis connection timeout in production",
            content="Root cause: connection pool exhaustion. Fix: increase pool size and add health checks.",
        )
    )

    # Phase 2: Search finds relevant memories
    results = store.search("pytest database testing")
    assert any("testing" in r.uri for r in results)

    # Phase 3: Context injection includes relevant memories
    ctx = build_memory_context(store, "write integration tests for the API", is_new_session=True)
    assert "Backend engineer" in ctx  # Profile always loaded on new session
    assert "pytest" in ctx.lower() or "testing" in ctx.lower()  # Relevant to prompt

    # Phase 4: Extraction produces valid candidates
    fake_llm_response = """
```memory
abstract: API uses FastAPI 0.100+ with Pydantic v2
category: entities
---
The main API project uses FastAPI >= 0.100 with Pydantic v2 models.
All endpoints return Pydantic BaseModel instances.
```
"""
    candidates = parse_extraction_response(fake_llm_response)
    assert len(candidates) == 1

    # Phase 5: Store extracted memory
    c = candidates[0]
    mgr.write(
        MemoryFile(
            category=c.category,
            slug=c.slug,
            abstract=c.abstract,
            content=c.content,
        )
    )
    assert store.count() == 4  # 3 original + 1 extracted

    # Phase 6: New search finds the extracted memory
    results2 = store.search("FastAPI Pydantic")
    assert any(
        "fastapi" in r.abstract.lower() or "pydantic" in r.abstract.lower() for r in results2
    )


def test_rebuild_preserves_search(setup: tuple[MemoryStore, MemoryFileManager]) -> None:
    """Rebuilding the index from disk preserves searchability."""
    store, mgr = setup

    mgr.write(
        MemoryFile(
            category="patterns",
            slug="deploy-flow",
            abstract="Always run migrations before deploying",
            content="1. Run alembic upgrade head\n2. Deploy\n3. Verify health check.",
        )
    )

    # Rebuild index from scratch
    mgr.rebuild_index()

    results = store.search("deploy migration")
    assert len(results) >= 1
    assert "deploy" in results[0].abstract.lower()
