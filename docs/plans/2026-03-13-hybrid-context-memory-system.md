# Hybrid Context Memory System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace klir's flat `MAINMEMORY.md` with a 6-category hierarchical memory system that uses SQLite FTS5 + BM25 for retrieval and LLM-as-retriever for ranking, with zero new external dependencies.

**Architecture:** Memories are organized into a hierarchical directory structure inspired by OpenViking's taxonomy (profile, preferences, entities, events, cases, patterns). Each memory file has an L0 abstract (one-liner) stored in a SQLite FTS5 index for fast BM25 retrieval. On each CLI call, the hook queries the index, retrieves top candidates, and injects only relevant memories into the prompt. Session-end extraction uses the existing CLI providers to extract new memories from stale sessions.

**Tech Stack:** Python 3.11+ stdlib (`sqlite3` with FTS5), existing klir infrastructure (`atomic_io`, `KlirPaths`, `MessageHookRegistry`, `ObserverManager`)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Telegram Message                │
├─────────────────────────────────────────────────┤
│  Orchestrator._prepare_normal()                 │
│    ├── MemoryHook.condition() fires             │
│    │   ├── MemoryStore.search(prompt) → BM25    │
│    │   ├── Top-N abstracts appended to prompt   │
│    │   └── CLI agent sees relevant memories     │
│    └── CLI executes with enriched prompt         │
├─────────────────────────────────────────────────┤
│  Session goes stale (_is_fresh() → False)       │
│    └── MemoryExtractor.extract(session_summary) │
│        ├── CLI provider extracts memories       │
│        ├── Dedup against existing index          │
│        ├── Write .md files to category dirs      │
│        └── Update FTS5 index                     │
└─────────────────────────────────────────────────┘
```

### Memory Directory Layout

```
~/.klir/workspace/memory_system/
├── MAINMEMORY.md              ← kept for backward compat (auto-generated summary)
├── RULES.md                   ← updated with new structure docs
├── index.db                   ← SQLite FTS5 index
├── user/
│   ├── profile.md             ← L0: always loaded (about the user)
│   ├── preferences/           ← L1: loaded on relevance
│   │   ├── coding-style.md
│   │   └── communication.md
│   └── entities/              ← L1: loaded on relevance
│       ├── project-foo.md
│       └── team-bar.md
└── agent/
    ├── cases/                 ← L2: semantic search only
    │   ├── fix-auth-bug.md
    │   └── deploy-pipeline.md
    └── patterns/              ← L2: semantic search only
        ├── test-first.md
        └── pr-workflow.md
```

### Memory File Format

```markdown
---
abstract: User prefers pytest with strict mode and 100% coverage
category: preferences
created: 2026-03-13
updated: 2026-03-13
source_session: abc123
---

User has consistently asked for:
- pytest with `--strict-markers`
- Coverage threshold of 100%
- No mocking of databases (use real test DB)
- Fixtures over setUp/tearDown
```

### Retrieval Flow (Per Message)

1. **Every message**: BM25 search prompt against FTS5 index → top 10 abstracts
2. **New session**: Load `user/profile.md` (L0) unconditionally + top 5 BM25 results as `append_system_prompt`
3. **Every 6th message** (existing cadence): Inject memory-check suffix asking CLI to update memories
4. **Future upgrade path**: Swap BM25 search for embedding search at `MemoryStore.search()` — single function change

---

## Task 1: MemoryStore — SQLite FTS5 Index

**Files:**
- Create: `klir/memory/__init__.py`
- Create: `klir/memory/store.py`
- Test: `tests/memory/test_store.py`

This is the core retrieval layer. It wraps a SQLite database with an FTS5 virtual table for BM25-ranked full-text search of memory abstracts and content.

**Step 1: Write the failing tests**

```python
# tests/memory/__init__.py
# (empty)
```

```python
# tests/memory/test_store.py
"""Tests for the memory store (SQLite FTS5 index)."""

from __future__ import annotations

import pytest
from pathlib import Path

from klir.memory.store import MemoryEntry, MemoryStore


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "index.db")


def test_add_and_search(store: MemoryStore) -> None:
    """Added memories are found by BM25 search."""
    store.upsert(MemoryEntry(
        uri="user/preferences/testing.md",
        abstract="User prefers pytest with strict markers",
        category="preferences",
        content="Always use pytest --strict-markers and 100% coverage.",
    ))
    results = store.search("pytest strict markers")
    assert len(results) >= 1
    assert results[0].uri == "user/preferences/testing.md"


def test_search_returns_empty_when_no_match(store: MemoryStore) -> None:
    """Search returns empty list when nothing matches."""
    store.upsert(MemoryEntry(
        uri="user/preferences/testing.md",
        abstract="User prefers pytest",
        category="preferences",
        content="pytest only.",
    ))
    results = store.search("kubernetes deployment helm")
    assert results == []


def test_upsert_updates_existing(store: MemoryStore) -> None:
    """Upserting same URI updates the entry."""
    store.upsert(MemoryEntry(
        uri="user/profile.md",
        abstract="Senior engineer",
        category="profile",
        content="Senior backend engineer.",
    ))
    store.upsert(MemoryEntry(
        uri="user/profile.md",
        abstract="Staff engineer",
        category="profile",
        content="Staff backend engineer.",
    ))
    results = store.search("staff engineer")
    assert len(results) == 1
    assert results[0].abstract == "Staff engineer"


def test_delete(store: MemoryStore) -> None:
    """Deleted entries are not returned by search."""
    store.upsert(MemoryEntry(
        uri="agent/cases/auth-fix.md",
        abstract="Fixed auth token expiry bug",
        category="cases",
        content="Token was not refreshed.",
    ))
    store.delete("agent/cases/auth-fix.md")
    results = store.search("auth token")
    assert results == []


def test_search_limit(store: MemoryStore) -> None:
    """Search respects the limit parameter."""
    for i in range(20):
        store.upsert(MemoryEntry(
            uri=f"agent/patterns/pattern-{i}.md",
            abstract=f"Pattern {i} for testing search limit",
            category="patterns",
            content=f"Pattern {i} content about testing.",
        ))
    results = store.search("pattern testing", limit=5)
    assert len(results) == 5


def test_list_by_category(store: MemoryStore) -> None:
    """List returns all entries for a given category."""
    store.upsert(MemoryEntry(
        uri="user/preferences/a.md", abstract="A", category="preferences", content="A",
    ))
    store.upsert(MemoryEntry(
        uri="user/preferences/b.md", abstract="B", category="preferences", content="B",
    ))
    store.upsert(MemoryEntry(
        uri="agent/cases/c.md", abstract="C", category="cases", content="C",
    ))
    results = store.list_category("preferences")
    assert len(results) == 2
    uris = {r.uri for r in results}
    assert uris == {"user/preferences/a.md", "user/preferences/b.md"}


def test_all_abstracts(store: MemoryStore) -> None:
    """all_abstracts returns URI+abstract pairs for index building."""
    store.upsert(MemoryEntry(
        uri="user/profile.md", abstract="Staff eng", category="profile", content="...",
    ))
    store.upsert(MemoryEntry(
        uri="agent/cases/x.md", abstract="Fixed X", category="cases", content="...",
    ))
    abstracts = store.all_abstracts()
    assert len(abstracts) == 2
    assert ("user/profile.md", "Staff eng") in abstracts


def test_empty_query_returns_empty(store: MemoryStore) -> None:
    """Empty or whitespace-only queries return empty results."""
    store.upsert(MemoryEntry(
        uri="user/profile.md", abstract="test", category="profile", content="test",
    ))
    assert store.search("") == []
    assert store.search("   ") == []


def test_persistence_across_instances(tmp_path: Path) -> None:
    """Data survives closing and reopening the store."""
    db_path = tmp_path / "index.db"
    store1 = MemoryStore(db_path)
    store1.upsert(MemoryEntry(
        uri="user/profile.md", abstract="Persistent", category="profile", content="Data",
    ))
    store1.close()

    store2 = MemoryStore(db_path)
    results = store2.search("persistent")
    assert len(results) == 1
    store2.close()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'klir.memory'`

**Step 3: Write the implementation**

```python
# klir/memory/__init__.py
"""Hierarchical memory system with FTS5 retrieval."""

from klir.memory.store import MemoryEntry as MemoryEntry
from klir.memory.store import MemoryStore as MemoryStore

__all__ = ["MemoryEntry", "MemoryStore"]
```

```python
# klir/memory/store.py
"""SQLite FTS5 memory index with BM25 ranking.

Stores memory abstracts and content in a full-text search index.
Retrieval uses BM25 scoring with a fallback to substring matching.
The interface is designed so the search implementation can be swapped
to embedding-based retrieval without changing callers.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A single memory record."""

    uri: str
    abstract: str
    category: str
    content: str
    score: float = 0.0


class MemoryStore:
    """SQLite-backed memory index with FTS5 full-text search.

    The ``search`` method is the single retrieval interface.  Currently
    it uses BM25 over FTS5; a future embedding backend only needs to
    replace the body of ``search`` (and possibly ``upsert``).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                uri TEXT PRIMARY KEY,
                abstract TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                uri,
                abstract,
                category,
                content,
                content='memories',
                content_rowid='rowid',
                tokenize='porter unicode61'
            );
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, uri, abstract, category, content)
                VALUES (new.rowid, new.uri, new.abstract, new.category, new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, uri, abstract, category, content)
                VALUES ('delete', old.rowid, old.uri, old.abstract, old.category, old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, uri, abstract, category, content)
                VALUES ('delete', old.rowid, old.uri, old.abstract, old.category, old.content);
                INSERT INTO memories_fts(rowid, uri, abstract, category, content)
                VALUES (new.rowid, new.uri, new.abstract, new.category, new.content);
            END;
        """)
        self._conn.commit()

    def upsert(self, entry: MemoryEntry) -> None:
        """Insert or update a memory entry."""
        self._conn.execute(
            """INSERT INTO memories (uri, abstract, category, content)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(uri) DO UPDATE SET
                   abstract = excluded.abstract,
                   category = excluded.category,
                   content = excluded.content,
                   updated_at = datetime('now')""",
            (entry.uri, entry.abstract, entry.category, entry.content),
        )
        self._conn.commit()

    def delete(self, uri: str) -> None:
        """Remove a memory entry by URI."""
        self._conn.execute("DELETE FROM memories WHERE uri = ?", (uri,))
        self._conn.commit()

    def search(self, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by BM25 relevance.

        This is the single retrieval interface.  To swap to embeddings,
        replace this method body.
        """
        query = query.strip()
        if not query:
            return []

        # Escape FTS5 special characters and build OR query for flexibility
        tokens = query.split()
        fts_query = " OR ".join(f'"{t}"' for t in tokens if t)
        if not fts_query:
            return []

        try:
            rows = self._conn.execute(
                """SELECT m.uri, m.abstract, m.category, m.content,
                          rank * -1 AS score
                   FROM memories_fts f
                   JOIN memories m ON m.rowid = f.rowid
                   WHERE memories_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            logger.debug("FTS5 query failed, falling back to LIKE: %s", fts_query)
            like_pattern = f"%{tokens[0]}%" if tokens else "%"
            rows = self._conn.execute(
                """SELECT uri, abstract, category, content, 0.0 AS score
                   FROM memories
                   WHERE abstract LIKE ? OR content LIKE ?
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (like_pattern, like_pattern, limit),
            ).fetchall()

        return [
            MemoryEntry(uri=r[0], abstract=r[1], category=r[2], content=r[3], score=r[4])
            for r in rows
        ]

    def list_category(self, category: str) -> list[MemoryEntry]:
        """List all entries in a category."""
        rows = self._conn.execute(
            "SELECT uri, abstract, category, content FROM memories WHERE category = ?",
            (category,),
        ).fetchall()
        return [MemoryEntry(uri=r[0], abstract=r[1], category=r[2], content=r[3]) for r in rows]

    def all_abstracts(self) -> list[tuple[str, str]]:
        """Return all (uri, abstract) pairs for index summaries."""
        return self._conn.execute(
            "SELECT uri, abstract FROM memories ORDER BY updated_at DESC"
        ).fetchall()

    def count(self) -> int:
        """Return total number of stored memories."""
        row = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add klir/memory/__init__.py klir/memory/store.py tests/memory/__init__.py tests/memory/test_store.py
git commit -m "feat(memory): Add SQLite FTS5 memory store with BM25 retrieval"
```

---

## Task 2: MemoryFileManager — Disk Layout and Sync

**Files:**
- Create: `klir/memory/files.py`
- Test: `tests/memory/test_files.py`

This manages the on-disk markdown files and keeps them in sync with the SQLite index. It reads/writes the hierarchical directory structure and parses the YAML frontmatter format.

**Step 1: Write the failing tests**

```python
# tests/memory/test_files.py
"""Tests for memory file manager."""

from __future__ import annotations

import pytest
from pathlib import Path

from klir.memory.files import MemoryFileManager, MemoryFile
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
    mgr: MemoryFileManager, store: MemoryStore, memory_dir: Path,
) -> None:
    """Deleting a memory removes both the file and the index entry."""
    mf = MemoryFile(
        category="patterns", slug="tdd", abstract="TDD workflow", content="Red green refactor.",
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
    mgr.write(MemoryFile(
        category="profile", slug="main", abstract="Staff eng", content="Staff backend engineer.",
    ))
    assert (memory_dir / "user" / "profile.md").exists()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memory/test_files.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'klir.memory.files'`

**Step 3: Write the implementation**

```python
# klir/memory/files.py
"""Memory file manager: reads/writes the hierarchical directory layout.

Keeps the on-disk markdown files and the SQLite FTS5 index in sync.
Parses a minimal YAML-like frontmatter for abstract/category metadata.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from klir.memory.store import MemoryEntry, MemoryStore

logger = logging.getLogger(__name__)

# Categories and their directory prefixes
_CATEGORY_DIRS: dict[str, str] = {
    "profile": "user",
    "preferences": "user/preferences",
    "entities": "user/entities",
    "events": "user/events",
    "cases": "agent/cases",
    "patterns": "agent/patterns",
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(slots=True)
class MemoryFile:
    """Parsed memory file data."""

    category: str
    slug: str
    abstract: str
    content: str


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML-like frontmatter from markdown text.

    Returns (metadata_dict, body).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = text[match.end():]
    return meta, body


def _render_frontmatter(mf: MemoryFile) -> str:
    """Render a memory file to markdown with frontmatter."""
    return (
        f"---\n"
        f"abstract: {mf.abstract}\n"
        f"category: {mf.category}\n"
        f"---\n\n"
        f"{mf.content}\n"
    )


def _uri_for(category: str, slug: str) -> str:
    """Build the URI for a memory entry."""
    prefix = _CATEGORY_DIRS.get(category, f"other/{category}")
    if category == "profile":
        return f"{prefix}/{slug}.md"
    return f"{prefix}/{slug}.md"


class MemoryFileManager:
    """Manages memory markdown files on disk and syncs with the FTS5 index."""

    def __init__(self, memory_dir: Path, store: MemoryStore) -> None:
        self._root = memory_dir
        self._store = store

    def write(self, mf: MemoryFile) -> Path:
        """Write a memory file to disk and index it."""
        uri = _uri_for(mf.category, mf.slug)
        file_path = self._root / uri
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(_render_frontmatter(mf), encoding="utf-8")

        self._store.upsert(MemoryEntry(
            uri=uri,
            abstract=mf.abstract,
            category=mf.category,
            content=mf.content,
        ))
        logger.info("Memory written: %s", uri)
        return file_path

    def read(self, category: str, slug: str) -> MemoryFile | None:
        """Read a memory file from disk."""
        uri = _uri_for(category, slug)
        file_path = self._root / uri
        if not file_path.exists():
            return None

        text = file_path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        return MemoryFile(
            category=meta.get("category", category),
            slug=slug,
            abstract=meta.get("abstract", ""),
            content=body.strip(),
        )

    def delete(self, category: str, slug: str) -> None:
        """Delete a memory file from disk and the index."""
        uri = _uri_for(category, slug)
        file_path = self._root / uri
        if file_path.exists():
            file_path.unlink()
        self._store.delete(uri)
        logger.info("Memory deleted: %s", uri)

    def list_all(self) -> list[MemoryFile]:
        """List all memory files from the index."""
        entries = self._store.all_abstracts()
        results: list[MemoryFile] = []
        for uri, abstract in entries:
            file_path = self._root / uri
            if not file_path.exists():
                continue
            text = file_path.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            parts = uri.rsplit("/", 1)
            slug = parts[-1].removesuffix(".md") if len(parts) > 1 else uri.removesuffix(".md")
            results.append(MemoryFile(
                category=meta.get("category", ""),
                slug=slug,
                abstract=abstract,
                content=body.strip(),
            ))
        return results

    def rebuild_index(self) -> None:
        """Rebuild the FTS5 index from all markdown files on disk.

        Walks the memory directory, parses frontmatter, and upserts each file.
        """
        count = 0
        for category, dir_prefix in _CATEGORY_DIRS.items():
            cat_path = self._root / dir_prefix
            if not cat_path.exists():
                continue
            for md_file in cat_path.glob("*.md"):
                text = md_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)
                slug = md_file.stem
                uri = _uri_for(meta.get("category", category), slug)
                self._store.upsert(MemoryEntry(
                    uri=uri,
                    abstract=meta.get("abstract", body[:80]),
                    category=meta.get("category", category),
                    content=body.strip(),
                ))
                count += 1
        logger.info("Index rebuilt: %d memories", count)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/memory/test_files.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add klir/memory/files.py tests/memory/test_files.py
git commit -m "feat(memory): Add file manager for hierarchical memory layout"
```

---

## Task 3: Wire MemoryStore into KlirPaths and Orchestrator

**Files:**
- Modify: `klir/workspace/paths.py` (add `memory_index_path` property)
- Modify: `klir/orchestrator/core.py` (initialize MemoryStore)
- Modify: `klir/orchestrator/lifecycle.py` (wire store into creation)
- Test: `tests/memory/test_wiring.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_wiring.py
"""Test that MemoryStore is wired into the orchestrator."""

from __future__ import annotations

from pathlib import Path

from klir.workspace.paths import KlirPaths


def test_memory_index_path() -> None:
    """KlirPaths exposes memory_index_path."""
    paths = KlirPaths(klir_home=Path("/tmp/test-klir"))
    assert paths.memory_index_path == Path("/tmp/test-klir/workspace/memory_system/index.db")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/memory/test_wiring.py -v`
Expected: FAIL with `AttributeError: 'KlirPaths' object has no attribute 'memory_index_path'`

**Step 3: Add memory_index_path to KlirPaths**

In `klir/workspace/paths.py`, after the `mainmemory_path` property (around line 143), add:

```python
    @property
    def memory_index_path(self) -> Path:
        return self.memory_system_dir / "index.db"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/memory/test_wiring.py -v`
Expected: PASS

**Step 5: Add MemoryStore to Orchestrator**

In `klir/orchestrator/core.py`:

1. Add import at the top:
```python
from klir.memory.store import MemoryStore
from klir.memory.files import MemoryFileManager
```

2. In `Orchestrator.__init__()`, after `self._hook_registry` initialization (around line 172), add:
```python
        self._memory_store = MemoryStore(paths.memory_index_path)
        self._memory_files = MemoryFileManager(paths.memory_system_dir, self._memory_store)
```

3. Add public properties:
```python
    @property
    def memory_store(self) -> MemoryStore:
        """Public access to the memory store."""
        return self._memory_store

    @property
    def memory_files(self) -> MemoryFileManager:
        """Public access to the memory file manager."""
        return self._memory_files
```

4. In `shutdown()` (or `lifecycle.shutdown()`), add cleanup:
```python
    orch._memory_store.close()
```

**Step 6: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All existing tests still pass, new test passes

**Step 7: Commit**

```bash
git add klir/workspace/paths.py klir/orchestrator/core.py tests/memory/test_wiring.py
git commit -m "feat(memory): Wire MemoryStore into KlirPaths and Orchestrator"
```

---

## Task 4: Memory Retrieval Hook

**Files:**
- Create: `klir/memory/hooks.py`
- Modify: `klir/orchestrator/hooks.py` (update MAINMEMORY_REMINDER)
- Modify: `klir/orchestrator/core.py` (register new hook)
- Modify: `klir/orchestrator/flows.py` (pass store to hook context)
- Test: `tests/memory/test_hooks.py`

This is the critical integration point. It replaces the existing "silently review MAINMEMORY.md" approach with an active retrieval step that searches the FTS5 index and injects relevant memories.

**Step 1: Write the failing tests**

```python
# tests/memory/test_hooks.py
"""Tests for memory retrieval hook."""

from __future__ import annotations

import pytest
from pathlib import Path

from klir.memory.hooks import build_memory_context, MemoryRetrievalHook
from klir.memory.store import MemoryEntry, MemoryStore
from klir.orchestrator.hooks import HookContext


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(tmp_path / "index.db")
    s.upsert(MemoryEntry(
        uri="user/preferences/testing.md",
        abstract="User prefers pytest with strict markers and 100% coverage",
        category="preferences",
        content="Always use pytest. Never mock the database.",
    ))
    s.upsert(MemoryEntry(
        uri="agent/cases/auth-fix.md",
        abstract="Fixed auth token expiry in the login endpoint",
        category="cases",
        content="Token refresh logic was missing in middleware.",
    ))
    s.upsert(MemoryEntry(
        uri="user/profile.md",
        abstract="Senior backend engineer who prefers Python and Go",
        category="profile",
        content="10 years experience. Focuses on API design.",
    ))
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
        store.upsert(MemoryEntry(
            uri=f"agent/patterns/p{i}.md",
            abstract=f"Pattern {i}: always validate input before processing",
            category="patterns",
            content=f"Detailed content for pattern {i}. " * 20,
        ))
    ctx = build_memory_context(store, "validate input")
    # Should be bounded (not all 50 memories dumped)
    assert len(ctx) < 8000
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memory/test_hooks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'klir.memory.hooks'`

**Step 3: Write the implementation**

```python
# klir/memory/hooks.py
"""Memory retrieval hook: searches the FTS5 index and builds context for injection.

This module provides the bridge between the MemoryStore and the
MessageHookRegistry. The ``build_memory_context`` function is the
single entry point for retrieving relevant memories for a prompt.
"""

from __future__ import annotations

import logging

from klir.memory.store import MemoryStore

logger = logging.getLogger(__name__)

# Maximum characters of memory context to inject per message
_MAX_CONTEXT_CHARS = 6000
# Number of BM25 results to retrieve
_SEARCH_LIMIT = 8
# Number of profile entries to include on new sessions
_PROFILE_LIMIT = 3


def build_memory_context(
    store: MemoryStore,
    prompt: str,
    *,
    is_new_session: bool = False,
) -> str:
    """Build a memory context string for injection into the CLI prompt.

    On new sessions, always includes profile memories.
    On every call, searches for prompt-relevant memories via BM25.

    Returns a formatted string ready for prompt injection, or empty string
    if no relevant memories are found.
    """
    if store.count() == 0:
        return ""

    sections: list[str] = []
    seen_uris: set[str] = set()
    budget = _MAX_CONTEXT_CHARS

    # L0: Always load profile on new sessions
    if is_new_session:
        profiles = store.list_category("profile")
        for entry in profiles[:_PROFILE_LIMIT]:
            block = f"**[{entry.uri}]** {entry.abstract}\n{entry.content}"
            if len(block) > budget:
                break
            sections.append(block)
            seen_uris.add(entry.uri)
            budget -= len(block)

    # L1/L2: BM25 search for relevant memories
    if prompt.strip():
        results = store.search(prompt, limit=_SEARCH_LIMIT)
        for entry in results:
            if entry.uri in seen_uris:
                continue
            # For search results, include abstract + truncated content
            content_preview = entry.content[:500] if len(entry.content) > 500 else entry.content
            block = f"**[{entry.uri}]** {entry.abstract}\n{content_preview}"
            if len(block) > budget:
                # Try abstract-only
                block = f"**[{entry.uri}]** {entry.abstract}"
                if len(block) > budget:
                    break
            sections.append(block)
            seen_uris.add(entry.uri)
            budget -= len(block)

    if not sections:
        return ""

    header = "## Recalled Memories\nRelevant context from long-term memory:\n"
    return header + "\n\n".join(sections)


class MemoryRetrievalHook:
    """Stateful hook that injects retrieved memories into prompts.

    Unlike the static ``MessageHook`` dataclass, this needs a reference
    to the ``MemoryStore`` instance.  It exposes the same ``(condition, suffix)``
    interface but computes the suffix dynamically.
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def apply(self, prompt: str, *, is_new_session: bool = False) -> str:
        """Apply memory retrieval to a prompt.

        Returns the prompt with memory context appended, or unchanged
        if no relevant memories are found.
        """
        ctx = build_memory_context(self._store, prompt, is_new_session=is_new_session)
        if not ctx:
            return prompt
        return prompt + "\n\n" + ctx
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/memory/test_hooks.py -v`
Expected: All 4 tests PASS

**Step 5: Integrate into flows.py**

In `klir/orchestrator/flows.py`, modify `_prepare_normal()`:

1. Add import:
```python
from klir.memory.hooks import MemoryRetrievalHook
```

2. After the hook_registry.apply() call (around line 110-111), add memory retrieval:
```python
    prompt = orch._hook_registry.apply(text, hook_ctx)
    # Memory retrieval: inject relevant memories from FTS5 index
    memory_hook = MemoryRetrievalHook(orch._memory_store)
    prompt = memory_hook.apply(prompt, is_new_session=is_new)
    prompt = orch._user_hooks.apply_pre(prompt, hook_ctx)
```

3. The existing `read_mainmemory()` call on new sessions (lines 94-97) should be kept temporarily for backward compatibility, but will be replaced by the profile loading in `build_memory_context`. Mark it with a TODO:
```python
    # TODO(memory-v2): Remove once profile migration is complete.
    #   Profile loading is now handled by MemoryRetrievalHook.
    append_prompt = None
    if is_new:
        mainmemory = await asyncio.to_thread(read_mainmemory, orch.paths)
        if mainmemory.strip():
            append_prompt = mainmemory
```

**Step 6: Update MAINMEMORY_REMINDER hook**

In `klir/orchestrator/hooks.py`, update the suffix of `MAINMEMORY_REMINDER` to reference the new structure:

```python
MAINMEMORY_REMINDER = MessageHook(
    name="mainmemory_reminder",
    condition=every_n_messages(6),
    suffix=(
        "## MEMORY CHECK\n"
        "Silently review: memory_system/ (user/profile.md, user/preferences/, "
        "user/entities/, agent/cases/, agent/patterns/).\n"
        "Compare what you already know with this conversation so far.\n"
        "If something important is missing from memory -- create or update the "
        "appropriate memory file with YAML frontmatter "
        "(abstract: one-liner, category: type).\n"
        "If you notice a gap that only the user can fill, ask ONE natural follow-up "
        "question that fits the current conversation. Do not interrogate."
    ),
)
```

**Step 7: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests pass

**Step 8: Commit**

```bash
git add klir/memory/hooks.py klir/orchestrator/flows.py klir/orchestrator/hooks.py tests/memory/test_hooks.py
git commit -m "feat(memory): Add retrieval hook with BM25 search injection"
```

---

## Task 5: Memory Extraction on Session Staleness

**Files:**
- Create: `klir/memory/extractor.py`
- Modify: `klir/session/manager.py` (add staleness callback)
- Test: `tests/memory/test_extractor.py`

When a session goes stale (idle timeout, daily reset, max messages), we extract memories before creating the new session. This uses the existing CLI providers to analyze the conversation and produce structured memory entries.

**Step 1: Write the failing tests**

```python
# tests/memory/test_extractor.py
"""Tests for memory extraction from session summaries."""

from __future__ import annotations

import pytest
from pathlib import Path

from klir.memory.extractor import (
    MemoryCandidate,
    parse_extraction_response,
)


def test_parse_extraction_response_single() -> None:
    """Parse a single memory from LLM response."""
    response = """
```memory
abstract: User prefers dark mode in all editors
category: preferences
---
User has explicitly requested dark mode for VS Code, terminal, and all
development tools. Apply dark themes by default.
```
"""
    candidates = parse_extraction_response(response)
    assert len(candidates) == 1
    assert candidates[0].abstract == "User prefers dark mode in all editors"
    assert candidates[0].category == "preferences"
    assert "dark mode" in candidates[0].content


def test_parse_extraction_response_multiple() -> None:
    """Parse multiple memories from LLM response."""
    response = """
```memory
abstract: User is a staff engineer at Acme Corp
category: profile
---
Staff-level backend engineer, 10 years experience.
```

```memory
abstract: Always run migrations before deploying
category: patterns
---
The team has a strict deploy process: migrations first, then deploy.
```
"""
    candidates = parse_extraction_response(response)
    assert len(candidates) == 2
    assert candidates[0].category == "profile"
    assert candidates[1].category == "patterns"


def test_parse_extraction_response_empty() -> None:
    """Empty or garbage input returns no candidates."""
    assert parse_extraction_response("") == []
    assert parse_extraction_response("No memories to extract.") == []
    assert parse_extraction_response("```python\nprint('hi')\n```") == []


def test_parse_extraction_response_invalid_category() -> None:
    """Invalid category is normalized to 'cases'."""
    response = """
```memory
abstract: Something happened
category: invalid_category
---
Content here.
```
"""
    candidates = parse_extraction_response(response)
    assert len(candidates) == 1
    assert candidates[0].category == "cases"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memory/test_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'klir.memory.extractor'`

**Step 3: Write the implementation**

```python
# klir/memory/extractor.py
"""Memory extraction: parses LLM responses into structured memory candidates.

The extraction prompt is sent to the active CLI provider at session end.
This module handles parsing the response into ``MemoryCandidate`` objects
that can be deduplicated and written to disk.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = frozenset({
    "profile", "preferences", "entities", "events", "cases", "patterns",
})

_MEMORY_BLOCK_RE = re.compile(
    r"```memory\s*\n"
    r"abstract:\s*(.+?)\n"
    r"category:\s*(.+?)\n"
    r"---\s*\n"
    r"(.*?)"
    r"```",
    re.DOTALL,
)


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:60]


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """A memory extracted from an LLM response, pending dedup and storage."""

    abstract: str
    category: str
    content: str
    slug: str


def parse_extraction_response(response: str) -> list[MemoryCandidate]:
    """Parse ```memory``` blocks from an LLM extraction response.

    Returns a list of MemoryCandidate objects.
    """
    candidates: list[MemoryCandidate] = []

    for match in _MEMORY_BLOCK_RE.finditer(response):
        abstract = match.group(1).strip()
        category = match.group(2).strip().lower()
        content = match.group(3).strip()

        if not abstract or not content:
            continue

        if category not in _VALID_CATEGORIES:
            logger.warning("Invalid memory category '%s', defaulting to 'cases'", category)
            category = "cases"

        candidates.append(MemoryCandidate(
            abstract=abstract,
            category=category,
            content=content,
            slug=_slugify(abstract),
        ))

    return candidates


# The extraction prompt template. Sent to the CLI provider with the
# session summary as context.
EXTRACTION_PROMPT = """You are analyzing a conversation to extract long-term memories.

Review the conversation below and extract any durable knowledge worth remembering
for future sessions. Output each memory as a ```memory``` block:

```memory
abstract: One-line summary of this memory
category: one of: profile, preferences, entities, events, cases, patterns
---
Detailed content (2-5 lines). Focus on facts, decisions, and patterns.
```

Categories:
- profile: About the user (role, expertise, background)
- preferences: User's preferred tools, styles, approaches
- entities: Projects, repos, teams, services the user works with
- events: Specific incidents, decisions with dates
- cases: Problem+solution pairs (debugging, fixes)
- patterns: Reusable workflows or conventions

If nothing is worth remembering, respond with: "No memories to extract."

Conversation summary:
{summary}
"""
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/memory/test_extractor.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add klir/memory/extractor.py tests/memory/test_extractor.py
git commit -m "feat(memory): Add extraction parser for LLM memory responses"
```

---

## Task 6: Session Staleness Extraction Observer

**Files:**
- Create: `klir/memory/observer.py`
- Modify: `klir/orchestrator/observers.py` (add memory observer)
- Modify: `klir/orchestrator/lifecycle.py` (start observer)
- Test: `tests/memory/test_observer.py`

This observer listens for session staleness events and triggers memory extraction. It runs the extraction prompt through the CLI service and writes the results via MemoryFileManager.

**Step 1: Write the failing test**

```python
# tests/memory/test_observer.py
"""Tests for memory extraction observer."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from klir.memory.extractor import MemoryCandidate, parse_extraction_response
from klir.memory.files import MemoryFile, MemoryFileManager
from klir.memory.store import MemoryStore


def test_candidates_to_files() -> None:
    """MemoryCandidate can be converted to MemoryFile for writing."""
    candidate = MemoryCandidate(
        abstract="User prefers tabs",
        category="preferences",
        content="Always use tabs, never spaces.",
        slug="user-prefers-tabs",
    )
    mf = MemoryFile(
        category=candidate.category,
        slug=candidate.slug,
        abstract=candidate.abstract,
        content=candidate.content,
    )
    assert mf.category == "preferences"
    assert mf.slug == "user-prefers-tabs"


@pytest.fixture
def memory_setup(tmp_path: Path) -> tuple[MemoryFileManager, MemoryStore]:
    memory_dir = tmp_path / "memory_system"
    memory_dir.mkdir()
    store = MemoryStore(memory_dir / "index.db")
    mgr = MemoryFileManager(memory_dir, store)
    return mgr, store


def test_dedup_skips_existing(memory_setup: tuple) -> None:
    """Existing memories with same abstract are skipped."""
    mgr, store = memory_setup
    # Write existing memory
    mgr.write(MemoryFile(
        category="preferences",
        slug="tabs",
        abstract="User prefers tabs over spaces",
        content="Tabs always.",
    ))
    # Simulate extraction returning same thing
    candidate = MemoryCandidate(
        abstract="User prefers tabs over spaces",
        category="preferences",
        content="Tabs always.",
        slug="user-prefers-tabs-over-spaces",
    )
    # Check if already exists via search
    existing = store.search(candidate.abstract, limit=1)
    assert len(existing) >= 1
    # Dedup: skip if top result abstract matches closely
    assert existing[0].abstract == "User prefers tabs over spaces"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memory/test_observer.py -v`
Expected: PASS (these are unit-level, no observer module needed yet)

**Step 3: Write the observer**

```python
# klir/memory/observer.py
"""Memory extraction observer: extracts memories when sessions go stale.

This observer hooks into session staleness detection and runs the
extraction prompt through the CLI provider to produce structured
memory entries.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from klir.memory.extractor import EXTRACTION_PROMPT, MemoryCandidate, parse_extraction_response
from klir.memory.files import MemoryFile, MemoryFileManager
from klir.memory.store import MemoryStore

logger = logging.getLogger(__name__)

# Simple dedup: skip if the top search result has the same abstract
_DEDUP_THRESHOLD = 0.9


def _abstracts_match(a: str, b: str) -> bool:
    """Check if two abstracts are similar enough to be duplicates."""
    a_norm = a.strip().lower()
    b_norm = b.strip().lower()
    if a_norm == b_norm:
        return True
    # Simple containment check
    return a_norm in b_norm or b_norm in a_norm


async def extract_and_store(
    summary: str,
    store: MemoryStore,
    files: MemoryFileManager,
    run_extraction: Callable[[str], Awaitable[str]],
) -> int:
    """Run memory extraction and store results.

    Args:
        summary: Conversation summary text to extract from.
        store: The FTS5 memory store for dedup checks.
        files: The file manager for writing memory files.
        run_extraction: Async callable that sends the extraction prompt
            to a CLI provider and returns the response text.

    Returns:
        Number of new memories stored.
    """
    prompt = EXTRACTION_PROMPT.format(summary=summary)

    try:
        response = await run_extraction(prompt)
    except Exception:
        logger.exception("Memory extraction CLI call failed")
        return 0

    candidates = parse_extraction_response(response)
    if not candidates:
        logger.info("No memories extracted from session")
        return 0

    stored = 0
    for candidate in candidates:
        # Simple dedup: check if similar memory already exists
        existing = store.search(candidate.abstract, limit=1)
        if existing and _abstracts_match(existing[0].abstract, candidate.abstract):
            logger.debug("Dedup: skipping '%s' (matches '%s')", candidate.abstract, existing[0].abstract)
            continue

        files.write(MemoryFile(
            category=candidate.category,
            slug=candidate.slug,
            abstract=candidate.abstract,
            content=candidate.content,
        ))
        stored += 1

    logger.info("Memory extraction complete: %d/%d stored", stored, len(candidates))
    return stored
```

**Step 4: Run tests**

Run: `uv run pytest tests/memory/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add klir/memory/observer.py tests/memory/test_observer.py
git commit -m "feat(memory): Add extraction observer for stale sessions"
```

---

## Task 7: Update Workspace Defaults and Migration

**Files:**
- Modify: `klir/_home_defaults/workspace/memory_system/MAINMEMORY.md` (backward compat note)
- Modify: `klir/_home_defaults/workspace/memory_system/RULES.md` (new structure docs)
- Create: `klir/memory/migrate.py` (migrate existing MAINMEMORY.md content)
- Modify: `klir/workspace/init.py` (add migration step)
- Test: `tests/memory/test_migrate.py`

**Step 1: Write the failing test**

```python
# tests/memory/test_migrate.py
"""Tests for MAINMEMORY.md migration to hierarchical structure."""

from __future__ import annotations

import pytest
from pathlib import Path

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
    """Migration is idempotent: skip if user/ directory already exists."""
    (memory_dir / "user").mkdir()
    (memory_dir / "user" / "profile.md").write_text("existing", encoding="utf-8")
    mainmemory = memory_dir / "MAINMEMORY.md"
    mainmemory.write_text("# Main Memory\n\nSome content\n", encoding="utf-8")
    store = MemoryStore(memory_dir / "index.db")
    migrated = migrate_mainmemory(mainmemory, memory_dir, store)
    assert migrated is False  # Already migrated
    store.close()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/memory/test_migrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'klir.memory.migrate'`

**Step 3: Write the implementation**

```python
# klir/memory/migrate.py
"""One-time migration from flat MAINMEMORY.md to hierarchical structure.

Reads the existing MAINMEMORY.md, splits into sections, and writes
the appropriate category files. The original file is renamed to
MAINMEMORY.md.bak as a safety net.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from klir.memory.files import MemoryFile, MemoryFileManager, _uri_for
from klir.memory.store import MemoryEntry, MemoryStore

logger = logging.getLogger(__name__)

_EMPTY_MARKERS = frozenset({
    "(empty",
    "(empty --",
    "(will be populated",
})


def _is_empty_section(text: str) -> bool:
    """Check if a section body is just the default empty placeholder."""
    stripped = text.strip().lower()
    return not stripped or any(stripped.startswith(m) for m in _EMPTY_MARKERS)


def _extract_sections(text: str) -> dict[str, str]:
    """Extract markdown H2 sections from MAINMEMORY.md."""
    sections: dict[str, str] = {}
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        elif current_heading:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


# Map existing section names to new categories
_SECTION_MAP: dict[str, str] = {
    "About the User": "profile",
    "Learned Facts": "entities",
    "Decisions and Preferences": "preferences",
}


def migrate_mainmemory(
    mainmemory_path: Path,
    memory_dir: Path,
    store: MemoryStore,
) -> bool:
    """Migrate existing MAINMEMORY.md to hierarchical structure.

    Returns True if migration was performed, False if skipped.
    """
    # Already migrated
    user_dir = memory_dir / "user"
    if user_dir.exists() and (user_dir / "profile.md").exists():
        logger.info("Migration skipped: user/profile.md already exists")
        return False

    if not mainmemory_path.exists():
        return False

    text = mainmemory_path.read_text(encoding="utf-8")
    sections = _extract_sections(text)

    # Check if all sections are empty
    has_content = False
    for heading, body in sections.items():
        if not _is_empty_section(body):
            has_content = True
            break

    if not has_content:
        logger.info("Migration skipped: MAINMEMORY.md is empty/default")
        return False

    mgr = MemoryFileManager(memory_dir, store)

    for heading, body in sections.items():
        if _is_empty_section(body):
            continue

        category = _SECTION_MAP.get(heading, "entities")
        slug = "main" if category == "profile" else re.sub(r"[^\w]+", "-", heading.lower()).strip("-")
        abstract = body[:80].replace("\n", " ").strip()

        mgr.write(MemoryFile(
            category=category,
            slug=slug,
            abstract=abstract,
            content=body,
        ))

    # Backup original
    backup = mainmemory_path.with_suffix(".md.bak")
    mainmemory_path.rename(backup)
    logger.info("Migrated MAINMEMORY.md → hierarchical structure (backup: %s)", backup.name)
    return True
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/memory/test_migrate.py -v`
Expected: All 3 tests PASS

**Step 5: Update RULES.md template**

Update `klir/_home_defaults/workspace/memory_system/RULES.md`:

```markdown
# Memory System

Long-term memory organized into categories under `memory_system/`.

## Directory Structure

- `user/profile.md` — About the user (always loaded on new sessions)
- `user/preferences/` — Tools, styles, approaches the user prefers
- `user/entities/` — Projects, repos, teams, services
- `user/events/` — Specific incidents, decisions with dates
- `agent/cases/` — Problem+solution pairs
- `agent/patterns/` — Reusable workflows and conventions

## Memory File Format

Every memory file uses frontmatter:

```
---
abstract: One-line summary
category: profile|preferences|entities|events|cases|patterns
---

Detailed content here.
```

## Silence Is Mandatory

Never tell the user you are reading or writing memory.
Memory operations are invisible.

## When to Write

- Durable personal facts or preferences
- Decisions that should affect future behavior
- User explicitly asks to remember
- Repeating workflow patterns
- Problem+solution pairs worth remembering

## When Not to Write

- One-off throwaway requests
- Temporary debugging noise
- Facts already recorded

## Format Rules

- Keep entries short and actionable
- One memory per file
- Use descriptive filenames (e.g., `testing-preferences.md`)
- Merge duplicates; remove stale facts

## Shared Knowledge (SHAREDMEMORY.md)

When you learn something relevant to ALL agents, update shared knowledge:

```bash
python3 tools/agent_tools/edit_shared_knowledge.py --append "New shared fact"
```

## Cleanup Rules

- If user says data is wrong or should be forgotten, remove/update immediately
- Do not leave "deleted" markers; keep files clean
```

**Step 6: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests pass

**Step 7: Commit**

```bash
git add klir/memory/migrate.py klir/_home_defaults/workspace/memory_system/RULES.md tests/memory/test_migrate.py
git commit -m "feat(memory): Add migration from flat MAINMEMORY.md and update RULES template"
```

---

## Task 8: Integration Test — End-to-End Memory Flow

**Files:**
- Create: `tests/memory/test_integration.py`

Full round-trip test: write memories → search → retrieve → inject into prompt.

**Step 1: Write the integration test**

```python
# tests/memory/test_integration.py
"""Integration test: full memory lifecycle."""

from __future__ import annotations

import pytest
from pathlib import Path

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


def test_full_lifecycle(setup: tuple) -> None:
    """Write → search → retrieve → inject → extract cycle."""
    store, mgr = setup

    # Phase 1: Seed initial memories
    mgr.write(MemoryFile(
        category="profile", slug="main",
        abstract="Backend engineer specializing in Python APIs",
        content="10 years exp. FastAPI, Django, asyncio.",
    ))
    mgr.write(MemoryFile(
        category="preferences", slug="testing",
        abstract="Strict pytest with real database integration tests",
        content="No mocking. Use test containers. 100% coverage target.",
    ))
    mgr.write(MemoryFile(
        category="cases", slug="redis-timeout",
        abstract="Fixed Redis connection timeout in production",
        content="Root cause: connection pool exhaustion. Fix: increase pool size and add health checks.",
    ))

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
    mgr.write(MemoryFile(
        category=c.category, slug=c.slug,
        abstract=c.abstract, content=c.content,
    ))
    assert store.count() == 4  # 3 original + 1 extracted

    # Phase 6: New search finds the extracted memory
    results2 = store.search("FastAPI Pydantic")
    assert any("fastapi" in r.abstract.lower() or "pydantic" in r.abstract.lower() for r in results2)


def test_rebuild_preserves_search(setup: tuple) -> None:
    """Rebuilding the index from disk preserves searchability."""
    store, mgr = setup

    mgr.write(MemoryFile(
        category="patterns", slug="deploy-flow",
        abstract="Always run migrations before deploying",
        content="1. Run alembic upgrade head\n2. Deploy\n3. Verify health check.",
    ))

    # Rebuild index from scratch
    mgr.rebuild_index()

    results = store.search("deploy migration")
    assert len(results) >= 1
    assert "deploy" in results[0].abstract.lower()
```

**Step 2: Run integration test**

Run: `uv run pytest tests/memory/test_integration.py -v`
Expected: All 2 tests PASS

**Step 3: Commit**

```bash
git add tests/memory/test_integration.py
git commit -m "test(memory): Add end-to-end integration test for memory lifecycle"
```

---

## Task 9: Quality Pass — Ruff, Mypy, Full Suite

**Files:**
- All `klir/memory/*.py` files
- All `tests/memory/*.py` files

**Step 1: Run ruff**

Run: `uv run ruff check klir/memory/ tests/memory/`
Fix any lint issues.

**Step 2: Run ruff format**

Run: `uv run ruff format klir/memory/ tests/memory/`

**Step 3: Run mypy**

Run: `uv run mypy klir/memory/`
Fix any type errors (likely around sqlite3 return types and optional handling).

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests pass, including existing tests.

**Step 5: Commit**

```bash
git add klir/memory/ tests/memory/
git commit -m "style(memory): Fix lint and type issues"
```

---

## Summary

| Task | What it builds | New files | Tests |
|------|---------------|-----------|-------|
| 1 | SQLite FTS5 store with BM25 search | `klir/memory/store.py` | 9 |
| 2 | File manager for hierarchical layout | `klir/memory/files.py` | 7 |
| 3 | Wire into KlirPaths + Orchestrator | Modified: `paths.py`, `core.py` | 1 |
| 4 | Retrieval hook with prompt injection | `klir/memory/hooks.py` | 4 |
| 5 | Extraction parser for LLM responses | `klir/memory/extractor.py` | 4 |
| 6 | Extraction observer for stale sessions | `klir/memory/observer.py` | 2 |
| 7 | Migration + updated RULES.md | `klir/memory/migrate.py` | 3 |
| 8 | Integration test | `tests/memory/test_integration.py` | 2 |
| 9 | Quality pass (ruff, mypy) | — | — |

**Total: 9 tasks, ~8 new files, ~32 tests, 0 new dependencies**

### Future Upgrade Path (Not in This Plan)

When memory count exceeds ~200 and BM25 quality degrades:

1. Add `klir/memory/embedding_store.py` implementing the same `search()` interface
2. Add `openai` or `httpx` call to an embedding API
3. Swap `MemoryStore.search()` to use embeddings instead of FTS5
4. Everything else (files, hooks, extraction, observer) stays unchanged

The abstraction boundary is `MemoryStore.search()` — that's the only function that needs to change.
