"""
混合检索服务。

功能说明:
本文件实现 README 要求的“多路召回”第一层能力,把向量检索结果与关键词检索结果
合并为统一候选集。该服务本身不依赖具体的向量检索实现,而是专注于:
1. 对 query 做稳定的关键词抽取。
2. 在统一长期记忆表中执行关键词召回。
3. 将“向量召回候选”和“关键词召回候选”去重合并,产出可交给 ReRank 的候选集。

使用说明:
service = HybridRetrievalService(config=config, engine=engine)
keyword_candidates = service.retrieve_keyword_candidates(...)
merged_candidates = service.merge_candidates(
    vector_candidates=vector_candidates,
    keyword_candidates=keyword_candidates,
    session_id="sess_1",
)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

from sqlalchemy import or_
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.longterm_memory_spec import LongTermMemorySpec
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecOut


@dataclass(slots=True)
class HybridRetrievalCandidate:
    """
    混合检索候选项。

    memory: 统一长期记忆输出 DTO。
    vector_score: 向量召回分数,范围 0 到 1。
    keyword_score: 关键词召回分数,范围 0 到 1。
    merged_score: 混合召回后的基础分数,范围 0 到 1。
    rerank_score: ReRank 分数;未经过 ReRank 时为空。
    matched_terms: 关键词检索命中的关键词列表。
    source_channels: 命中的召回通道,例如 `("vector", "keyword")`。
    current_session_match: 是否命中当前 session。
    """

    memory: LongTermMemorySpecOut
    vector_score: float = 0.0
    keyword_score: float = 0.0
    merged_score: float = 0.0
    rerank_score: float | None = None
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    source_channels: tuple[str, ...] = field(default_factory=tuple)
    current_session_match: bool = False


class HybridRetrievalService:
    """
    混合检索服务。

    config: 全局配置对象,用于读取关键词召回数量与排序参数。
    engine: 长期记忆数据库引擎。
    """

    ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.-]{2,}")
    CJK_SEQUENCE_PATTERN = re.compile("[一-鿿]{2,}")
    CJK_STOPWORDS = {
        "什么",
        "怎么",
        "请问",
        "一下",
        "一下子",
        "是否",
        "以及",
        "当前",
        "这个",
        "那个",
        "这里",
        "那里",
        "已经",
        "还有",
        "然后",
        "因为",
        "所以",
        "但是",
        "如果",
        "我们",
        "你们",
        "他们",
        "用户",
        "回答",
        "问题",
        "一下",
        "现在",
        "就是",
    }

    def __init__(self, *, config: AgentConfig, engine: Engine) -> None:
        """保存配置与数据库引擎。"""

        self.config = config
        self.engine = engine

    def retrieve_keyword_candidates(
        self,
        *,
        query: str,
        user_id: str,
        session_id: str | None,
        tag: str,
        memory_type: str,
        limit: int,
    ) -> list[HybridRetrievalCandidate]:
        """
        按关键词召回长期记忆候选。

        query: 当前用户问题。
        user_id: 记忆所属用户 ID。
        session_id: 当前 session ID,用于标记候选优先级。
        tag: 记忆大类。
        memory_type: 记忆子类型。
        limit: 召回数量上限。
        """

        normalized_query = query.strip()
        if not normalized_query:
            return []
        keywords = self.extract_keywords(normalized_query)
        if not keywords:
            return []
        records = self._select_keyword_candidate_records(
            user_id=user_id,
            tag=tag,
            memory_type=memory_type,
            keywords=keywords,
            limit=limit,
        )
        scored: list[HybridRetrievalCandidate] = []
        for record in records:
            memory = LongTermMemorySpecOut.from_record(record)
            if not self.is_memory_currently_active(memory):
                continue
            score, matched_terms = self._keyword_score(memory.content, keywords)
            if score <= 0.0:
                continue
            scored.append(
                HybridRetrievalCandidate(
                    memory=memory,
                    keyword_score=score,
                    merged_score=score,
                    matched_terms=matched_terms,
                    source_channels=("keyword",),
                    current_session_match=bool(session_id and memory.session_id == session_id),
                )
            )
        scored.sort(
            key=lambda item: (
                item.keyword_score,
                int(item.current_session_match),
                self._ensure_aware_datetime(item.memory.updated_at)
                or datetime.min.replace(tzinfo=timezone.utc),
                item.memory.importance,
            ),
            reverse=True,
        )
        return scored[:limit]

    def merge_candidates(
        self,
        *,
        vector_candidates: list[HybridRetrievalCandidate],
        keyword_candidates: list[HybridRetrievalCandidate],
        session_id: str | None,
    ) -> list[HybridRetrievalCandidate]:
        """
        合并向量召回与关键词召回候选并去重。

        vector_candidates: 向量召回结果。
        keyword_candidates: 关键词召回结果。
        session_id: 当前 session ID,用于标记当前会话命中。
        """

        merged_map: dict[str, HybridRetrievalCandidate] = {}
        for candidate in vector_candidates:
            merged_map[candidate.memory.memory_id] = HybridRetrievalCandidate(
                memory=candidate.memory,
                vector_score=self._clamp_score(candidate.vector_score),
                keyword_score=0.0,
                merged_score=self._clamp_score(candidate.vector_score),
                matched_terms=tuple(candidate.matched_terms),
                source_channels=("vector",),
                current_session_match=bool(session_id and candidate.memory.session_id == session_id),
            )
        for candidate in keyword_candidates:
            existing = merged_map.get(candidate.memory.memory_id)
            if existing is None:
                merged_map[candidate.memory.memory_id] = HybridRetrievalCandidate(
                    memory=candidate.memory,
                    vector_score=0.0,
                    keyword_score=self._clamp_score(candidate.keyword_score),
                    merged_score=self._clamp_score(candidate.keyword_score),
                    matched_terms=tuple(candidate.matched_terms),
                    source_channels=("keyword",),
                    current_session_match=bool(session_id and candidate.memory.session_id == session_id),
                )
                continue
            existing.keyword_score = self._clamp_score(candidate.keyword_score)
            existing.matched_terms = tuple(sorted(set(existing.matched_terms) | set(candidate.matched_terms)))
            existing.source_channels = ("vector", "keyword")
        merged = list(merged_map.values())
        for candidate in merged:
            candidate.merged_score = self._compute_merged_score(candidate)
        merged.sort(
            key=lambda item: (
                item.merged_score,
                int(item.current_session_match),
                len(item.source_channels),
                self._ensure_aware_datetime(item.memory.updated_at)
                or datetime.min.replace(tzinfo=timezone.utc),
                item.memory.importance,
            ),
            reverse=True,
        )
        return merged

    @classmethod
    def extract_keywords(cls, query: str, *, max_keywords: int = 12) -> list[str]:
        """
        从 query 中抽取适合关键词召回的 token。

        query: 当前用户问题。
        max_keywords: 最多保留的关键词数。
        """

        keywords: set[str] = set()
        normalized = query.strip().lower()
        for token in cls.ASCII_TOKEN_PATTERN.findall(normalized):
            keywords.add(token)
        for sequence in cls.CJK_SEQUENCE_PATTERN.findall(normalized):
            if sequence not in cls.CJK_STOPWORDS:
                keywords.add(sequence)
            for size in range(min(4, len(sequence)), 1, -1):
                for start in range(0, len(sequence) - size + 1):
                    fragment = sequence[start : start + size]
                    if fragment in cls.CJK_STOPWORDS:
                        continue
                    keywords.add(fragment)
        ranked_keywords = sorted(keywords, key=lambda item: (-len(item), item))
        return ranked_keywords[:max_keywords]

    def _select_keyword_candidate_records(
        self,
        *,
        user_id: str,
        tag: str,
        memory_type: str,
        keywords: list[str],
        limit: int,
    ) -> list[LongTermMemorySpec]:
        """
        先用 SQL 做一次轻量预筛,再返回可参与 Python 打分的候选记录。

        user_id: 记忆所属用户 ID。
        tag: 记忆大类。
        memory_type: 记忆子类型。
        keywords: 已抽取的关键词列表。
        limit: 最终召回数量上限。
        """

        scan_limit = max(limit * 10, 50)
        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.tag == tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .where(LongTermMemorySpec.user_id == user_id)
            .order_by(LongTermMemorySpec.updated_at.desc())
            .limit(scan_limit)
        )
        strongest_terms = keywords[: min(len(keywords), 8)]
        if strongest_terms:
            statement = statement.where(
                or_(*[LongTermMemorySpec.content.ilike(f"%{term}%") for term in strongest_terms])
            )
        with Session(self.engine) as db_session:
            records = db_session.exec(statement).all()
        if records:
            return records
        fallback_statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.tag == tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .where(LongTermMemorySpec.user_id == user_id)
            .order_by(LongTermMemorySpec.updated_at.desc())
            .limit(scan_limit)
        )
        with Session(self.engine) as db_session:
            return db_session.exec(fallback_statement).all()

    @classmethod
    def _keyword_score(cls, content: str, keywords: list[str]) -> tuple[float, tuple[str, ...]]:
        """
        为单条正文计算关键词匹配分数。

        content: 候选记忆正文。
        keywords: query 关键词列表。
        """

        normalized_content = content.lower()
        matched_terms: list[str] = []
        total_weight = 0.0
        matched_weight = 0.0
        for keyword in keywords:
            weight = min(max(len(keyword), 2), 6) / 6.0
            total_weight += weight
            if keyword not in normalized_content:
                continue
            matched_terms.append(keyword)
            occurrences = normalized_content.count(keyword)
            matched_weight += weight + min(occurrences - 1, 2) * 0.08 * weight
        if total_weight == 0.0 or not matched_terms:
            return 0.0, ()
        coverage_score = matched_weight / total_weight
        phrase_bonus = min(len(matched_terms), 4) * 0.03
        return cls._clamp_score(coverage_score + phrase_bonus), tuple(matched_terms)

    @classmethod
    def is_memory_currently_active(cls, memory: LongTermMemorySpecOut) -> bool:
        """
        判断记忆当前是否仍可参与召回。

        memory: 统一长期记忆输出 DTO。
        """

        valid_until = cls._ensure_aware_datetime(memory.valid_until)
        if valid_until is not None and valid_until <= datetime.now(timezone.utc):
            return False
        fact_status = memory.metadata_json.get("fact_status")
        if fact_status in {"superseded", "expired", "deleted"}:
            return False
        fact = memory.metadata_json.get("fact")
        if isinstance(fact, dict) and fact.get("status") in {"superseded", "expired", "deleted"}:
            return False
        return True

    @classmethod
    def _compute_merged_score(cls, candidate: HybridRetrievalCandidate) -> float:
        """
        计算混合召回基础分。

        candidate: 已聚合的混合召回候选。
        """

        if candidate.vector_score > 0.0 and candidate.keyword_score > 0.0:
            dual_channel_bonus = 0.05
            merged = 0.6 * max(candidate.vector_score, candidate.keyword_score) + 0.4 * (
                candidate.vector_score + candidate.keyword_score
            ) / 2.0
            return cls._clamp_score(merged + dual_channel_bonus)
        return cls._clamp_score(max(candidate.vector_score, candidate.keyword_score))

    @staticmethod
    def _ensure_aware_datetime(value: datetime | None) -> datetime | None:
        """
        将数据库时间统一规范为 UTC aware datetime。

        value: 可能无时区的数据库时间。
        """

        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _clamp_score(value: float) -> float:
        """
        将分数裁剪到 0 到 1。

        value: 原始分数。
        """

        return max(0.0, min(1.0, value))
