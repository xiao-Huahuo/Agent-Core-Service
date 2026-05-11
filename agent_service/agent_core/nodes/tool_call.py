"""
工具调用节点。

功能说明:
本文件只实现 `ToolCallNode` 一个节点。该节点负责执行模型消息中的 tool_calls,
并把工具执行结果写回 LangGraph 消息状态。

使用说明:
`graph.py` 会把本节点注册为 `action` 节点。第一版支持传入 LangChain 工具列表;
后续 MCP 工具注册完成后,可以在构建图时把 MCP 工具也合并进该节点。
"""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig


class ToolCallNode:
    """
    执行工具调用的 LangGraph 节点。

    config: 全局配置对象,保留给后续根据配置选择内置工具或 MCP 工具。
    tools: LangChain 工具列表,用于构造 LangGraph 的 `ToolNode`。
    """

    def __init__(self, *, config: AgentConfig, tools: Sequence[Any] | None = None) -> None:
        """初始化工具节点;没有工具时保留空节点以返回可观测错误。"""

        self.config = config
        self.tools = list(tools or [])
        self.tool_node = ToolNode(self.tools) if self.tools else None

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """执行工具调用;若未注册工具则为每个调用返回说明性 ToolMessage。"""

        if self.tool_node is not None:
            result = self.tool_node.invoke(state)
            trace = {"node": "action", "event": "tools_executed", "tool_count": len(self.tools)}
            return {**result, "trace": [trace]}

        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        messages = [
            ToolMessage(
                content=f"工具 {tool_call.get('name', '')} 未注册,无法执行。",
                tool_call_id=tool_call["id"],
            )
            for tool_call in tool_calls
            if "id" in tool_call
        ]
        return {
            "messages": messages,
            "trace": [
                {
                    "node": "action",
                    "event": "no_tools_registered",
                    "requested_tool_count": len(tool_calls),
                }
            ],
        }
