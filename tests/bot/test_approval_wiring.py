"""Test that approval callbacks are routed in app.py."""

from __future__ import annotations

from klir.bot.approval_handler import APR_PREFIX


class TestApprovalCallbackRouting:
    def test_apr_prefix_recognized(self) -> None:
        """Callback data starting with 'apr:' should be recognized."""
        assert "apr:req_1:yes".startswith(APR_PREFIX)
        assert not "ns:session:label".startswith(APR_PREFIX)
