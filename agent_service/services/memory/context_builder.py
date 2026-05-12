"""
短期上下文构建服务。

功能说明:
本文件实现第一版 `ContextBuilder`。它只负责同一 session 内的上下文追加和
滑动窗口: 从 MessageService 读取最近 N 条历史消息,转换成 LangChain messages,
然后把当前用户输入追加到最后。关键信息提取、summary、长期记忆和知识库 RAG
会在后续版本接入,不在第一版中实现。

使用说明:
调用方需要显式传入配置和 MessageService:

builder = ContextBuilder(config=config, message_service=message_service)
messages = builder.build_messages(user_id="u1", session_id="s1", current_prompt="你好")
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.message import MessageOut
from agent_service.services.message_service import MessageService


class ContextBuilder:
    """
    短期上下文构建器。

    config: 全局配置对象,用于读取滑动窗口大小。
    message_service: 消息服务,用于读取同一 session 的历史消息。
    """

    def __init__(self, *, config: AgentConfig, message_service: MessageService) -> None:
        """保存配置和消息服务。"""

        self.config = config
        self.message_service = message_service

    def build_messages(self, *, user_id: str, session_id: str, current_prompt: str) -> list[BaseMessage]:
        """
        构建当前轮 Agent 调用需要的 LangChain messages。

        user_id: 用户 ID,用于防止不同用户上下文串线。
        session_id: 会话 ID,用于读取同一会话的历史消息。
        current_prompt: 当前用户输入,永远追加到上下文最后。
        """

        history = self.message_service.list_recent_messages(
            user_id=user_id,
            session_id=session_id,
            limit=self.config.memory.max_context_messages,
        )
        messages = [self._to_langchain_message(message) for message in history]
        messages.append(HumanMessage(content=current_prompt))
        return messages

    @staticmethod
    def _to_langchain_message(message: MessageOut) -> BaseMessage:
        """
        将数据库消息 DTO 转换为 LangChain message。

        message: 数据库消息输出 DTO。
        """

        if message.role == "user":
            return HumanMessage(content=message.content)
        if message.role == "assistant":
            additional_kwargs: dict[str, Any] = {}
            if message.tool_calls_json:
                additional_kwargs["tool_calls"] = message.tool_calls_json
            return AIMessage(
                content=message.content,
                tool_calls=message.tool_calls_json,
                additional_kwargs=additional_kwargs,
            )
        if message.role == "tool":
            return ToolMessage(content=message.content, tool_call_id=message.tool_call_id or "")
        if message.role == "system":
            return SystemMessage(content=message.content)
        raise ValueError(f"不支持的消息角色: {message.role}")
