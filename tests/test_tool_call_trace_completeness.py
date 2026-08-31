"""Tool action trace completeness regression tests.

The Debug language trace must keep exact tool arguments and results even when
the compact one-line preview is intentionally shortened for the chat UI.
"""

from langchain_core.messages import AIMessage

from agent_service.agent_core.nodes.tool_call import ToolCallNode
from agent_service.core.agent_config import AgentConfig


class _Registry:
    """Minimal registry used by the executor test double."""

    @staticmethod
    def get(_name: str):
        return None


class _Executor:
    """Return an exact long result without involving real tools."""

    registry = _Registry()

    @staticmethod
    def execute(_name: str, _arguments: dict) -> str:
        return "完整返回-" + "R" * 400


def test_action_trace_keeps_full_arguments_and_result() -> None:
    """Action traces expose full payloads instead of only truncated summaries."""

    config = AgentConfig.load_config({}, load_env=False, ensure_directories=False, ensure_models=False)
    arguments = {"goal": "完整参数-" + "A" * 400, "mode": "background"}
    node = ToolCallNode(config=config, tool_executor=_Executor())

    result = node({
        "messages": [AIMessage(content="", tool_calls=[{
            "id": "call-1",
            "name": "spawn_child_agent",
            "args": arguments,
        }])],
    })

    start_trace, end_trace = result["trace"]
    assert start_trace["tool_args"] == arguments
    assert "参数：" not in start_trace["human_readable"]
    assert end_trace["tool_args"] == arguments
    assert end_trace["raw_content"] == "完整返回-" + "R" * 400
