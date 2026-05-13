"""
重要事实摘要服务。

功能说明:
本文件实现 `ImportantFactSummaryService`,负责把长对话或工作上下文压缩成“后续推理仍然
有用”的重要事实摘要。该服务同时提供:

1. 小模型摘要:
   使用统一调度器把摘要任务路由到 `small` 模型池,避免挤占主推理大模型配额。
2. 长期记忆落库:
   将压缩后的摘要写入统一长期记忆表,供后续 `ContextBuilder` 和检索链路复用。

使用说明:
service = ImportantFactSummaryService(config=config, task_scheduler=scheduler)
summary = service.summarize_text(transcript="...", task_type="background_summary", mode="summary")
"""

from __future__ import annotations

import hashlib
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate, LongTermMemorySpecOut
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.task_schedule import LLMTaskScheduler, SMALL_MODEL_TIER, get_llm_task_scheduler


class ImportantFactSummaryService:
    """
    重要事实摘要服务。

    config: 全局配置对象。
    memory_service: 长期记忆服务,用于把摘要写入向量库。
    embedding_service: Embedding 服务,用于为摘要生成向量。
    task_scheduler: 统一调度器,用于通过小模型池执行摘要任务。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        memory_service: LongTermMemoryService | None = None,
        embedding_service: EmbeddingService | None = None,
        task_scheduler: LLMTaskScheduler | None = None,
    ) -> None:
        """初始化重要事实摘要服务依赖。"""

        self.config = config
        self.memory_service = memory_service or LongTermMemoryService(config=config)
        self.embedding_service = embedding_service or EmbeddingService(config=config)
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)

    def summarize_text(
        self,
        *,
        transcript: str,
        task_type: str,
        mode: str,
    ) -> str:
        """
        使用小模型将输入文本压缩为重要事实摘要。

        transcript: 需要压缩的工作上下文文本。
        task_type: 当前任务类型,用于复用调度器优先级和超时配置。
        mode: 摘要模式,支持 `summary` 与 `compress`。
        """

        normalized_transcript = transcript.strip()
        if not normalized_transcript:
            return ""
        response = self.task_scheduler.invoke_chat(
            task_type=task_type,
            model_tier=SMALL_MODEL_TIER,
            messages=[
                SystemMessage(content=self._build_system_prompt(mode=mode)),
                HumanMessage(content=normalized_transcript),
            ],
        )
        return str(response.content).strip()

    def persist_summary_memory(
        self,
        *,
        user_id: str,
        session_id: str,
        summary_text: str,
        memory_type: str,
        source_type: str,
        source_id: str,
        source_hash: str,
        source_range_json: dict[str, Any],
        metadata_json: dict[str, Any] | None = None,
        importance: float = 0.9,
        authority: float = 0.55,
    ) -> LongTermMemorySpecOut | None:
        """
        将重要事实摘要写入统一长期记忆表。

        user_id: 用户 ID。
        session_id: 会话 ID。
        summary_text: 已生成的重要事实摘要。
        memory_type: 长期记忆类型。
        source_type: 来源类型。
        source_id: 来源标识。
        source_hash: 用于摘要去重的稳定哈希。
        source_range_json: 来源范围元数据。
        metadata_json: 可选扩展元数据。
        importance: 摘要重要性评分。
        authority: 摘要权威性评分。
        """

        normalized_summary = summary_text.strip()
        if not normalized_summary:
            return None
        if self.memory_service.has_source_hash(source_hash=source_hash, memory_type=memory_type):
            return None
        vector = self.embedding_service.embed_text(normalized_summary)
        return self.memory_service.create_memory(
            LongTermMemorySpecCreate(
                user_id=user_id,
                session_id=session_id,
                tag=self.config.constants.memory_tag,
                memory_type=memory_type,
                content=normalized_summary,
                source_type=source_type,
                source_id=source_id,
                source_hash=source_hash,
                source_range_json=source_range_json,
                metadata_json=metadata_json or {},
                confidence=0.85,
                importance=importance,
                authority=authority,
                embedding_model=self.config.model.embedding_model_name,
                embedding_vector_json=vector,
            )
        )

    @staticmethod
    def build_hash(*parts: str) -> str:
        """
        根据多个文本片段生成稳定哈希。

        parts: 需要参与哈希的文本片段。
        """

        normalized = "|".join(part.strip() for part in parts if part.strip())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _build_system_prompt(self, *, mode: str) -> str:
        """
        根据摘要模式返回最终系统提示词。

        mode: 摘要模式,支持 `summary` 与 `compress`。
        """

        if mode == "compress":
            return (
                f"{self.config.model.important_fact_summary_system_prompt}"
                "当前任务是上下文压缩。"
                "输出必须直接帮助后续继续对话或继续工具推理。"
                "请优先保留当前有效事实、旧值是否失效、当前问题、最近决策和未完成事项。"
            )
        return (
            f"{self.config.model.important_fact_summary_system_prompt}"
            "当前任务是会话长期记忆摘要。"
            "请保留对未来轮次仍有价值的稳定事实和约束。"
        )
