"""
短期上下文构建服务。

功能说明:
本文件实现上下文构建器。它负责同一 session 内的短期消息窗口拼接,并在构建
时自动召回长期摘要记忆和知识库片段,把它们压缩成结构化上下文附加给模型。

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
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.message_service import MessageService


class ContextBuilder:
    """
    短期上下文构建器。

    config: 全局配置对象,用于读取滑动窗口大小。
    message_service: 消息服务,用于读取同一 session 的历史消息。
    retrieval_service: 统一长期记忆检索服务,用于自动召回 Memory/Knowledge。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        message_service: MessageService,
        retrieval_service: MemoryRetrievalService | None = None,
    ) -> None:
        """保存配置、消息服务和长期记忆检索服务。"""

        self.config = config
        self.message_service = message_service
        self.retrieval_service = retrieval_service or MemoryRetrievalService(config=config)

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
        messages: list[BaseMessage] = []
        memory_context = self._build_retrieved_context(
            user_id=user_id,
            session_id=session_id,
            current_prompt=current_prompt,
            has_history=bool(history),
        )
        if memory_context:
            messages.append(SystemMessage(content=memory_context))
        messages.extend(self._to_langchain_message(message) for message in history)
        messages.append(HumanMessage(content=current_prompt))
        return messages

    def _build_retrieved_context(
        self,
        *,
        user_id: str,
        session_id: str,
        current_prompt: str,
        has_history: bool,
    ) -> str:
        """
        构建长期记忆和知识库召回上下文文本。

        user_id: 用户 ID。
        session_id: 会话 ID。
        current_prompt: 当前用户输入。
        """

        memories = self.retrieval_service.retrieve_long_term_memory(
            query=current_prompt,
            user_id=user_id,
            session_id=session_id,
            top_k=2,
        )
        if not memories:
            latest_summary = self.retrieval_service.get_latest_session_summary(
                user_id=user_id,
                session_id=session_id,
            )
            if latest_summary is not None:
                memories = [latest_summary]
        knowledge = self.retrieval_service.retrieve_knowledge(
            query=current_prompt,
            top_k=self.config.memory.rerank_top_k,
        )
        sections: list[str] = []
        sections.extend(self.config.model.retrieval_context_system_prompt.splitlines())
        if has_history:
            sections.append("短期上下文状态: 当前 session 已存在历史消息,回答时优先使用这些历史事实。")
        if memories:
            sections.append("长期记忆召回:")
            sections.extend(
                f"- score={item.final_score:.3f} content={item.memory.content}"
                for item in memories
            )
        if knowledge:
            sections.append("知识库召回:")
            sections.extend(
                f"- score={item.final_score:.3f} source={item.memory.source_uri or item.memory.source_id} content={item.memory.content}"
                for item in knowledge
            )
        if len(sections) <= 4 and not has_history:
            return ""
        return "\n".join(sections)

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
