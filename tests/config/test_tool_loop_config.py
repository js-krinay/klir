from klir.config import AgentConfig


def test_tool_loop_threshold_defaults_to_zero() -> None:
    cfg = AgentConfig()
    assert cfg.tool_loop_threshold == 0


def test_tool_loop_threshold_from_dict() -> None:
    cfg = AgentConfig(tool_loop_threshold=15)
    assert cfg.tool_loop_threshold == 15
