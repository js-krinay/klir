"""Tests for KlirPaths and resolve_paths."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from klir.workspace.paths import KlirPaths, resolve_paths


def test_workspace_property() -> None:
    paths = KlirPaths(
        klir_home=Path("/home/test/.klir"),
        home_defaults=Path("/opt/klir/workspace"),
        framework_root=Path("/opt/klir"),
    )
    assert paths.workspace == Path("/home/test/.klir/workspace")


def test_config_path() -> None:
    paths = KlirPaths(
        klir_home=Path("/home/test/.klir"),
        home_defaults=Path("/opt/klir/workspace"),
        framework_root=Path("/opt/klir"),
    )
    assert paths.config_path == Path("/home/test/.klir/config/config.json")


def test_sessions_path() -> None:
    paths = KlirPaths(
        klir_home=Path("/home/test/.klir"),
        home_defaults=Path("/opt/klir/workspace"),
        framework_root=Path("/opt/klir"),
    )
    assert paths.sessions_path == Path("/home/test/.klir/sessions.json")


def test_logs_dir() -> None:
    paths = KlirPaths(
        klir_home=Path("/home/test/.klir"),
        home_defaults=Path("/opt/klir/workspace"),
        framework_root=Path("/opt/klir"),
    )
    assert paths.logs_dir == Path("/home/test/.klir/logs")


def test_home_defaults() -> None:
    paths = KlirPaths(
        klir_home=Path("/x"),
        home_defaults=Path("/opt/klir/workspace"),
        framework_root=Path("/opt/klir"),
    )
    assert paths.home_defaults == Path("/opt/klir/workspace")


def test_resolve_paths_explicit() -> None:
    paths = resolve_paths(klir_home="/tmp/test_home", framework_root="/tmp/test_fw")
    assert paths.klir_home == Path("/tmp/test_home").resolve()
    assert paths.framework_root == Path("/tmp/test_fw").resolve()


def test_resolve_paths_env_vars() -> None:
    with patch.dict(
        os.environ, {"KLIR_HOME": "/tmp/env_home", "KLIR_FRAMEWORK_ROOT": "/tmp/env_fw"}
    ):
        paths = resolve_paths()
        assert paths.klir_home == Path("/tmp/env_home").resolve()
        assert paths.framework_root == Path("/tmp/env_fw").resolve()


def test_resolve_paths_defaults() -> None:
    with patch.dict(os.environ, {}, clear=True):
        env_clean = {
            k: v for k, v in os.environ.items() if k not in ("KLIR_HOME", "KLIR_FRAMEWORK_ROOT")
        }
        with patch.dict(os.environ, env_clean, clear=True):
            paths = resolve_paths()
            assert paths.klir_home == (Path.home() / ".klir").resolve()
