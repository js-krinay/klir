"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _no_real_process_signals() -> object:
    """Globally prevent tests from sending real signals to system processes.

    Multiple modules import process_tree helpers that send real OS signals.
    Mock processes carry arbitrary PIDs (e.g. 1, 10) that correspond to real
    system processes — sending signals to them crashes the desktop session.
    """
    with (
        patch(
            "klir.cli.process_registry.terminate_process_tree",
            return_value=None,
        ),
        patch(
            "klir.cli.process_registry.force_kill_process_tree",
            return_value=None,
        ),
        patch(
            "klir.cli.executor.force_kill_process_tree",
            return_value=None,
        ),
        patch(
            "klir.cli.gemini_provider.force_kill_process_tree",
            return_value=None,
        ),
        patch(
            "klir.cron.execution.force_kill_process_tree",
            return_value=None,
        ),
        patch(
            "klir.infra.pidlock.terminate_process_tree",
            return_value=None,
        ),
        patch(
            "klir.infra.pidlock.force_kill_process_tree",
            return_value=None,
        ),
        patch(
            "klir.infra.pidlock.list_process_descendants",
            return_value=[],
        ),
    ):
        yield


@pytest.fixture
def tmp_klir_home(tmp_path: Path) -> Path:
    """Temporary ~/.klir equivalent."""
    home = tmp_path / ".klir"
    home.mkdir()
    return home


@pytest.fixture
def tmp_workspace(tmp_klir_home: Path) -> Path:
    """Temporary workspace directory."""
    ws = tmp_klir_home / "workspace"
    ws.mkdir()
    return ws
