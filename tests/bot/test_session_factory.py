"""Tests for Bot session factory with proxy support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestSessionFactory:
    def test_no_proxy_returns_none(self) -> None:
        from klir.bot.session_factory import create_bot_session

        result = create_bot_session(proxy_url=None)
        assert result is None

    def test_with_proxy_returns_session(self) -> None:
        from klir.bot.session_factory import create_bot_session

        with patch("klir.bot.session_factory.AiohttpSession") as MockSession:
            mock_instance = MagicMock()
            MockSession.return_value = mock_instance

            result = create_bot_session(proxy_url="http://proxy:8080")
            assert result is mock_instance
            MockSession.assert_called_once_with(proxy="http://proxy:8080")
