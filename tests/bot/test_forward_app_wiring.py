"""Tests for forwarding config wiring in app dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from klir.config import AgentConfig, ForwardingConfig


class TestForwardAppWiring:
    def test_streaming_dispatch_receives_forwarding_config(self) -> None:
        """Verify StreamingDispatch dataclass accepts forwarding fields."""
        from klir.bot.message_dispatch import StreamingDispatch

        cfg = AgentConfig(
            forwarding=ForwardingConfig(enabled=True),
            allowed_user_ids=[100],
            allowed_group_ids=[-200],
        )
        dispatch = StreamingDispatch(
            bot=MagicMock(),
            orchestrator=MagicMock(),
            message=MagicMock(),
            key=MagicMock(),
            text="test",
            streaming_cfg=cfg.streaming,
            allowed_roots=None,
            forwarding_enabled=cfg.forwarding.enabled,
            forwarding_targets=cfg.allowed_forward_targets,
        )
        assert dispatch.forwarding_enabled is True
        assert dispatch.forwarding_targets == {100, -200}

    def test_non_streaming_dispatch_receives_forwarding_config(self) -> None:
        """Verify NonStreamingDispatch dataclass accepts forwarding fields."""
        from klir.bot.message_dispatch import NonStreamingDispatch

        cfg = AgentConfig(
            forwarding=ForwardingConfig(enabled=True),
            allowed_channel_ids=[-300],
        )
        dispatch = NonStreamingDispatch(
            bot=MagicMock(),
            orchestrator=MagicMock(),
            key=MagicMock(),
            text="test",
            allowed_roots=None,
            forwarding_enabled=cfg.forwarding.enabled,
            forwarding_targets=cfg.allowed_forward_targets,
        )
        assert dispatch.forwarding_enabled is True
        assert dispatch.forwarding_targets == {-300}
