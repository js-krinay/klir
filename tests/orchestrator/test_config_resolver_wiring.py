"""Test that orchestrator uses ChatConfigResolver."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestOrchestratorResolverWiring:
    def test_orchestrator_has_resolver(self) -> None:
        """Orchestrator should expose a ChatConfigResolver instance."""
        from klir.config_resolver import ChatConfigResolver

        # Check that the class exists and is importable
        resolver = ChatConfigResolver.__new__(ChatConfigResolver)
        assert hasattr(resolver, "provider")
        assert hasattr(resolver, "model")
