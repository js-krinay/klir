"""Tests for reply_to_mode threading through dispatch."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ductor_bot.bot.message_dispatch import (
    NonStreamingDispatch,
    StreamingDispatch,
    run_non_streaming_message,
    run_streaming_message,
)
from ductor_bot.session.key import SessionKey


def _make_key() -> SessionKey:
    return SessionKey(chat_id=1)


class TestNonStreamingDispatchReplyToMode:
    async def test_default_reply_to_mode_is_first(self) -> None:
        d = NonStreamingDispatch(
            bot=MagicMock(),
            orchestrator=MagicMock(),
            key=_make_key(),
            text="hi",
            allowed_roots=None,
        )
        assert d.reply_to_mode == "first"

    async def test_mode_off_passed_to_send_rich(self) -> None:
        bot = MagicMock()
        bot.send_chat_action = AsyncMock()
        orch = MagicMock()
        result = MagicMock()
        result.text = "response"
        orch.handle_message = AsyncMock(return_value=result)
        reply_msg = MagicMock()
        reply_msg.message_id = 42

        d = NonStreamingDispatch(
            bot=bot,
            orchestrator=orch,
            key=_make_key(),
            text="hi",
            allowed_roots=None,
            reply_to=reply_msg,
            reply_to_mode="off",
        )

        with patch("ductor_bot.bot.message_dispatch.send_rich", new_callable=AsyncMock) as mock_sr:
            await run_non_streaming_message(d)
            opts = mock_sr.call_args.args[3]
            assert opts.reply_to_mode == "off"


class TestStreamingDispatchReplyToMode:
    async def test_default_reply_to_mode_is_first(self) -> None:
        from ductor_bot.config import StreamingConfig

        d = StreamingDispatch(
            bot=MagicMock(),
            orchestrator=MagicMock(),
            message=MagicMock(),
            key=_make_key(),
            text="hi",
            streaming_cfg=StreamingConfig(),
            allowed_roots=None,
        )
        assert d.reply_to_mode == "first"

    async def test_mode_all_passed_to_stream_editor(self) -> None:
        from ductor_bot.config import StreamingConfig

        bot = MagicMock()
        bot.send_chat_action = AsyncMock()
        orch = MagicMock()
        result = MagicMock()
        result.text = "response"
        result.stream_fallback = False
        orch.handle_message_streaming = AsyncMock(return_value=result)

        msg = MagicMock()
        msg.message_id = 42

        d = StreamingDispatch(
            bot=bot,
            orchestrator=orch,
            message=msg,
            key=_make_key(),
            text="hi",
            streaming_cfg=StreamingConfig(),
            allowed_roots=None,
            reply_to_mode="all",
        )

        with patch("ductor_bot.bot.message_dispatch.create_stream_editor") as mock_cse:
            mock_editor = MagicMock()
            mock_editor.has_content = True
            mock_editor.append_text = AsyncMock()
            mock_editor.finalize = AsyncMock()
            mock_cse.return_value = mock_editor

            await run_streaming_message(d)
            assert mock_cse.call_args.kwargs["reply_to_mode"] == "all"
