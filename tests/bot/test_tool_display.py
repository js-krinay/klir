"""Tests for ToolActivity dataclass and display formatting."""

from __future__ import annotations

from klir.cli.stream_events import ToolUseEvent
from klir.cli.tool_activity import ToolActivity


class TestDisplayLabel:
    def test_display_name_only(self) -> None:
        activity = ToolActivity(name="Bash")
        assert activity.display_label() == "Bash"

    def test_display_with_file_path(self) -> None:
        activity = ToolActivity(name="Read", file_path="/home/user/project/src/main.py")
        assert activity.display_label() == "Read: /home/user/project/src/main.py"

    def test_display_with_command(self) -> None:
        activity = ToolActivity(name="Bash", command="ls -la")
        assert activity.display_label() == "Bash: ls -la"

    def test_display_truncates_long_command(self) -> None:
        long_cmd = "x" * 200
        activity = ToolActivity(name="Bash", command=long_cmd)
        label = activity.display_label()
        # Name + ": " + truncated detail
        detail = label.removeprefix("Bash: ")
        assert len(detail) <= 100
        assert detail.endswith("\u2026")

    def test_display_with_edit_file(self) -> None:
        activity = ToolActivity(name="Edit", file_path="/home/user/project/config.yaml")
        assert activity.display_label() == "Edit: /home/user/project/config.yaml"

    def test_file_path_preferred_over_command(self) -> None:
        activity = ToolActivity(name="Bash", file_path="/some/path.py", command="echo hello")
        assert activity.display_label() == "Bash: /some/path.py"


class TestFromEvent:
    def test_from_tool_use_event_read(self) -> None:
        event = ToolUseEvent(
            type="assistant",
            tool_name="Read",
            parameters={"file_path": "/home/user/project/src/main.py"},
        )
        activity = ToolActivity.from_event(event)
        assert activity.name == "Read"
        assert activity.file_path == "/home/user/project/src/main.py"
        assert activity.command is None

    def test_from_tool_use_event_bash(self) -> None:
        event = ToolUseEvent(
            type="assistant",
            tool_name="Bash",
            parameters={"command": "ls -la"},
        )
        activity = ToolActivity.from_event(event)
        assert activity.name == "Bash"
        assert activity.file_path is None
        assert activity.command == "ls -la"

    def test_from_tool_use_event_no_params(self) -> None:
        event = ToolUseEvent(
            type="assistant",
            tool_name="SomeTool",
            parameters=None,
        )
        activity = ToolActivity.from_event(event)
        assert activity.name == "SomeTool"
        assert activity.file_path is None
        assert activity.command is None
