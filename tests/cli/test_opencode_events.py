"""Tests for OpenCode CLI JSON event parsing."""

from __future__ import annotations

import json

from klir.cli.opencode_events import (
    parse_opencode_json,
    parse_opencode_stream_event,
)
from klir.cli.stream_events import (
    AssistantTextDelta,
    ResultEvent,
    SystemInitEvent,
    ThinkingEvent,
    ToolUseEvent,
)

# ---------------------------------------------------------------------------
# parse_opencode_json
# ---------------------------------------------------------------------------


class TestParseOpenCodeJson:
    def test_empty_input(self) -> None:
        text, sid, usage = parse_opencode_json("")
        assert text == ""
        assert sid is None
        assert usage is None

    def test_plain_text_fallback(self) -> None:
        text, sid, usage = parse_opencode_json("Hello world")
        assert text == "Hello world"
        assert sid is None
        assert usage is None

    def test_multiline_plain_text(self) -> None:
        text, _sid, _usage = parse_opencode_json("line one\nline two")
        assert text == "line one\nline two"

    def test_json_with_result_field(self) -> None:
        data = json.dumps({"result": "The answer is 42."})
        text, _sid, _usage = parse_opencode_json(data)
        assert text == "The answer is 42."

    def test_json_with_text_field(self) -> None:
        data = json.dumps({"text": "Some text output"})
        text, _sid, _usage = parse_opencode_json(data)
        assert text == "Some text output"

    def test_json_with_content_field(self) -> None:
        data = json.dumps({"content": "Content value"})
        text, _sid, _usage = parse_opencode_json(data)
        assert text == "Content value"

    def test_session_id_extraction(self) -> None:
        data = json.dumps({"session_id": "sess-abc123", "text": "output"})
        _text, sid, _usage = parse_opencode_json(data)
        assert sid == "sess-abc123"

    def test_session_id_from_camel_case_key(self) -> None:
        data = json.dumps({"sessionId": "sess-xyz", "text": "output"})
        _, sid, _ = parse_opencode_json(data)
        assert sid == "sess-xyz"

    def test_session_id_from_id_key(self) -> None:
        data = json.dumps({"id": "sess-id-001", "text": "hi"})
        _, sid, _ = parse_opencode_json(data)
        assert sid == "sess-id-001"

    def test_first_session_id_wins(self) -> None:
        lines = "\n".join([
            json.dumps({"session_id": "first", "text": "a"}),
            json.dumps({"session_id": "second", "text": "b"}),
        ])
        _, sid, _ = parse_opencode_json(lines)
        assert sid == "first"

    def test_usage_from_result_event(self) -> None:
        data = json.dumps({
            "type": "result",
            "text": "done",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        _, _, usage = parse_opencode_json(data)
        assert usage == {"input_tokens": 100, "output_tokens": 50}

    def test_usage_from_stats_block(self) -> None:
        data = json.dumps({
            "text": "out",
            "stats": {"input_tokens": 200, "output_tokens": 80},
        })
        _, _, usage = parse_opencode_json(data)
        assert usage is not None
        assert usage["input_tokens"] == 200
        assert usage["output_tokens"] == 80

    def test_message_started_with_content_list(self) -> None:
        data = json.dumps({
            "type": "message.completed",
            "content": [
                {"type": "text", "text": "block one"},
                {"type": "text", "text": "block two"},
            ],
        })
        text, _, _ = parse_opencode_json(data)
        assert "block one" in text
        assert "block two" in text

    def test_message_part_updated_text(self) -> None:
        data = json.dumps({
            "type": "message.part.updated",
            "text": "partial update",
        })
        text, _, _ = parse_opencode_json(data)
        assert text == "partial update"

    def test_blank_lines_skipped(self) -> None:
        raw = "\n\n" + json.dumps({"text": "value"}) + "\n\n"
        text, _, _ = parse_opencode_json(raw)
        assert text == "value"

    def test_non_dict_json_treated_as_plain_text(self) -> None:
        raw = json.dumps([1, 2, 3])
        text, sid, _usage = parse_opencode_json(raw)
        assert text == raw
        assert sid is None

    def test_empty_session_id_ignored(self) -> None:
        data = json.dumps({"session_id": "  ", "text": "ok"})
        _, sid, _ = parse_opencode_json(data)
        assert sid is None


# ---------------------------------------------------------------------------
# parse_opencode_stream_event
# ---------------------------------------------------------------------------


class TestParseOpenCodeStreamEvent:
    def test_empty_line(self) -> None:
        assert parse_opencode_stream_event("") == []
        assert parse_opencode_stream_event("   ") == []

    def test_plain_text_becomes_text_delta(self) -> None:
        events = parse_opencode_stream_event("Hello stream")
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)
        assert events[0].text == "Hello stream"

    def test_session_started_event(self) -> None:
        line = json.dumps({"type": "session.started", "session_id": "s-001"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], SystemInitEvent)
        assert events[0].session_id == "s-001"

    def test_session_created_event(self) -> None:
        line = json.dumps({"type": "session.created", "id": "s-002"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], SystemInitEvent)
        assert events[0].session_id == "s-002"

    def test_session_completed_event(self) -> None:
        line = json.dumps({
            "type": "session.completed",
            "text": "final",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].usage == {"input_tokens": 10, "output_tokens": 5}

    def test_message_completed_event(self) -> None:
        line = json.dumps({"type": "message.completed", "text": "done"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)

    def test_result_type_event(self) -> None:
        line = json.dumps({"type": "result", "text": "answer"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)

    def test_error_event(self) -> None:
        line = json.dumps({
            "type": "error",
            "error": {"message": "rate limited"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].is_error is True
        assert "rate limited" in events[0].result

    def test_session_failed_event(self) -> None:
        line = json.dumps({"type": "session.failed", "error": "timeout"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ResultEvent)
        assert events[0].is_error is True

    def test_message_part_updated_text_delta(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "text", "text": "chunk"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)
        assert events[0].text == "chunk"

    def test_message_delta_text(self) -> None:
        line = json.dumps({"type": "message.delta", "text": "delta text"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)

    def test_content_delta_text(self) -> None:
        line = json.dumps({"type": "content.delta", "content": "content val"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], AssistantTextDelta)

    def test_thinking_event(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "thinking", "text": "reasoning..."},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)
        assert events[0].text == "reasoning..."

    def test_reasoning_event(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "reasoning", "text": "thinking hard"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)

    def test_tool_started_event(self) -> None:
        line = json.dumps({
            "type": "tool.started",
            "name": "bash",
            "parameters": {"command": "ls"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolUseEvent)
        assert events[0].tool_name == "bash"
        assert events[0].parameters == {"command": "ls"}

    def test_tool_use_event(self) -> None:
        line = json.dumps({
            "type": "tool_use",
            "tool_name": "read_file",
            "input": {"path": "/tmp/x"},
        })
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolUseEvent)
        assert events[0].tool_name == "read_file"

    def test_tool_running_event(self) -> None:
        line = json.dumps({"type": "tool.running", "tool": "edit"})
        events = parse_opencode_stream_event(line)
        assert len(events) == 1
        assert isinstance(events[0], ToolUseEvent)
        assert events[0].tool_name == "edit"

    def test_unknown_event_type_returns_empty(self) -> None:
        line = json.dumps({"type": "internal.debug", "data": "foo"})
        events = parse_opencode_stream_event(line)
        assert events == []

    def test_tool_without_name_returns_empty(self) -> None:
        line = json.dumps({"type": "tool.started"})
        events = parse_opencode_stream_event(line)
        assert events == []

    def test_content_update_empty_text_returns_empty(self) -> None:
        line = json.dumps({
            "type": "message.part.updated",
            "part": {"type": "text", "text": ""},
        })
        events = parse_opencode_stream_event(line)
        assert events == []
