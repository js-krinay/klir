"""Tests for proxy URL resolution."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestProxyResolution:
    def test_config_url_takes_priority(self) -> None:
        from klir.infra.proxy import resolve_proxy_url

        cfg = MagicMock()
        cfg.proxy.url = "http://config-proxy:8080"
        cfg.proxy.is_configured = True

        result = resolve_proxy_url(cfg)
        assert result == "http://config-proxy:8080"

    def test_env_https_proxy_fallback(self) -> None:
        from klir.infra.proxy import resolve_proxy_url

        cfg = MagicMock()
        cfg.proxy.url = ""
        cfg.proxy.is_configured = False

        with patch.dict(os.environ, {"HTTPS_PROXY": "http://env-proxy:3128"}):
            result = resolve_proxy_url(cfg)
            assert result == "http://env-proxy:3128"

    def test_env_http_proxy_fallback(self) -> None:
        from klir.infra.proxy import resolve_proxy_url

        cfg = MagicMock()
        cfg.proxy.url = ""
        cfg.proxy.is_configured = False

        with patch.dict(os.environ, {"HTTP_PROXY": "http://env-proxy:3128"}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "HTTPS_PROXY"}
            with patch.dict(os.environ, env, clear=True):
                result = resolve_proxy_url(cfg)
                assert result == "http://env-proxy:3128"

    def test_no_proxy_returns_none(self) -> None:
        from klir.infra.proxy import resolve_proxy_url

        cfg = MagicMock()
        cfg.proxy.url = ""
        cfg.proxy.is_configured = False

        with patch.dict(os.environ, {}, clear=True):
            result = resolve_proxy_url(cfg)
            assert result is None

    def test_sanitize_strips_credentials(self) -> None:
        from klir.infra.proxy import sanitize_proxy_url

        assert sanitize_proxy_url("http://user:pass@proxy:8080") == "http://***@proxy:8080"

    def test_sanitize_preserves_url_without_credentials(self) -> None:
        from klir.infra.proxy import sanitize_proxy_url

        assert sanitize_proxy_url("http://proxy:8080") == "http://proxy:8080"

    def test_lowercase_env_vars(self) -> None:
        from klir.infra.proxy import resolve_proxy_url

        cfg = MagicMock()
        cfg.proxy.url = ""
        cfg.proxy.is_configured = False

        with patch.dict(os.environ, {"https_proxy": "http://lower:8080"}, clear=True):
            result = resolve_proxy_url(cfg)
            assert result == "http://lower:8080"
