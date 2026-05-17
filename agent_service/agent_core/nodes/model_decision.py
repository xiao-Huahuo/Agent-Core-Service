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

import logging
from typing import Any, Sequence

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK, LLMTaskScheduler, get_llm_task_scheduler
from agent_service.tools.runtime_context import get_agent_token_callback, get_context_mirror_callback

logger = logging.getLogger(__name__)


class ModelDecisionNode:
    """
    调用大模型进行 Agent 决策的 LangGraph 节点。

    config: 全局配置对象,从 `AgentCore(config=...)` 显式传入。
    tools: 可供模型调用的 LangChain 工具列表;为空时模型只会进行普通对话。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        task_scheduler: LLMTaskScheduler | None = None,
    ) -> None:
        """初始化聊天模型,并在存在工具时绑定工具。"""

        self.config = config
        self.tools = list(tools or [])
        self.tool_names = [str(tool.name) for tool in self.tools if getattr(tool, "name", None)]
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.model = self._build_model()

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """读取当前消息状态,调用模型,并把模型响应追加回 `messages`。"""

        system_content = self.config.model.system_prompt
        plan = state.get("plan")
        if plan and plan.get("hint"):
            covered = plan.get("covered", [])
            suggested = plan.get("suggested", [])
            sufficient = plan.get("sufficient", False)
            status = "信息已充足，可以结束探索" if sufficient else "信息尚不充分，需继续探索"
            system_content += (
                f"\n\n【探索状态 — 仅供参考，你自行决定下一步】\n"
                f"已覆盖: {', '.join(covered) if covered else '暂无'}\n"
                f"建议方向: {', '.join(suggested) if suggested else '暂无'}\n"
                f"当前判断: {status}\n"
                f"策略提示: {plan['hint']}"
            )

        system_message = SystemMessage(content=system_content)
        token_callback = get_agent_token_callback()

        if token_callback is not None:
            return self._streaming_call(
                system_message=system_message,
                state=state,
                token_callback=token_callback,
            )

        response = self.task_scheduler.invoke_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, *state["messages"]],
            tool_names=self.tool_names,
        )
        tool_calls = getattr(response, "tool_calls", []) or []
        return {
            "messages": [response],
            "trace": [
                {
                    "node": "agent",
                    "event": "model_response",
                    "tool_call_count": len(tool_calls),
                    "has_content": bool(response.content),
                    "human_readable": self._make_agent_readable(tool_calls, bool(response.content)),
                }
            ],
        }

    def _streaming_call(
        self,
        *,
        system_message: SystemMessage,
        state: AgentState,
        token_callback: Any,
    ) -> dict[str, Any]:
        """
        流式调用模型,逐 token 通过 callback 推送,最终返回完整消息。

        system_message: 系统提示消息。
        state: 当前 AgentState。
        token_callback: 接收累积文本内容的回调。
        """

        cumulative = ""
        final_message: Any = None

        context_callback = get_context_mirror_callback()
        if context_callback is not None:
            context_callback(self._serialize_messages([system_message, *state["messages"]]))

        for chunk in self.task_scheduler.stream_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, *state["messages"]],
            tool_names=self.tool_names,
        ):
            delta = chunk.get("content_delta", "")
            if delta:
                cumulative += delta
                token_callback(cumulative)
            if chunk.get("status") == "complete":
                final_message = chunk.get("message")
        if final_message is None:
            from langchain_core.messages import AIMessage
            final_message = AIMessage(content=cumulative)
        tool_calls = getattr(final_message, "tool_calls", []) or []
        has_content = bool(getattr(final_message, "content", None))
        return {
            "messages": [final_message],
            "trace": [
                {
                    "node": "agent",
                    "event": "model_response",
                    "tool_call_count": len(tool_calls),
                    "has_content": has_content,
                    "human_readable": self._make_agent_readable(tool_calls, has_content),
                }
            ],
        }

    @staticmethod
    def _make_agent_readable(tool_calls: list, has_content: bool) -> str:
        """根据模型决策生成人类可读的思考描述。"""

        if tool_calls:
            names = ", ".join(tc.get("name", "") for tc in tool_calls if tc.get("name"))
            return f"模型决定调用工具：{names}"
        if has_content:
            return "模型生成最终回复。"
        return "模型返回空响应。"

    @staticmethod
    def _serialize_messages(messages: list) -> list[dict[str, Any]]:
        """
        将 LangChain BaseMessage 列表序列化为 JSON 友好的 dict 列表。

        用于上下文镜像回调, 让前端 Obs 面板能看到模型收到的完整消息。
        """
        role_map = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}
        result: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {
                "role": role_map.get(msg.type, msg.type),
                "content": str(getattr(msg, "content", "") or ""),
            }
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                entry["tool_calls"] = tool_calls
            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                entry["tool_call_id"] = tool_call_id
            name = getattr(msg, "name", None)
            if name:
                entry["name"] = name
            result.append(entry)
        return result

    def _build_model(self) -> Any:
        """根据 `AgentConfig.ModelConfig` 创建 OpenAI Compatible 聊天模型。"""

        if not self.config.model.model_name:
            raise ValueError("config.model.model_name 不能为空。")
        if not self.config.model.api_key:
            raise ValueError("config.model.api_key 不能为空。")
        if not self.config.model.base_url:
            raise ValueError("config.model.base_url 不能为空。")

        model_kwargs = AgentConfig.ModelConfig.get_model_kwargs(self.config.model.model_name)
        model = ChatOpenAI(
            model=self.config.model.model_name,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            temperature=self.config.model.resolve_primary_temperature(),
            timeout=self.config.model.timeout_seconds,
            **model_kwargs,
        )
        if self.tools:
            return model.bind_tools(self.tools)
        return model
