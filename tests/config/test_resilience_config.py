"""Tests for ResilienceConfig."""

from __future__ import annotations


class TestResilienceConfig:
    def test_defaults(self) -> None:
        from klir.config import ResilienceConfig

        cfg = ResilienceConfig()
        assert cfg.max_retries == 3
        assert cfg.base_backoff_seconds == 1.0
        assert cfg.max_backoff_seconds == 30.0
        assert cfg.jitter is True

    def test_custom_values(self) -> None:
        from klir.config import ResilienceConfig

        cfg = ResilienceConfig(
            max_retries=5,
            base_backoff_seconds=2.0,
            max_backoff_seconds=60.0,
            jitter=False,
        )
        assert cfg.max_retries == 5
        assert cfg.base_backoff_seconds == 2.0
        assert cfg.max_backoff_seconds == 60.0
        assert cfg.jitter is False

    def test_agent_config_includes_resilience(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.resilience.max_retries == 3

    def test_agent_config_custom_resilience(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(
            telegram_token="test:token",
            resilience={"max_retries": 5, "base_backoff_seconds": 2.0},  # type: ignore[arg-type]
        )
        assert cfg.resilience.max_retries == 5
        assert cfg.resilience.base_backoff_seconds == 2.0
