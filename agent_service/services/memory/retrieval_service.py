"""
统一长期记忆检索服务。

功能说明:
本文件实现第一版 Memory/Knowledge 统一召回链路。它负责根据当前 query 生成
Embedding,优先使用 pgvector 做向量召回,在不可用时回退到 JSON 向量字段的
Python 余弦相似度计算,然后按相关性、时效性和权威性做联合排序。

使用说明:
service = MemoryRetrievalService(config=config)
memories = service.retrieve_long_term_memory(query="项目代号是什么", user_id="u1", session_id="s1")
knowledge = service.retrieve_knowledge(query="什么是海洋酸化")
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.longterm_memory_spec import LongTermMemorySpec
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecOut
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService


@dataclass(slots=True)
class RetrievedMemory:
    """
    检索结果结构。

    memory: 长期记忆输出 DTO。
    relevance_score: 向量相似度得分。
    freshness_score: 时效性得分。
    final_score: 联合排序得分。
    """

    memory: LongTermMemorySpecOut
    relevance_score: float
    freshness_score: float
    final_score: float
    current_session_match: bool = False


class MemoryRetrievalService:
    """
    统一长期记忆检索服务。

    config: 全局配置对象,用于读取 top_k 和排序权重。
    embedding_service: 可选 Embedding 服务,测试时可注入假向量生成器。
    memory_service: 可选长期记忆服务,用于复用同一数据库引擎和 pgvector 状态。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        embedding_service: EmbeddingService | None = None,
        memory_service: LongTermMemoryService | None = None,
    ) -> None:
        """初始化检索服务。"""

        self.config = config
        self.embedding_service = embedding_service or EmbeddingService(config=config)
        self.memory_service = memory_service or LongTermMemoryService(config=config)
        self.engine: Engine = self.memory_service.engine

    def retrieve_long_term_memory(
        self,
        *,
        query: str,
        user_id: str,
        session_id: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedMemory]:
        """
        检索用户长期记忆摘要。

        query: 当前查询文本。
        user_id: 用户 ID。
        session_id: 可选 session ID,用于在跨 session 召回后给当前会话记忆更高排序优先级。
        top_k: 可选返回条数。
        """

        fact_memories = self._retrieve(
            query=query,
            user_id=user_id,
            session_id=session_id,
            tag=self.config.constants.memory_tag,
            memory_type="session_fact",
            top_k=top_k,
        )
        if fact_memories:
            return fact_memories
        return self._retrieve(
            query=query,
            user_id=user_id,
            session_id=session_id,
            tag=self.config.constants.memory_tag,
            memory_type="session_summary",
            top_k=top_k,
        )

    def retrieve_knowledge(self, *, query: str, top_k: int | None = None) -> list[RetrievedMemory]:
        """
        检索知识库切片。

        query: 当前查询文本。
        top_k: 可选返回条数。
        """

        return self._retrieve(
            query=query,
            user_id="system",
            session_id=None,
            tag=self.config.constants.knowledge_tag,
            memory_type="knowledge_chunk",
            top_k=top_k,
        )

    def get_latest_session_summary(self, *, user_id: str, session_id: str) -> RetrievedMemory | None:
        """
        获取当前会话最近一条摘要记忆,用于同 session 的保底注入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.tag == self.config.constants.memory_tag)
            .where(LongTermMemorySpec.memory_type == "session_summary")
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.session_id == session_id)
            .order_by(LongTermMemorySpec.updated_at.desc())
            .limit(1)
        )
        with Session(self.engine) as db_session:
            record = db_session.exec(statement).first()
        if record is None:
            return None
        memory = LongTermMemorySpecOut.from_record(record)
        now = datetime.now(timezone.utc)
        retrieved = RetrievedMemory(
            memory=memory,
            relevance_score=1.0,
            freshness_score=self._freshness_score(memory, now=now),
            final_score=0.0,
            current_session_match=True,
        )
        retrieved.final_score = self._final_score(retrieved)
        return retrieved

    def _retrieve(
        self,
        *,
        query: str,
        user_id: str,
        session_id: str | None,
        tag: str,
        memory_type: str,
        top_k: int | None,
    ) -> list[RetrievedMemory]:
        """
        执行统一检索。

        query: 当前查询文本。
        user_id: 用户 ID。
        session_id: 可选会话 ID,用于在用户级跨 session 召回后标记当前会话优先级。
        tag: Memory 或 Knowledge。
        memory_type: 记忆子类型。
        top_k: 返回条数。
        """

        normalized_query = query.strip()
        if not normalized_query:
            return []
        final_top_k = top_k or self.config.memory.rerank_top_k
        query_vector = self.embedding_service.embed_text(normalized_query)
        if not query_vector:
            return []
        candidates = self._retrieve_by_pgvector(
            query_vector=query_vector,
            user_id=user_id,
            session_id=session_id,
            tag=tag,
            memory_type=memory_type,
            limit=max(final_top_k, self.config.memory.vector_top_k),
        )
        if not candidates:
            candidates = self._retrieve_by_json_vectors(
                query_vector=query_vector,
                user_id=user_id,
                session_id=session_id,
                tag=tag,
                memory_type=memory_type,
                limit=max(final_top_k, self.config.memory.vector_top_k),
            )
        now = datetime.now(timezone.utc)
        ranked = sorted(
            (
                RetrievedMemory(
                    memory=item["memory"],
                    relevance_score=item["relevance_score"],
                    freshness_score=self._freshness_score(item["memory"], now=now),
                    final_score=0.0,
                    current_session_match=bool(session_id and item["memory"].session_id == session_id),
                )
                for item in candidates
            ),
            key=self._rank_key,
            reverse=True,
        )
        for item in ranked:
            item.final_score = self._final_score(item)
        ranked = [item for item in ranked if item.final_score >= self.config.memory.score_threshold]
        return ranked[:final_top_k]

    def _retrieve_by_pgvector(
        self,
        *,
        query_vector: list[float],
        user_id: str,
        session_id: str | None,
        tag: str,
        memory_type: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        使用 pgvector 向量列检索候选记忆。

        query_vector: 查询向量。
        user_id: 用户 ID。
        session_id: 可选会话 ID,仅用于标记当前会话匹配,不再限制跨 session 召回范围。
        tag: 记忆大类。
        memory_type: 记忆子类型。
        limit: 候选数量上限。
        """

        self.memory_service.ensure_pgvector_storage(vector_dimension=len(query_vector))
        if not self.engine.dialect.name.startswith("postgresql") or self.memory_service.pgvector_available is False:
            return []
        where_clauses = [
            "tag = :tag",
            "memory_type = :memory_type",
            "user_id = :user_id",
            "(valid_until IS NULL OR valid_until >= NOW())",
        ]
        parameters: dict[str, Any] = {
            "tag": tag,
            "memory_type": memory_type,
            "user_id": user_id,
            "query_vector": json.dumps(query_vector, separators=(",", ":")),
            "limit": limit,
        }
        sql = text(
            "SELECT memory_id, (1 - (embedding_vector <=> CAST(:query_vector AS vector))) AS relevance_score "
            "FROM longterm_memory_specs "
            f"WHERE {' AND '.join(where_clauses)} "
            "AND embedding_vector IS NOT NULL "
            "ORDER BY embedding_vector <=> CAST(:query_vector AS vector) "
            "LIMIT :limit"
        )
        with self.engine.begin() as connection:
            rows = list(connection.execute(sql, parameters).mappings())
        if not rows:
            return []
        memory_ids = [row["memory_id"] for row in rows]
        with Session(self.engine) as db_session:
            statement = select(LongTermMemorySpec).where(LongTermMemorySpec.memory_id.in_(memory_ids))
            records = db_session.exec(statement).all()
        record_map = {record.memory_id: LongTermMemorySpecOut.from_record(record) for record in records}
        return [
            {
                "memory": record_map[row["memory_id"]],
                "relevance_score": self._clamp_score(float(row["relevance_score"] or 0.0)),
            }
            for row in rows
            if row["memory_id"] in record_map and self._is_memory_currently_active(record_map[row["memory_id"]])
        ]

    def _retrieve_by_json_vectors(
        self,
        *,
        query_vector: list[float],
        user_id: str,
        session_id: str | None,
        tag: str,
        memory_type: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        使用 JSON 向量字段回退检索候选记忆。

        query_vector: 查询向量。
        user_id: 用户 ID。
        session_id: 可选会话 ID,仅用于保持函数签名一致,不限制跨 session 候选集。
        tag: 记忆大类。
        memory_type: 记忆子类型。
        limit: 候选数量上限。
        """

        now = datetime.now(timezone.utc)
        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.tag == tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .where(LongTermMemorySpec.user_id == user_id)
            .order_by(LongTermMemorySpec.updated_at.desc())
        )
        with Session(self.engine) as db_session:
            records = db_session.exec(statement).all()
        scored: list[dict[str, Any]] = []
        for record in records:
            if record.valid_until is not None and record.valid_until < now:
                continue
            if not record.embedding_vector_json:
                continue
            memory = LongTermMemorySpecOut.from_record(record)
            if not self._is_memory_currently_active(memory):
                continue
            scored.append(
                {
                    "memory": memory,
                    "relevance_score": self._cosine_similarity(query_vector, record.embedding_vector_json),
                }
            )
        scored.sort(key=lambda item: item["relevance_score"], reverse=True)
        return scored[:limit]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        """
        计算两组向量的余弦相似度。

        left: 左向量。
        right: 右向量。
        """

        if len(left) != len(right) or not left or not right:
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return MemoryRetrievalService._clamp_score((numerator / (left_norm * right_norm) + 1.0) / 2.0)

    def _final_score(self, item: RetrievedMemory) -> float:
        """
        计算相关性、时效性和权威性的联合得分。

        item: 检索结果。
        """

        return self._clamp_score(
            self.config.memory.relevance_weight * item.relevance_score
            + self.config.memory.freshness_weight * item.freshness_score
            + self.config.memory.authority_weight * item.memory.authority
        )

    def _rank_key(self, item: RetrievedMemory) -> tuple[float, int, datetime, float, float]:
        """
        返回联合排序键。

        item: 检索结果。
        """

        final_score = self._final_score(item)
        return final_score, int(item.current_session_match), item.memory.updated_at, item.relevance_score, item.memory.importance

    @staticmethod
    def _freshness_score(memory: LongTermMemorySpecOut, *, now: datetime) -> float:
        """
        计算记忆时效性得分。

        memory: 长期记忆记录。
        now: 当前时间。
        """

        updated_at = memory.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_days = max((now - updated_at).total_seconds() / 86400.0, 0.0)
        return 1.0 / (1.0 + age_days / 30.0)

    @staticmethod
    def _is_memory_currently_active(memory: LongTermMemorySpecOut) -> bool:
        """
        判断长期记忆当前是否仍应参与召回。
        memory: 长期记忆输出记录。
        """

        if memory.valid_until is not None and memory.valid_until <= datetime.now(timezone.utc):
            return False
        fact_status = memory.metadata_json.get("fact_status")
        if fact_status in {"superseded", "expired", "deleted"}:
            return False
        fact = memory.metadata_json.get("fact")
        if isinstance(fact, dict) and fact.get("status") in {"superseded", "expired", "deleted"}:
            return False
        return True

    @staticmethod
    def _clamp_score(value: float) -> float:
        """
        将得分裁剪到 0 到 1。

        value: 原始得分。
        """

        return max(0.0, min(1.0, value))
