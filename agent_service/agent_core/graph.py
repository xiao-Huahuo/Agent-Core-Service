"""
Agent LangGraph 图构建模块。

功能说明:
本文件负责把独立节点装配成最基础的 ReAct 循环图。节点实现不写在这里,
而是分别放在 `nodes/model_decision.py`、`nodes/tool_call.py` 和 `nodes/summary.py`
中,满足每个节点文件只实现一个节点的结构要求。

使用说明:
外部通常不直接调用本模块,而是通过 `AgentCore(config=...)` 间接构建图。
第一版图结构为 `agent -> action -> agent -> summary -> END`。
"""

from __future__ import annotations

from typing import Any, Literal, Sequence

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.nodes.base import AgentState
from agent_service.agent_core.nodes.model_decision import ModelDecisionNode
from agent_service.agent_core.nodes.summary import SummaryNode
from agent_service.agent_core.nodes.tool_call import ToolCallNode
from agent_service.core.agent_config import AgentConfig
from agent_service.tools import ToolExecutor


class AgentGraphBuilder:
    """
    Agent 图构建器。

    config: 全局配置对象,由 `AgentCore` 显式传入。
    tools: 可供模型调用的 LangChain 工具列表。
    tool_executor: 项目工具执行器,用于 action 节点实际执行 tool_calls。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        """保存构图所需的配置和工具列表。"""

        self.config = config
        self.tools = list(tools or [])
        self.tool_executor = tool_executor

    def build(self) -> CompiledStateGraph:
        """构建并编译最基础的 Agent ReAct 循环图。"""

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", ModelDecisionNode(config=self.config, tools=self.tools))
        workflow.add_node(
            "action",
            ToolCallNode(config=self.config, tools=self.tools, tool_executor=self.tool_executor),
        )
        workflow.add_node("summary", SummaryNode(config=self.config))
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self._route_after_model,
            path_map={"action": "action", "summary": "summary"},
        )
        workflow.add_edge("action", "agent")
        workflow.add_edge("summary", END)
        return workflow.compile()

    @staticmethod
    def _route_after_model(state: AgentState) -> Literal["action", "summary"]:
        """根据模型最后一条消息是否包含工具调用决定下一步节点。"""

        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        return "action" if tool_calls else "summary"
