"""Tests for approval inline button handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


class TestApprovalHandler:
    async def test_send_approval_request_sends_to_approvers(self) -> None:
        from klir.bot.approval_handler import send_approval_request

        bot = AsyncMock()
        bot.send_message.return_value = MagicMock(message_id=99)

        await send_approval_request(
            bot=bot,
            approver_ids=[100, 200],
            request_id="apr_1",
            tool_name="Write",
            chat_id=42,
            parameters={"path": "/tmp/test.py"},
        )

        assert bot.send_message.call_count == 2
        call_kwargs = bot.send_message.call_args_list[0].kwargs
        assert call_kwargs["chat_id"] == 100
        assert call_kwargs["reply_markup"] is not None

    async def test_approval_message_contains_tool_info(self) -> None:
        from klir.bot.approval_handler import send_approval_request

        bot = AsyncMock()
        bot.send_message.return_value = MagicMock(message_id=99)

        await send_approval_request(
            bot=bot,
            approver_ids=[100],
            request_id="apr_1",
            tool_name="Bash",
            chat_id=42,
            parameters={"command": "rm -rf /"},
        )

        call_kwargs = bot.send_message.call_args.kwargs
        text = call_kwargs["text"]
        assert "Bash" in text
        assert "apr_1" in text or "rm -rf" in text

    async def test_handle_approval_callback_resolves(self) -> None:
        from klir.bot.approval_handler import handle_approval_callback

        svc = MagicMock()
        svc.resolve.return_value = True

        bot = AsyncMock()
        result = await handle_approval_callback(
            bot=bot,
            svc=svc,
            callback_data="apr:apr_1:yes",
            chat_id=100,
            message_id=99,
        )

        svc.resolve.assert_called_once_with("apr_1", approved=True)
        assert result is True

    async def test_handle_denial_callback(self) -> None:
        from klir.bot.approval_handler import handle_approval_callback

        svc = MagicMock()
        svc.resolve.return_value = True

        bot = AsyncMock()
        await handle_approval_callback(
            bot=bot,
            svc=svc,
            callback_data="apr:apr_1:no",
            chat_id=100,
            message_id=99,
        )

        svc.resolve.assert_called_once_with("apr_1", approved=False)

    async def test_parse_approval_callback(self) -> None:
        from klir.bot.approval_handler import parse_approval_callback

        assert parse_approval_callback("apr:apr_1:yes") == ("apr_1", True)
        assert parse_approval_callback("apr:apr_1:no") == ("apr_1", False)
        assert parse_approval_callback("other:data") is None
