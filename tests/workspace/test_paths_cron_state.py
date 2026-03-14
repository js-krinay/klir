from pathlib import Path

from klir.workspace.paths import KlirPaths


def test_cron_state_dir(tmp_path: Path) -> None:
    paths = KlirPaths(klir_home=tmp_path / "home")
    assert paths.cron_state_dir == tmp_path / "home" / "cron-state"


def test_cron_job_state_dir(tmp_path: Path) -> None:
    paths = KlirPaths(klir_home=tmp_path / "home")
    assert paths.cron_job_state_dir("daily") == tmp_path / "home" / "cron-state" / "daily"
