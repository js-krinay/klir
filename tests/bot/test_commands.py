"""Tests for command definitions and scoped lists."""

from __future__ import annotations


class TestCommandLists:
    def test_bot_commands_has_entries(self) -> None:
        from klir.commands import BOT_COMMANDS

        assert len(BOT_COMMANDS) > 0
        assert all(len(t) == 2 for t in BOT_COMMANDS)

    def test_group_commands_is_subset_of_bot_commands(self) -> None:
        from klir.commands import BOT_COMMANDS, GROUP_COMMANDS

        bot_cmds = {t[0] for t in BOT_COMMANDS}
        group_cmds = {t[0] for t in GROUP_COMMANDS}
        assert group_cmds.issubset(bot_cmds)

    def test_group_commands_excludes_admin(self) -> None:
        from klir.commands import GROUP_COMMANDS

        group_cmds = {t[0] for t in GROUP_COMMANDS}
        # Admin/maintenance commands should NOT appear in groups
        for cmd in ("restart", "upgrade", "diagnose"):
            assert cmd not in group_cmds

    def test_group_commands_includes_daily(self) -> None:
        from klir.commands import GROUP_COMMANDS

        group_cmds = {t[0] for t in GROUP_COMMANDS}
        for cmd in ("new", "stop", "model", "status", "help"):
            assert cmd in group_cmds

    def test_private_commands_count(self) -> None:
        """Private chats should show all commands."""
        from klir.commands import BOT_COMMANDS

        # Currently 15 commands — this ensures we don't accidentally drop any
        assert len(BOT_COMMANDS) >= 14

    def test_descriptions_not_truncated(self) -> None:
        """Telegram truncates command descriptions beyond 256 chars."""
        from klir.commands import BOT_COMMANDS, GROUP_COMMANDS

        for cmd, desc in BOT_COMMANDS + GROUP_COMMANDS:
            assert len(desc) <= 256, f"/{cmd} description too long: {len(desc)}"
