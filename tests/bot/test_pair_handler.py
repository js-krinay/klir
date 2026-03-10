"""Tests for /pair command handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def _make_message(user_id: int = 100, chat_type: str = "private") -> MagicMock:
    msg = MagicMock()
    msg.chat = MagicMock()
    msg.chat.id = user_id
    msg.chat.type = chat_type
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.message_id = 1
    msg.reply = AsyncMock()
    return msg


class TestPairHandler:
    async def test_pair_generates_code(self) -> None:
        from ductor_bot.bot.pair_handler import handle_pair

        pairing_svc = MagicMock()
        pairing_svc.generate_code.return_value = "ABC123"
        pairing_svc._cfg.code_ttl_minutes = 60

        msg = _make_message(user_id=100)
        await handle_pair(msg, pairing_svc)

        pairing_svc.generate_code.assert_called_once_with(admin_user_id=100)
        msg.reply.assert_called_once()
        reply_text = msg.reply.call_args[0][0]
        assert "ABC123" in reply_text

    async def test_pair_only_in_private(self) -> None:
        from ductor_bot.bot.pair_handler import handle_pair

        pairing_svc = MagicMock()
        msg = _make_message(user_id=100, chat_type="supergroup")

        await handle_pair(msg, pairing_svc)

        pairing_svc.generate_code.assert_not_called()
        msg.reply.assert_called_once()
        reply_text = msg.reply.call_args[0][0]
        assert "private" in reply_text.lower() or "DM" in reply_text

    async def test_pair_max_codes_reached(self) -> None:
        from ductor_bot.bot.pair_handler import handle_pair

        pairing_svc = MagicMock()
        pairing_svc.generate_code.return_value = None

        msg = _make_message(user_id=100)
        await handle_pair(msg, pairing_svc)

        msg.reply.assert_called_once()
        reply_text = msg.reply.call_args[0][0]
        assert "Maximum" in reply_text

    async def test_pair_shows_custom_ttl(self) -> None:
        from ductor_bot.bot.pair_handler import handle_pair

        pairing_svc = MagicMock()
        pairing_svc.generate_code.return_value = "XYZ789"
        pairing_svc._cfg.code_ttl_minutes = 30

        msg = _make_message(user_id=100)
        await handle_pair(msg, pairing_svc)

        reply_text = msg.reply.call_args[0][0]
        assert "30 minutes" in reply_text
