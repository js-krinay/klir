"""Test that MemoryStore is wired into the orchestrator."""

from __future__ import annotations

from pathlib import Path

from klir.workspace.paths import KlirPaths


def test_memory_index_path() -> None:
    """KlirPaths exposes memory_index_path."""
    paths = KlirPaths(klir_home=Path("/tmp/test-klir"))
    assert paths.memory_index_path == Path("/tmp/test-klir/workspace/memory_system/index.db")
