"""Tests for ProxyConfig."""

from __future__ import annotations

import pytest


class TestProxyConfig:
    def test_default_empty(self) -> None:
        from klir.config import ProxyConfig

        cfg = ProxyConfig()
        assert cfg.url == ""

    def test_set_proxy_url(self) -> None:
        from klir.config import ProxyConfig

        cfg = ProxyConfig(url="http://proxy.example.com:8080")
        assert cfg.url == "http://proxy.example.com:8080"

    def test_socks5_proxy(self) -> None:
        from klir.config import ProxyConfig

        cfg = ProxyConfig(url="socks5://localhost:1080")
        assert cfg.url == "socks5://localhost:1080"

    def test_agent_config_includes_proxy(self) -> None:
        from klir.config import AgentConfig

        cfg = AgentConfig(telegram_token="test:token")
        assert cfg.proxy.url == ""

    def test_is_configured_false_when_empty(self) -> None:
        from klir.config import ProxyConfig

        cfg = ProxyConfig()
        assert cfg.is_configured is False

    def test_is_configured_true_when_set(self) -> None:
        from klir.config import ProxyConfig

        cfg = ProxyConfig(url="http://proxy:8080")
        assert cfg.is_configured is True
