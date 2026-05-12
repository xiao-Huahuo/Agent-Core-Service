"""
会话摘要长期记忆服务。

功能说明:
本文件负责把 session 中尚未摘要覆盖的消息交给 LLM 生成关键信息摘要,再生成
Embedding 并写入统一长期记忆表。摘要写入后,对应原始消息会标记为
`is_summarized=True`,后续短期上下文构建器将不再重复加载这些原始消息。

使用说明:
service = SessionSummaryService(config=config)
service.summarize_session(user_id="u1", session_id="s1")
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.schemas.message import MessageOut
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.memory_resolver import MemoryResolver
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.message_service import MessageService


class SessionSummaryService:
    """
    会话摘要服务。

    config: 全局配置对象。
    message_service: 可选消息服务。
    memory_service: 可选长期记忆服务。
    embedding_service: 可选 Embedding 服务。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        message_service: MessageService | None = None,
        memory_service: LongTermMemoryService | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """初始化摘要服务。"""

        self.config = config
        self.message_service = message_service or MessageService(config=config)
        self.memory_service = memory_service or LongTermMemoryService(config=config)
        self.embedding_service = embedding_service or EmbeddingService(config=config)
        self.memory_resolver = MemoryResolver(
            config=config,
            memory_service=self.memory_service,
            embedding_service=self.embedding_service,
        )
        self.model = self._build_model()

    def summarize_session(self, *, user_id: str, session_id: str) -> str | None:
        """
        摘要指定 session 的未摘要消息并写入向量库。

        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        messages = self.message_service.list_unsummarized_messages(user_id=user_id, session_id=session_id)
        if not messages:
            return None
        summary = self._summarize_messages(messages)
        if not summary:
            return None
        vector = self.embedding_service.embed_text(summary)
        message_ids = [message.message_id for message in messages]
        summary_memory = self.memory_service.create_memory(
            LongTermMemorySpecCreate(
                user_id=user_id,
                session_id=session_id,
                tag=self.config.constants.memory_tag,
                memory_type="session_summary",
                content=summary,
                source_type="session_messages",
                source_id=session_id,
                source_hash=self._hash_message_ids(message_ids),
                source_range_json={"message_ids": message_ids},
                metadata_json={"message_count": len(messages)},
                confidence=0.8,
                importance=0.7,
                authority=0.5,
                embedding_model=self.config.model.embedding_model_name,
                embedding_vector_json=vector,
            )
        )
        self.memory_resolver.resolve_summary(
            user_id=user_id,
            session_id=session_id,
            summary_memory=summary_memory,
        )
        self.message_service.mark_messages_summarized(message_ids=message_ids)
        return summary

    def _summarize_messages(self, messages: Sequence[MessageOut]) -> str:
        """
        调用 LLM 从消息列表提取摘要。

        messages: 尚未摘要覆盖的消息。
        """

        transcript = "\n".join(f"{message.role}: {message.content}" for message in messages if message.content)
        if not transcript.strip():
            return ""
        response = self.model.invoke(
            [
                SystemMessage(
                    content=(
                        "你负责为 Agent 会话生成长期记忆摘要。"
                        "只保留后续对话有用的用户偏好、事实、约束、任务目标、未完成事项和工具结果。"
                        "不要编造,不要保留无意义寒暄。输出中文短摘要。"
                    )
                ),
                HumanMessage(content=transcript),
            ]
        )
        return str(response.content).strip()

    def _build_model(self) -> ChatOpenAI:
        """
        创建摘要用 LLM。

        使用主模型配置,避免为第一版额外增加摘要专用模型配置。
        """

        if not self.config.model.model_name:
            raise ValueError("config.model.model_name 不能为空。")
        if not self.config.model.api_key:
            raise ValueError("config.model.api_key 不能为空。")
        if not self.config.model.base_url:
            raise ValueError("config.model.base_url 不能为空。")
        return ChatOpenAI(
            model=self.config.model.model_name,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            temperature=0.0,
            timeout=self.config.model.timeout_seconds,
        )

    @staticmethod
    def _hash_message_ids(message_ids: Sequence[str]) -> str:
        """
        根据消息 ID 列表生成摘要来源哈希。

        message_ids: 被摘要覆盖的消息 ID。
        """

        return hashlib.sha256("|".join(message_ids).encode("utf-8")).hexdigest()
