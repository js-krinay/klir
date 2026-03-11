"""Bot startup lifecycle: orchestrator creation, recovery, sentinel handling."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from klir.bot.sender import SendRichOpts, send_rich
from klir.infra.restart import consume_restart_sentinel
from klir.infra.updater import UpdateObserver, consume_upgrade_sentinel
from klir.infra.version import get_current_version

if TYPE_CHECKING:
    from klir.bot.app import TelegramBot

logger = logging.getLogger(__name__)


async def _handle_restart_sentinel(bot: TelegramBot) -> dict[str, object] | None:
    """Consume and handle the restart sentinel file. Returns sentinel dict or None."""
    sentinel_path = bot._orch.paths.klir_home / "restart-sentinel.json"
    sentinel = await asyncio.to_thread(consume_restart_sentinel, sentinel_path=sentinel_path)
    if sentinel:
        chat_id = int(sentinel.get("chat_id", 0))
        msg = str(sentinel.get("message", "Restart completed."))
        if chat_id:
            await send_rich(
                bot.bot_instance,
                chat_id,
                msg,
                SendRichOpts(allowed_roots=bot.file_roots(bot._orch.paths)),
            )
    return sentinel


async def run_startup(bot: TelegramBot) -> None:
    """Execute full startup sequence: orchestrator, sentinels, recovery, update observer."""
    from klir.orchestrator.core import Orchestrator

    bot._orchestrator = await Orchestrator.create(
        bot.config,
        agent_name=bot._agent_name,
    )

    from klir.bot.chat_tracker import ChatTracker

    bot._chat_tracker = ChatTracker(bot._orch.paths.chat_activity_path)

    # Seed topic name cache from persisted sessions and wire the resolver.
    all_sessions = await bot._orch._sessions.list_all()
    seeded = bot._topic_names.seed_from_sessions(all_sessions)
    if seeded:
        logger.info("Topic name cache seeded with %d name(s)", seeded)
    bot._orch._sessions.set_topic_name_resolver(bot._topic_names.resolve)

    me = await bot.bot_instance.get_me()
    bot._bot_id = me.id
    bot._bot_username = (me.username or "").lower()
    bot._sequential.set_bot_username(bot._bot_username)
    logger.info("Bot online: @%s (id=%d)", me.username, me.id)

    if bot._proxy_url:
        from klir.infra.proxy import sanitize_proxy_url

        logger.info("Telegram API connected via proxy: %s", sanitize_proxy_url(bot._proxy_url))

    sentinel = await _handle_restart_sentinel(bot)

    bot._orch.wire_observers_to_bus(bot._bus, wake_handler=bot._handle_webhook_wake)
    bot._orchestrator.set_config_hot_reload_handler(bot._on_auth_hot_reload)

    # Check for post-upgrade notification
    upgrade = await asyncio.to_thread(consume_upgrade_sentinel, bot._orch.paths.klir_home)
    if upgrade:
        uid = int(upgrade.get("chat_id", 0))
        old_v = upgrade.get("old_version", "?")
        new_v = upgrade.get("new_version", get_current_version())
        if uid:
            await send_rich(
                bot.bot_instance,
                uid,
                f"**Upgrade complete** `{old_v}` -> `{new_v}`",
                SendRichOpts(
                    allowed_roots=bot.file_roots(bot._orch.paths),
                ),
            )

    # -- Startup lifecycle detection --
    from klir.infra.startup_state import detect_startup_kind, save_startup_state
    from klir.text.response_format import startup_notification_text

    startup_info = await asyncio.to_thread(detect_startup_kind, bot._orch.paths.startup_state_path)
    await asyncio.to_thread(save_startup_state, bot._orch.paths.startup_state_path, startup_info)
    if sentinel is None and startup_info.kind.value != "service_restart":
        note = startup_notification_text(startup_info.kind.value)
        if note:
            await bot.broadcast(note, SendRichOpts(allowed_roots=bot.file_roots(bot._orch.paths)))

    # -- Auto-recovery of interrupted work --
    from klir.infra.recovery import RecoveryPlanner
    from klir.text.response_format import recovery_notification_text

    planner = RecoveryPlanner(
        inflight=bot._orch.inflight_tracker,
        named_sessions=bot._orch.named_sessions.pop_recovered_running(),
        max_age_seconds=bot.config.timeouts.normal * 2,
    )
    for action in planner.plan():
        note = recovery_notification_text(action.kind, action.prompt_preview, action.session_name)
        await send_rich(
            bot.bot_instance,
            action.chat_id,
            note,
            SendRichOpts(allowed_roots=bot.file_roots(bot._orch.paths)),
        )
        if action.kind == "named_session" and action.session_name:
            with contextlib.suppress(Exception):
                bot._orch.submit_named_followup_bg(
                    action.chat_id,
                    action.session_name,
                    action.prompt_preview,
                    message_id=0,
                    thread_id=None,
                )
    bot._orch.inflight_tracker.clear()

    # Start background version checker (skip for dev/source installs)
    from klir.infra.install import is_upgradeable

    if is_upgradeable() and bot.config.update_check:
        bot._update_observer = UpdateObserver(notify=bot._on_update_available)
        bot._update_observer.start()

    await bot._sync_commands()
    bot._restart_watcher = asyncio.create_task(bot._watch_restart_marker())

    # Audit groups on startup and start periodic 24h check
    await bot.audit_groups()
    bot._group_audit_task = asyncio.create_task(bot._run_group_audit_loop())

    await bot._binding_cleanup.start()
