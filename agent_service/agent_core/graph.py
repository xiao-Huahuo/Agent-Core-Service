"""
Agent LangGraph 图构建模块。

功能说明:
本文件负责把独立节点装配成包含推理规划与反思的循环图。节点实现不写在这里,
而是分别放在 `nodes/` 目录下各文件中,满足每个节点文件只实现一个节点的结构要求。

使用说明:
外部通常不直接调用本模块,而是通过 `AgentCore(config=...)` 间接构建图。
当前图结构:
  safety_input -> compress -> planner -> agent -> action -> reflection -> compress -> ...
    -> safety_output -> summary -> END
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Sequence

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.nodes.base import AgentState
from agent_service.agent_core.nodes.compress import CompressNode
from agent_service.agent_core.nodes.model_decision import ModelDecisionNode
from agent_service.agent_core.nodes.planner import PlannerNode
from agent_service.agent_core.nodes.reflection import ReflectionNode
from agent_service.agent_core.nodes.safety import SafetyInputNode, SafetyOutputNode
from agent_service.agent_core.nodes.tool_call import ToolCallNode
from agent_service.core.agent_config import AgentConfig
from agent_service.services.safety import SafetyService
from agent_service.services.scheduler import LLMTaskScheduler
from agent_service.tools import ToolExecutor

logger = logging.getLogger(__name__)


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
        task_scheduler: LLMTaskScheduler | None = None,
        safety_service: SafetyService | None = None,
    ) -> None:
        """保存构图所需的配置和工具列表。"""

        self.config = config
        self.tools = list(tools or [])
        self.tool_executor = tool_executor
        self.task_scheduler = task_scheduler
        self.safety_service = safety_service
        self._branch_labels: dict[tuple[str, str], str] = {}

    @property
    def branch_labels(self) -> dict[tuple[str, str], str]:
        """条件边的(source, target) → 条件描述映射,供画图脚本使用。"""

        return dict(self._branch_labels)

    def build(self) -> CompiledStateGraph:
        """构建并编译 ReAct 循环图,包含安全审核、推理规划与反思节点。"""

        logger.info("开始构建 Agent 图...")
        self._branch_labels.clear()
        workflow = StateGraph(AgentState)
        if self.safety_service and self.safety_service.supports_input_audit:
            workflow.add_node(
                "safety_input",
                SafetyInputNode(config=self.config, safety_service=self.safety_service),
            )
        workflow.add_node(
            "compress",
            CompressNode(
                config=self.config,
                task_scheduler=self.task_scheduler,
            ),
        )
        workflow.add_node(
            "planner",
            PlannerNode(
                config=self.config,
                task_scheduler=self.task_scheduler,
            ),
        )
        workflow.add_node(
            "agent",
            ModelDecisionNode(
                config=self.config,
                tools=self.tools,
                task_scheduler=self.task_scheduler,
            ),
        )
        workflow.add_node(
            "action",
            ToolCallNode(config=self.config, tools=self.tools, tool_executor=self.tool_executor),
        )
        workflow.add_node(
            "reflection",
            ReflectionNode(
                config=self.config,
                task_scheduler=self.task_scheduler,
            ),
        )
        if self.safety_service is not None:
            workflow.add_node(
                "safety_output",
                SafetyOutputNode(config=self.config, safety_service=self.safety_service),
            )
        if self.safety_service and self.safety_service.supports_input_audit:
            workflow.set_entry_point("safety_input")
            workflow.add_conditional_edges(
                "safety_input",
                self._route_after_safety_input,
                path_map={"compress": "compress", "__end__": END},
            )
            self._branch_labels[("safety_input", "compress")] = "审核通过"
            self._branch_labels[("safety_input", "__end__")] = "审核拦截"
        else:
            workflow.set_entry_point("compress")
        workflow.add_edge("compress", "planner")
        workflow.add_edge("planner", "agent")
        if self.safety_service is not None:
            workflow.add_conditional_edges(
                "agent",
                self._route_after_model,
                path_map={"action": "action", "safety_output": "safety_output", "__end__": END},
            )
            self._branch_labels[("agent", "action")] = "有 tool_calls"
            self._branch_labels[("agent", "safety_output")] = "无 tool_calls"
        else:
            workflow.add_conditional_edges(
                "agent",
                self._route_after_model,
                path_map={"action": "action", "__end__": END},
            )
            self._branch_labels[("agent", "action")] = "有 tool_calls"
            self._branch_labels[("agent", "__end__")] = "无 tool_calls → 结束"
        workflow.add_edge("action", "reflection")
        if self.safety_service is not None:
            workflow.add_conditional_edges(
                "reflection",
                self._route_after_reflection,
                path_map={"planner": "planner", "compress": "compress", "safety_output": "safety_output", "__end__": END},
            )
            self._branch_labels[("reflection", "planner")] = "continue"
            self._branch_labels[("reflection", "compress")] = "context overflow"
            self._branch_labels[("reflection", "safety_output")] = "answer"
        else:
            workflow.add_conditional_edges(
                "reflection",
                self._route_after_reflection,
                path_map={"planner": "planner", "compress": "compress", "__end__": END},
            )
            self._branch_labels[("reflection", "planner")] = "continue"
            self._branch_labels[("reflection", "compress")] = "context overflow"
            self._branch_labels[("reflection", "__end__")] = "answer → 结束"
        if self.safety_service is not None:
            workflow.add_edge("safety_output", END)
            self._branch_labels[("safety_output", "__end__")] = "审核结束"
        # Summary 节点不再在图中自动执行,写入长期记忆改为由 write_long_term_memory 工具主动触发
        compiled = workflow.compile()
        logger.info("Agent 图构建完成 | 节点数=%d", len(compiled.get_graph().nodes))
        return compiled

    def _route_after_model(self, state: AgentState) -> Literal["action", "safety_output", "__end__"]:
        """根据模型最后一条消息是否包含工具调用决定下一步。"""

        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        if tool_calls:
            return "action"
        return "safety_output" if self.safety_service is not None else "__end__"

    def _route_after_reflection(self, state: AgentState) -> Literal["planner", "compress", "safety_output", "__end__"]:
        """
        根据反思节点决策决定下一步。
        "continue" → planner(继续工具循环),
        "compress" → compress(上下文溢出,先压缩再进入 planner),
        "answer" → 安全输出审核或直接结束。
        """

        decision = state.get("reflection_decision", "continue")
        if decision == "continue":
            return "planner"
        if decision == "compress":
            return "compress"
        return "safety_output" if self.safety_service is not None else "__end__"

    @staticmethod
    def _route_after_safety_input(state: AgentState) -> Literal["compress", "__end__"]:
        """安全输入审核通过 → compress,拦截 → 直接结束。"""

        decision = state.get("reflection_decision")
        if decision == "blocked":
            return "__end__"
        return "compress"

    @staticmethod
    def _route_after_safety_output(state: AgentState) -> Literal["summary", "__end__"]:
        """安全输出审核通过 → summary,拦截 → 直接结束。"""

        last_trace: dict[str, Any] = {}
        trace_list = state.get("trace", [])
        if trace_list:
            last_trace = trace_list[-1]
        if last_trace.get("node") == "safety_output" and last_trace.get("event") in ("blocked",):
            return "__end__"
        return "summary"
