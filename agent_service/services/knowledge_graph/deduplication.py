"""KnowledgeGraphService 的 deduplication 职责。

方法体由原服务机械迁移，业务行为不变。
"""

from __future__ import annotations
import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol
from langchain_core.messages import HumanMessage, SystemMessage
import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.core.db.engine import get_database_engine
from agent_service.models.knowledge_graph import (
    KnowledgeGraphDocumentStatus,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)
from agent_service.models.session import utc_now
from agent_service.services.memory.rag.frontmatter_document import (
    StructuredKnowledgeDocument,
    StructuredKnowledgeSection,
)
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.scheduler import (
    BACKGROUND_FACT_RESOLUTION_TASK,
    LLMTaskScheduler,
    SMALL_MODEL_TIER,
    get_llm_task_scheduler,
)
from agent_service.services.token_usage.service import TokenUsageService
from agent_service.services.knowledge_graph.service import (
    EntityCandidate, GraphExtractionResult, KnowledgeGraphExtractor,
    LLMKnowledgeGraphExtractor,
    RelationCandidate, StructuredKnowledgeDocument, StructuredKnowledgeSection,
)

logger = logging.getLogger(__name__)

class KnowledgeGraphDeduplicationMixin:
    def _deduplicate_entities_incremental(
        self,
        *,
        user_id: str,
        library_id: str,
        new_entities: list[EntityCandidate],
        extractor: LLMKnowledgeGraphExtractor,
        document: StructuredKnowledgeDocument,
    ) -> dict[str, str]:
        """增量去重: embedding 检索相似实体 → 小模型裁决同义 → 返回 name_mapping。"""

        if not isinstance(extractor, LLMKnowledgeGraphExtractor) or not new_entities:
            return {}
        candidates = self._search_similar_entities(
            user_id=user_id, library_id=library_id, new_entities=new_entities,
        )
        if not candidates:
            return {}
        return extractor.deduplicate_entities_incremental(
            entities=new_entities, candidates=candidates, document=document,
        )
    def _search_similar_entities(
        self,
        *,
        user_id: str,
        library_id: str,
        new_entities: list[EntityCandidate],
    ) -> dict[str, list[tuple[str, float]]]:
        """用 Embedding 搜索库中已有相似实体,返回 {新实体名: [(库中实体名, 相似度), ...]}。"""

        with Session(self.engine) as db:
            existing = db.exec(
                select(KnowledgeGraphNode.node_id, KnowledgeGraphNode.label)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.node_type == "entity")
            ).all()
        if not existing:
            return {}
        try:
            embedder = EmbeddingService(config=self.config)
            new_texts = [e.name for e in new_entities]
            existing_texts = [row.label for row in existing]
            new_vecs = embedder.embed_texts(new_texts)
            existing_vecs = embedder.embed_texts(existing_texts)
        except Exception:
            logger.warning("Embedding 不可用,跳过增量去重", exc_info=True)
            return {}

        results: dict[str, list[tuple[str, float]]] = {}
        for i, nv in enumerate(new_vecs):
            scores = []
            for j, ev in enumerate(existing_vecs):
                sim = self._cosine_similarity(nv, ev)
                if sim >= 0.55:
                    scores.append((existing_texts[j], sim))
            scores.sort(key=lambda x: x[1], reverse=True)
            if scores:
                results[new_entities[i].name] = scores[:10]
        return results
    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算余弦相似度。"""
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
    def full_dedup_library(
        self,
        *,
        user_id: str,
        library_id: str,
        llm_config: dict[str, Any] | None = None,
        eps: float = 0.5,
        min_samples: int = 2,
        max_cluster_size: int | None = None,
    ) -> int:
        """全库实体去重: Embedding 聚类 + 逐簇小模型去重。

        先用 Embedding 将全库实体向量化,再用 DBSCAN 按余弦距离聚出"语义密集团"。
        如果单个簇超过 max_cluster_size 则拆成子批次,避免一次喂给 LLM 太多实体。
        """

        max_cluster_size = max_cluster_size or self.config.limits.graph_dedup_max_cluster_size
        with Session(self.engine) as db:
            entity_rows = db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.node_type == "entity")
            ).all()

        if len(entity_rows) <= 1:
            _set_dedup_progress(user_id, library_id, "completed", 0, 0, "无需去重", 0)
            return 0

        _set_dedup_progress(user_id, library_id, "running", 0, 0, "正在生成 Embedding…", 0)

        # 生成全部实体的嵌入向量
        embedder = EmbeddingService(config=self.config)
        all_labels = [row.label for row in entity_rows]
        all_vectors = embedder.embed_texts(all_labels)  # list[list[float]]

        # DBSCAN 聚类 (余弦距离)
        matrix = np.array(all_vectors, dtype=np.float64)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit(matrix)
        cluster_labels = clustering.labels_

        # 按簇分组,跳过噪声点(簇标签 -1); 超大簇拆成子批次
        raw_clusters: dict[int, list[tuple[str, KnowledgeGraphNode]]] = {}
        for label, entity_label, row in zip(cluster_labels, all_labels, entity_rows):
            if label == -1:
                continue
            raw_clusters.setdefault(label, []).append((entity_label, row))

        batches: list[list[tuple[str, KnowledgeGraphNode]]] = []
        for items in raw_clusters.values():
            for start in range(0, len(items), max_cluster_size):
                batches.append(items[start:start + max_cluster_size])

        total_batches = len(batches)
        _set_dedup_progress(user_id, library_id, "running", total_batches, 0,
                            f"聚类完成,共 {total_batches} 批需要处理", 0)

        extractor = LLMKnowledgeGraphExtractor(
            config=self.config,
            llm_config=llm_config,
            user_id=user_id,
            library_id=library_id,
        )
        dummy_doc = StructuredKnowledgeDocument(
            document_id="__full_dedup__", source_type="text", source_path="", source_uri="",
            source_hash="", title="【全库去重】", summary="", tags=[], authority=0.7,
            valid_from=None, valid_until=None, metadata={}, sections=[],
        )

        all_mapping: dict[str, str] = {}
        for idx, cluster_items in enumerate(batches, start=1):
            if len(cluster_items) <= 1:
                continue
            batch = [
                EntityCandidate(
                    name=label,
                    entity_type=row.entity_type,
                    aliases=row.metadata_json.get("aliases", []) if row.metadata_json else [],
                    description="",
                    confidence=row.metadata_json.get("confidence", 0.7) if row.metadata_json else 0.7,
                )
                for label, row in cluster_items
            ]
            _set_dedup_progress(user_id, library_id, "running", total_batches, idx,
                                f"正在处理第 {idx}/{total_batches} 批 ({len(batch)} 个实体)", 0)
            result = extractor.deduplicate_entities(batch, document=dummy_doc)
            name_mapping = result.get("name_mapping", {}) or {}
            for src, dst in name_mapping.items():
                all_mapping[src] = dst

        if not all_mapping:
            _set_dedup_progress(user_id, library_id, "completed", total_batches, total_batches, "未发现同义实体", 0)
            return 0

        _set_dedup_progress(user_id, library_id, "running", total_batches, total_batches, "正在更新数据库…", 0)

        # ----------------------------------------------------------------
        # 以下 DB 更新逻辑与原实现一致 (链式映射 + 重定向边 + 清理自环)
        # ----------------------------------------------------------------
        label_map: dict[str, str] = {}
        seen_labels: set[str] = set()
        for src, dst in all_mapping.items():
            if src == dst:
                continue
            resolved = dst
            visited = {src}
            while resolved in all_mapping and resolved != all_mapping[resolved]:
                if resolved in visited:
                    resolved = dst
                    break
                visited.add(resolved)
                resolved = all_mapping[resolved]
            label_map[src] = resolved
            seen_labels.add(src)
            seen_labels.add(resolved)

        with Session(self.engine) as db:
            for src_label, dst_label in label_map.items():
                src_rows = db.exec(
                    select(KnowledgeGraphNode)
                    .where(KnowledgeGraphNode.user_id == user_id)
                    .where(KnowledgeGraphNode.library_id == library_id)
                    .where(KnowledgeGraphNode.node_type == "entity")
                    .where(KnowledgeGraphNode.label == src_label)
                ).all()
                dst_rows = db.exec(
                    select(KnowledgeGraphNode)
                    .where(KnowledgeGraphNode.user_id == user_id)
                    .where(KnowledgeGraphNode.library_id == library_id)
                    .where(KnowledgeGraphNode.node_type == "entity")
                    .where(KnowledgeGraphNode.label == dst_label)
                ).all()
                if not src_rows or not dst_rows:
                    continue
                src_node = src_rows[0]
                dst_node = dst_rows[0]
                if src_node.node_id == dst_node.node_id:
                    continue
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_node_id == src_node.node_id)
                ).all():
                    edge.source_node_id = dst_node.node_id
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.target_node_id == src_node.node_id)
                ).all():
                    edge.target_node_id = dst_node.node_id
                db.delete(src_node)
            for edge in db.exec(
                select(KnowledgeGraphEdge)
                .where(KnowledgeGraphEdge.user_id == user_id)
                .where(KnowledgeGraphEdge.library_id == library_id)
                .where(KnowledgeGraphEdge.source_node_id == KnowledgeGraphEdge.target_node_id)
            ).all():
                db.delete(edge)
            db.commit()
        merged = len(label_map)
        _set_dedup_progress(user_id, library_id, "completed", total_batches, total_batches,
                            f"去重完成,合并了 {merged} 个实体", merged)
        return merged
