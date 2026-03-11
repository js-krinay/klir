"""Tests for persisting paired users to config.json."""

from __future__ import annotations

import json
from pathlib import Path


class TestPairingPersistence:
    async def test_paired_user_added_to_config(self, tmp_path: Path) -> None:
        """When a user pairs, their ID should be persisted to config.json."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "telegram_token": "test:token",
            "allowed_user_ids": [100],
        }))

        from klir.config import update_config_file

        # Simulate what the on_paired callback does
        data = json.loads(config_path.read_text())
        allowed = data.get("allowed_user_ids", [])
        if 999 not in allowed:
            allowed.append(999)
            update_config_file(config_path, allowed_user_ids=allowed)

        result = json.loads(config_path.read_text())
        assert 999 in result["allowed_user_ids"]
        assert 100 in result["allowed_user_ids"]
