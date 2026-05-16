"""
工具调用节点。

功能说明:
本文件只实现 `ToolCallNode` 一个节点。该节点负责执行模型消息中的 tool_calls,
并把工具执行结果写回 LangGraph 消息状态。

使用说明:
`graph.py` 会把本节点注册为 `action` 节点。默认路径使用项目工具执行器执行
内置工具;如果未来传入外部 LangChain 工具且没有项目执行器,则回退到 LangGraph
自带 `ToolNode`。
"""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.tools import ToolExecutor
from agent_service.tools.runtime_context import get_tool_trace_callback


class ToolCallNode:
    """
    执行工具调用的 LangGraph 节点。

    config: 全局配置对象,保留给后续根据配置选择内置工具或 MCP 工具。
    tools: LangChain 工具列表,用于构造 LangGraph 的 `ToolNode`。
    tool_executor: 项目工具执行器,优先用于执行模型生成的 tool_calls。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        """初始化工具节点;没有工具时保留空节点以返回可观测错误。"""

        self.config = config
        self.tools = list(tools or [])
        self.tool_executor = tool_executor
        self.tool_node = ToolNode(self.tools) if self.tools and self.tool_executor is None else None

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """执行工具调用;若未注册工具则为每个调用返回说明性 ToolMessage。"""

        if self.tool_executor is not None:
            return self._execute_with_project_executor(state)

        if self.tool_node is not None:
            result = self.tool_node.invoke(state)
            trace = {
                "node": "action",
                "event": "tools_executed",
                "tool_count": len(self.tools),
                "human_readable": f"通过 LangGraph ToolNode 执行了 {len(self.tools)} 个工具。",
            }
            return {**result, "trace": [trace]}

        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        tool_names = [tc.get("name", "") for tc in tool_calls]
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
                    "human_readable": f"模型尝试调用工具（{', '.join(tool_names)}），但工具未注册，无法执行。",
                }
            ],
        }

    def _execute_with_project_executor(self, state: AgentState) -> dict[str, Any]:
        """
        使用项目工具执行器处理 tool_calls。

        state: 当前 LangGraph 状态,最后一条消息应为包含 tool_calls 的 AIMessage。
        """

        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        messages: list[ToolMessage] = []
        traces: list[dict[str, Any]] = []
        trace_callback = get_tool_trace_callback()
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id")
            if not tool_call_id:
                continue
            tool_name = tool_call.get("name", "")
            arguments = tool_call.get("args", {})
            if not isinstance(arguments, dict):
                arguments = {}
            args_summary = self._summarize_args(arguments)
            start_trace = {
                "node": "action",
                "event": "tool_call_start",
                "tool_name": tool_name,
                "tool_args_summary": args_summary,
                "human_readable": f"正在调用工具「{tool_name}」，参数：{args_summary}",
            }
            traces.append(start_trace)
            if trace_callback is not None:
                trace_callback(start_trace)
            try:
                content = self.tool_executor.execute(tool_name, arguments)
            except Exception as exc:
                content = f"工具 {tool_name} 执行失败: {exc}"
            messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))
            result_summary = self._summarize_result(content)
            result_count = self._count_results(content)
            end_trace = {
                "node": "action",
                "event": "tool_call_end",
                "tool_name": tool_name,
                "result_summary": result_summary,
                "human_readable": f"工具「{tool_name}」返回：{result_summary}",
                "result_count": result_count,
            }
            traces.append(end_trace)
            if trace_callback is not None:
                trace_callback(end_trace)
        return {"messages": messages, "trace": traces}

    @staticmethod
    def _summarize_args(arguments: dict[str, Any]) -> str:
        """将工具参数转为简短可读摘要，单行截断。"""

        parts: list[str] = []
        for k, v in arguments.items():
            v_str = str(v)
            if len(v_str) > 80:
                v_str = v_str[:80] + "…"
            parts.append(f"{k}={v_str}")
        summary = ", ".join(parts) if parts else "无参数"
        return summary[:200]

    @staticmethod
    def _summarize_result(content: str) -> str:
        """将工具返回结果截断为摘要文本。"""

        text = str(content).strip()
        if len(text) <= 200:
            return text
        return text[:200] + "…"

    @staticmethod
    def _count_results(content: str) -> int | None:
        """从工具输出中统计条目数,供前端展示"检索到 X 条知识"等。"""
        lines = str(content).strip().split("\n")
        count = 0
        for line in lines:
            stripped = line.lstrip()
            # 匹配 "1. " "2. " 等编号行
            if stripped and stripped[0].isdigit():
                dot_pos = stripped.find(". ")
                if dot_pos > 0 and stripped[:dot_pos].isdigit():
                    count += 1
        return count if count > 0 else None
