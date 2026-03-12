from __future__ import annotations

from klir.cli.tool_loop_detector import ToolLoopDetector


class TestToolLoopDetector:
    def test_no_loop_different_tools(self) -> None:
        detector = ToolLoopDetector()
        for tool in ["read", "write", "search", "edit", "list"]:
            detector.record(tool)
            assert not detector.is_looping

    def test_loop_detected_at_threshold(self) -> None:
        detector = ToolLoopDetector(threshold=3)
        detector.record("read")
        assert not detector.is_looping
        detector.record("read")
        assert not detector.is_looping
        detector.record("read")
        assert detector.is_looping

    def test_counter_resets_on_different_tool(self) -> None:
        detector = ToolLoopDetector(threshold=3)
        detector.record("read")
        detector.record("read")
        assert detector.consecutive_count == 2
        detector.record("write")
        assert detector.consecutive_count == 1
        assert not detector.is_looping

    def test_default_threshold(self) -> None:
        detector = ToolLoopDetector()
        for _ in range(9):
            detector.record("read")
            assert not detector.is_looping
        detector.record("read")
        assert detector.is_looping

    def test_count_property(self) -> None:
        detector = ToolLoopDetector()
        assert detector.consecutive_count == 0
        assert detector.current_tool is None
        detector.record("read")
        assert detector.consecutive_count == 1
        assert detector.current_tool == "read"
        detector.record("read")
        assert detector.consecutive_count == 2

    def test_reset(self) -> None:
        detector = ToolLoopDetector()
        detector.record("read")
        detector.record("read")
        detector.reset()
        assert detector.consecutive_count == 0
        assert detector.current_tool is None
        assert not detector.is_looping
