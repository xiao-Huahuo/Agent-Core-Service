"""
Agent 工具注册表观测测试。

功能说明:
验证 AgentCore 暴露给 REST/gRPC/前端观测页的工具列表来自最终工具注册表。
"""

from agent_service.agent_core import AgentCore
from agent_service.tools import ToolRegistry


def test_agent_core_lists_registered_tools_from_final_registry() -> None:
    """工具观测快照应包含最终注册表中的工具基础信息。"""

    agent = AgentCore.__new__(AgentCore)
    agent.tool_registry = ToolRegistry.with_builtin_tools()
    agent.tools = []

    payload = agent.list_registered_tools()
    search_tool = next(tool for tool in payload["tools"] if tool["name"] == "search_knowledge")

    assert payload["tool_count"] == len(agent.tool_registry.definitions)
    assert search_tool["display_name"] == "搜索知识库"
    assert search_tool["argument_count"] >= 1
    assert "properties" in search_tool["args_schema"]


def test_current_time_tool_is_not_registered() -> None:
    """用户提问自带时间后，Agent 不应再暴露重复的当前时间工具。"""

    registry = ToolRegistry.with_builtin_tools()

    assert registry.get("get_current_time") is None
