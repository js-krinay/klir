"""Tests for ThreadBindingConfig."""

from __future__ import annotations


class TestThreadBindingConfig:
    def test_default_idle_timeout(self) -> None:
        from klir.config import ThreadBindingConfig

        cfg = ThreadBindingConfig()
        assert cfg.idle_timeout_minutes == 60

    def test_default_max_age(self) -> None:
        from klir.config import ThreadBindingConfig

        cfg = ThreadBindingConfig()
        assert cfg.max_age_minutes == 1440

    def test_default_cleanup_interval(self) -> None:
        from klir.config import ThreadBindingConfig

        cfg = ThreadBindingConfig()
        assert cfg.cleanup_interval_minutes == 15

    def test_default_enabled(self) -> None:
        from klir.config import ThreadBindingConfig

        cfg = ThreadBindingConfig()
        assert cfg.enabled is True

    def test_agent_config_includes_thread_binding(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig()
        assert cfg.thread_binding.enabled is True
        assert cfg.thread_binding.idle_timeout_minutes == 60

    def test_custom_values(self) -> None:
        from klir.config import ThreadBindingConfig

        cfg = ThreadBindingConfig(idle_timeout_minutes=30, max_age_minutes=720)
        assert cfg.idle_timeout_minutes == 30
        assert cfg.max_age_minutes == 720

    def test_disabled(self) -> None:
        from klir.config import ThreadBindingConfig

        cfg = ThreadBindingConfig(enabled=False)
        assert cfg.enabled is False
