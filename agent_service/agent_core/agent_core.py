"""
AgentCore 对外入口模块。

功能说明:
本文件提供 `AgentCore` 类,作为 Agent 微服务核心能力的对外门面。它不直接实现
具体节点逻辑,而是接收 `AgentConfig` 后调用 `AgentGraphBuilder` 构建 LangGraph 图,
再通过 `stream_run()` 对外提供最基础的 Agent 循环执行能力。每次初始化时还会
调用绘图脚本,读取实际编译后的图结构,在项目根目录生成 Mermaid 节点流程图。

使用说明:
调用方应显式传入配置对象:

config = AgentConfig.load_config()
agent = AgentCore(config=config)
for chunk in agent.stream_run(prompt="你好", user_id="u1", session_id="s1"):
    ...
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.graph import AgentGraphBuilder
from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.draw_agent_graph import draw_agent_graph
from agent_service.tools import ToolExecutor, ToolRegistry


class AgentCore:
    """
    Agent 微服务核心入口。

    config: 由 `core.agent_config.AgentConfig.load_config()` 创建的显式配置对象。
    tools: 可选 LangChain 工具列表;为空时默认加载工具注册表中的内置工具。
    graph: 可选已编译图对象,主要用于测试时注入假图以避免真实模型请求。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        graph: CompiledStateGraph | None = None,
    ) -> None:
        """保存配置、构建或接收 LangGraph 图,并输出当前节点流程图 SVG。"""

        self.config = config
        self.tool_registry = ToolRegistry.with_builtin_tools() if tools is None else None
        self.tool_executor = ToolExecutor(registry=self.tool_registry) if self.tool_registry is not None else None
        self.tools = list(tools) if tools is not None else self.tool_registry.to_langchain_tools()
        self.graph: CompiledStateGraph = graph or AgentGraphBuilder(
            config=config,
            tools=self.tools,
            tool_executor=self.tool_executor,
        ).build()
        self.graph_diagram_path = draw_agent_graph(
            compiled_graph=self.graph,
            output_path=config.storage.project_root / "agent_graph.mmd",
        )

    def stream_run(self, *, prompt: str, user_id: str, session_id: str) -> Iterator[str]:
        """
        运行一轮 Agent 循环并输出 SSE 风格字符串。

        prompt: 用户本轮输入。
        user_id: 用户 ID,用于后续记忆和会话隔离。
        session_id: 会话 ID,用于后续 checkpoint 和短期记忆恢复。
        """

        inputs = {
            "messages": [HumanMessage(content=prompt)],
            "user_id": user_id,
            "session_id": session_id,
            "trace": [],
        }
        runtime_config = {"configurable": {"thread_id": session_id}}
        for event in self.graph.stream(inputs, config=runtime_config, stream_mode="updates"):
            for node_name, state_update in event.items():
                payload = self._build_stream_payload(node_name=node_name, state_update=state_update)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    def close(self) -> None:
        """释放 AgentCore 持有的资源;第一版没有长期连接需要关闭。"""

    @staticmethod
    def _build_stream_payload(*, node_name: str, state_update: dict[str, Any] | None) -> dict[str, Any]:
        """把 LangGraph 节点更新转换为稳定的流式输出结构。"""

        if not state_update:
            return {"node": node_name, "content": "", "tool_calls": [], "trace": []}

        messages = state_update.get("messages", [])
        last_message = messages[-1] if messages else None
        content = getattr(last_message, "content", "") if last_message is not None else ""
        tool_calls = getattr(last_message, "tool_calls", []) if last_message is not None else []
        return {
            "node": node_name,
            "content": content or "",
            "tool_calls": tool_calls or [],
            "trace": state_update.get("trace", []),
        }
