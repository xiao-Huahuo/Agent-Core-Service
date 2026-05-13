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

from collections.abc import Sequence
import hashlib

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.message import MessageOut
from agent_service.services.memory.important_fact_summary_service import ImportantFactSummaryService
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.memory_resolver import MemoryResolver
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.message_service import MessageService
from agent_service.task_schedule import BACKGROUND_SUMMARY_TASK, LLMTaskScheduler, get_llm_task_scheduler


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
        task_scheduler: LLMTaskScheduler | None = None,
    ) -> None:
        """初始化摘要服务。"""

        self.config = config
        self.message_service = message_service or MessageService(config=config)
        self.memory_service = memory_service or LongTermMemoryService(config=config)
        self.embedding_service = embedding_service or EmbeddingService(config=config)
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.important_fact_summary_service = ImportantFactSummaryService(
            config=config,
            memory_service=self.memory_service,
            embedding_service=self.embedding_service,
            task_scheduler=self.task_scheduler,
        )
        self.memory_resolver = MemoryResolver(
            config=config,
            memory_service=self.memory_service,
            embedding_service=self.embedding_service,
            task_scheduler=self.task_scheduler,
        )

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
        message_ids = [message.message_id for message in messages]
        summary_memory = self.important_fact_summary_service.persist_summary_memory(
            user_id=user_id,
            session_id=session_id,
            summary_text=summary,
            memory_type="session_summary",
            source_type="session_messages",
            source_id=session_id,
            source_hash=self._hash_message_ids(message_ids),
            source_range_json={"message_ids": message_ids},
            metadata_json={"message_count": len(messages)},
            importance=0.7,
            authority=0.5,
        )
        if summary_memory is None:
            self.message_service.mark_messages_summarized(message_ids=message_ids)
            return summary
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
        return self.important_fact_summary_service.summarize_text(
            task_type=BACKGROUND_SUMMARY_TASK,
            transcript=transcript,
            mode="summary",
        )

    @staticmethod
    def _hash_message_ids(message_ids: Sequence[str]) -> str:
        """
        根据消息 ID 列表生成摘要来源哈希。

        message_ids: 被摘要覆盖的消息 ID。
        """

        return hashlib.sha256("|".join(message_ids).encode("utf-8")).hexdigest()
