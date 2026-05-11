"""
模型决策节点。

功能说明:
本文件只实现 `ModelDecisionNode` 一个节点。该节点负责调用 OpenAI Compatible
聊天模型,根据当前 `AgentState.messages` 决定直接回复用户还是发起工具调用。

使用说明:
`graph.py` 会把本节点注册为 `agent` 节点。节点接收 `AgentConfig` 和工具列表,
使用 `config.model` 中的模型名称、API Key、Base URL、温度和超时时间初始化模型。
"""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig


class ModelDecisionNode:
    """
    调用大模型进行 Agent 决策的 LangGraph 节点。

    config: 全局配置对象,从 `AgentCore(config=...)` 显式传入。
    tools: 可供模型调用的 LangChain 工具列表;为空时模型只会进行普通对话。
    """

    def __init__(self, *, config: AgentConfig, tools: Sequence[Any] | None = None) -> None:
        """初始化聊天模型,并在存在工具时绑定工具。"""

        self.config = config
        self.tools = list(tools or [])
        self.model = self._build_model()

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """读取当前消息状态,调用模型,并把模型响应追加回 `messages`。"""

        system_message = SystemMessage(content=self.config.model.system_prompt)
        response = self.model.invoke([system_message, *state["messages"]])
        tool_calls = getattr(response, "tool_calls", []) or []
        return {
            "messages": [response],
            "trace": [
                {
                    "node": "agent",
                    "event": "model_response",
                    "tool_call_count": len(tool_calls),
                    "has_content": bool(response.content),
                }
            ],
        }

    def _build_model(self) -> Any:
        """根据 `AgentConfig.ModelConfig` 创建 OpenAI Compatible 聊天模型。"""

        if not self.config.model.model_name:
            raise ValueError("config.model.model_name 不能为空。")
        if not self.config.model.api_key:
            raise ValueError("config.model.api_key 不能为空。")
        if not self.config.model.base_url:
            raise ValueError("config.model.base_url 不能为空。")

        model = ChatOpenAI(
            model=self.config.model.model_name,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            temperature=self.config.model.temperature,
            timeout=self.config.model.timeout_seconds,
        )
        if self.tools:
            return model.bind_tools(self.tools)
        return model
