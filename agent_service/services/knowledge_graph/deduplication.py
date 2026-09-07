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
    KnowledgeGraphDedupDecision,
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
    _DEDUP_ADJUDICATOR_VERSION = "remote-dedup-v1"

    def _deduplicate_entities_local(
        self,
        entities: list[EntityCandidate],
    ) -> tuple[list[EntityCandidate], dict[str, str]]:
        """按规范名称和显式别名在本地合并实体，不调用任何模型。"""

        if len(entities) <= 1:
            return list(entities), {entity.name: entity.name for entity in entities}
        parent = list(range(len(entities)))

        def find(index: int) -> int:
            """返回并压缩当前实体所属集合根节点。"""

            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            """合并两个由名称或显式别名确认相同的实体集合。"""

            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        names_by_type: dict[tuple[str, str], int] = {}
        for index, entity in enumerate(entities):
            names_by_type[(self._normalize_label(entity.name), entity.entity_type)] = index
        for index, entity in enumerate(entities):
            for alias in entity.aliases:
                match = names_by_type.get((self._normalize_label(alias), entity.entity_type))
                if match is not None:
                    union(index, match)

        groups: dict[int, list[EntityCandidate]] = {}
        for index, entity in enumerate(entities):
            groups.setdefault(find(index), []).append(entity)
        merged: list[EntityCandidate] = []
        mapping: dict[str, str] = {}
        for members in groups.values():
            canonical = max(members, key=lambda item: (item.confidence, -len(item.name)))
            aliases = list(dict.fromkeys(
                alias
                for member in members
                for alias in (member.name, *member.aliases)
                if self._normalize_label(alias) != self._normalize_label(canonical.name)
            ))[:5]
            canonical.aliases = aliases
            merged.append(canonical)
            mapping.update({member.name: canonical.name for member in members})
        return merged, mapping

    def _deduplicate_document_entities_layered(
        self,
        *,
        user_id: str,
        library_id: str,
        entities: list[EntityCandidate],
        extractor: Any,
        document: StructuredKnowledgeDocument,
    ) -> tuple[list[EntityCandidate], dict[str, str], bool]:
        """先做名称别名合并，再对跨章节实体执行本地 Embedding 灰区分流。"""

        merged, mapping = self._deduplicate_entities_local(entities)
        if len(merged) <= 1 or not hasattr(extractor, "remote_adjudicator"):
            return merged, mapping, False
        try:
            vectors = EmbeddingService(config=self.config).embed_texts([entity.name for entity in merged])
        except Exception:
            logger.warning("文档内实体 Embedding 不可用，保留名称与别名去重结果", exc_info=True)
            return merged, mapping, False

        high_threshold = float(self.config.limits.graph_dedup_high_similarity)
        gray_threshold = float(self.config.limits.graph_dedup_gray_similarity)
        cached = self._load_dedup_decisions(user_id=user_id, library_id=library_id)
        decisions: list[KnowledgeGraphDedupDecision] = []
        gray_pairs: list[tuple[EntityCandidate, EntityCandidate, float]] = []
        for left_index, left in enumerate(merged):
            for right_index in range(left_index + 1, len(merged)):
                right = merged[right_index]
                if left.entity_type != right.entity_type:
                    continue
                similarity = self._cosine_similarity(vectors[left_index], vectors[right_index])
                decision_id = self._dedup_decision_id(
                    user_id=user_id,
                    library_id=library_id,
                    left_label=left.name,
                    right_label=right.name,
                    entity_type=left.entity_type,
                )
                prior = cached.get(decision_id)
                if prior and prior.adjudicator_version == self._DEDUP_ADJUDICATOR_VERSION and prior.decision != "pending":
                    if prior.decision == "merge" and prior.canonical_label:
                        source = right.name if prior.canonical_label == left.name else left.name
                        mapping[source] = prior.canonical_label
                    continue
                if similarity >= high_threshold:
                    canonical, source = (left, right) if left.confidence >= right.confidence else (right, left)
                    mapping[source.name] = canonical.name
                    decisions.append(self._build_dedup_decision(
                        user_id=user_id,
                        library_id=library_id,
                        left_label=left.name,
                        right_label=right.name,
                        entity_type=left.entity_type,
                        decision="merge",
                        canonical_label=canonical.name,
                        similarity=similarity,
                    ))
                elif similarity >= gray_threshold:
                    gray_pairs.append((left, right, similarity))

        remote_pending = bool(gray_pairs)
        adjudicator = getattr(extractor, "remote_adjudicator", None)
        if gray_pairs and adjudicator is not None:
            gray_entities = {entity.name: entity for pair in gray_pairs for entity in pair[:2]}
            try:
                result = adjudicator.deduplicate_entities(list(gray_entities.values()), document=document)
                remote_mapping = dict(result.get("name_mapping", {}) or {})
                for left, right, similarity in gray_pairs:
                    left_target = self._normalize_label(remote_mapping.get(left.name, left.name))
                    right_target = self._normalize_label(remote_mapping.get(right.name, right.name))
                    should_merge = left_target == right_target
                    canonical = left.name if should_merge else ""
                    if should_merge:
                        mapping[right.name] = canonical
                    decisions.append(self._build_dedup_decision(
                        user_id=user_id,
                        library_id=library_id,
                        left_label=left.name,
                        right_label=right.name,
                        entity_type=left.entity_type,
                        decision="merge" if should_merge else "separate",
                        canonical_label=canonical,
                        similarity=similarity,
                    ))
                remote_pending = False
            except Exception as exc:  # noqa: BLE001 - retain local mappings and mark only gray pairs pending
                logger.warning("文档内实体灰区裁决失败，保留本地去重结果 | error=%s", exc)
        if remote_pending:
            decisions.extend(
                self._build_dedup_decision(
                    user_id=user_id,
                    library_id=library_id,
                    left_label=left.name,
                    right_label=right.name,
                    entity_type=left.entity_type,
                    decision="pending",
                    canonical_label="",
                    similarity=similarity,
                )
                for left, right, similarity in gray_pairs
            )
        self._save_dedup_decisions(decisions)
        return merged, mapping, remote_pending

    def _deduplicate_entities_incremental(
        self,
        *,
        user_id: str,
        library_id: str,
        new_entities: list[EntityCandidate],
        extractor: Any,
        document: StructuredKnowledgeDocument,
        return_pending_status: bool = False,
    ) -> dict[str, str] | tuple[dict[str, str], bool]:
        """增量去重：本地处理明确相似度，仅把未缓存灰区交给联网裁决。"""

        if not new_entities:
            return ({}, False) if return_pending_status else {}
        candidates = self._search_similar_entities(
            user_id=user_id,
            library_id=library_id,
            new_entities=new_entities,
            exclude_document_id=document.document_id,
        )
        if not candidates:
            return ({}, False) if return_pending_status else {}
        high_threshold = float(self.config.limits.graph_dedup_high_similarity)
        gray_threshold = float(self.config.limits.graph_dedup_gray_similarity)
        mapping: dict[str, str] = {}
        gray_candidates: dict[str, list[tuple[str, float]]] = {}
        pending_decisions: list[KnowledgeGraphDedupDecision] = []
        entity_type_by_name = {entity.name: entity.entity_type for entity in new_entities}
        cached_decisions = self._load_dedup_decisions(user_id=user_id, library_id=library_id)
        for name, matches in candidates.items():
            compatible = [match for match in matches if match[2] == entity_type_by_name.get(name)]
            unresolved: list[tuple[str, float, str]] = []
            cached_merge = ""
            for label, score, entity_type in compatible:
                decision_id = self._dedup_decision_id(
                    user_id=user_id,
                    library_id=library_id,
                    left_label=name,
                    right_label=label,
                    entity_type=entity_type,
                )
                decision = cached_decisions.get(decision_id)
                if (
                    decision is None
                    or decision.adjudicator_version != self._DEDUP_ADJUDICATOR_VERSION
                    or decision.decision == "pending"
                ):
                    unresolved.append((label, score, entity_type))
                elif decision.decision == "merge":
                    cached_merge = decision.canonical_label
                    break
            if cached_merge:
                mapping[name] = cached_merge
                continue
            if unresolved and unresolved[0][1] >= high_threshold:
                label, score, entity_type = unresolved[0]
                mapping[name] = label
                pending_decisions.append(self._build_dedup_decision(
                    user_id=user_id,
                    library_id=library_id,
                    left_label=name,
                    right_label=label,
                    entity_type=entity_type,
                    decision="merge",
                    canonical_label=label,
                    similarity=score,
                ))
                continue
            gray = [(label, score) for label, score, _entity_type in unresolved if score >= gray_threshold]
            if gray:
                gray_candidates[name] = gray
        adjudicator = getattr(extractor, "remote_adjudicator", None)
        if adjudicator is None and isinstance(extractor, LLMKnowledgeGraphExtractor):
            adjudicator = extractor
        remote_pending = bool(gray_candidates)
        if gray_candidates and adjudicator is not None:
            try:
                adjudicated = adjudicator.deduplicate_entities_incremental(
                    entities=new_entities,
                    candidates=gray_candidates,
                    document=document,
                )
                for name, matches in gray_candidates.items():
                    selected = str(adjudicated.get(name) or "")
                    allowed = {self._normalize_label(label): label for label, _score in matches}
                    canonical = allowed.get(self._normalize_label(selected), "")
                    if canonical:
                        mapping[name] = canonical
                    entity_type = entity_type_by_name.get(name, "other")
                    pending_decisions.extend(
                        self._build_dedup_decision(
                            user_id=user_id,
                            library_id=library_id,
                            left_label=name,
                            right_label=label,
                            entity_type=entity_type,
                            decision="merge" if canonical == label else "separate",
                            canonical_label=canonical if canonical == label else "",
                            similarity=score,
                        )
                        for label, score in matches
                    )
                remote_pending = False
            except Exception as exc:  # noqa: BLE001 - local high-confidence mapping remains usable
                logger.warning("增量实体灰区裁决失败，保留本地去重结果 | error=%s", exc)
        if remote_pending:
            pending_decisions.extend(
                self._build_dedup_decision(
                    user_id=user_id,
                    library_id=library_id,
                    left_label=name,
                    right_label=label,
                    entity_type=entity_type_by_name.get(name, "other"),
                    decision="pending",
                    canonical_label="",
                    similarity=score,
                )
                for name, matches in gray_candidates.items()
                for label, score in matches
            )
        self._save_dedup_decisions(pending_decisions)
        return (mapping, remote_pending) if return_pending_status else mapping

    def _load_dedup_decisions(
        self,
        *,
        user_id: str,
        library_id: str,
    ) -> dict[str, KnowledgeGraphDedupDecision]:
        """一次读取当前知识库的既有实体对判定。"""

        with Session(self.engine) as db:
            rows = db.exec(
                select(KnowledgeGraphDedupDecision)
                .where(KnowledgeGraphDedupDecision.user_id == user_id)
                .where(KnowledgeGraphDedupDecision.library_id == library_id)
            ).all()
            return {row.decision_id: row for row in rows}

    def _save_dedup_decisions(self, decisions: list[KnowledgeGraphDedupDecision]) -> None:
        """原子保存本轮新增的明确或联网实体对判定。"""

        if not decisions:
            return
        with Session(self.engine) as db:
            for decision in decisions:
                db.merge(decision)
            db.commit()

    def _build_dedup_decision(
        self,
        *,
        user_id: str,
        library_id: str,
        left_label: str,
        right_label: str,
        entity_type: str,
        decision: str,
        canonical_label: str,
        similarity: float,
    ) -> KnowledgeGraphDedupDecision:
        """构造具有对称稳定 ID 的实体对判定记录。"""

        return KnowledgeGraphDedupDecision(
            decision_id=self._dedup_decision_id(
                user_id=user_id,
                library_id=library_id,
                left_label=left_label,
                right_label=right_label,
                entity_type=entity_type,
            ),
            user_id=user_id,
            library_id=library_id,
            left_label=left_label,
            right_label=right_label,
            entity_type=entity_type,
            decision=decision,
            canonical_label=canonical_label,
            similarity=max(0.0, min(1.0, similarity)),
            adjudicator_version=self._DEDUP_ADJUDICATOR_VERSION,
            updated_at=utc_now(),
        )

    def _dedup_decision_id(
        self,
        *,
        user_id: str,
        library_id: str,
        left_label: str,
        right_label: str,
        entity_type: str,
    ) -> str:
        """按规范化且与方向无关的实体对生成缓存 ID。"""

        left, right = sorted((self._normalize_label(left_label), self._normalize_label(right_label)))
        return self._hashed_id("kgdedup", user_id, library_id, entity_type, left, right)
    def _search_similar_entities(
        self,
        *,
        user_id: str,
        library_id: str,
        new_entities: list[EntityCandidate],
        exclude_document_id: str = "",
    ) -> dict[str, list[tuple[str, float, str]]]:
        """用本地 Embedding 搜索已有实体，返回名称、相似度和类型。"""

        with Session(self.engine) as db:
            existing = db.exec(
                select(KnowledgeGraphNode.node_id, KnowledgeGraphNode.label, KnowledgeGraphNode.entity_type)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.node_type == "entity")
            ).all()
            if exclude_document_id:
                other_edges = db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_document_id != exclude_document_id)
                ).all()
                other_node_ids = {
                    node_id
                    for edge in other_edges
                    for node_id in (edge.source_node_id, edge.target_node_id)
                }
                existing = [row for row in existing if row.node_id in other_node_ids]
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

        results: dict[str, list[tuple[str, float, str]]] = {}
        for i, nv in enumerate(new_vecs):
            scores = []
            for j, ev in enumerate(existing_vecs):
                sim = self._cosine_similarity(nv, ev)
                if sim >= float(self.config.limits.graph_dedup_gray_similarity):
                    scores.append((existing_texts[j], sim, existing[j].entity_type))
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
        """全库实体去重：Embedding 聚类后本地分流，仅裁决未缓存灰区。

        先用 Embedding 将全库实体向量化,再用 DBSCAN 按余弦距离聚出"语义密集团"。
        如果单个簇超过 max_cluster_size 则拆成子批次，避免灰区候选过大。
        """

        from agent_service.services.knowledge_graph.service import _set_dedup_progress

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
        vector_by_node_id = {row.node_id: vector for row, vector in zip(entity_rows, all_vectors)}

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

        from agent_service.services.knowledge_graph.service import _build_llm_config

        resolved_llm_config = _build_llm_config(self.config, user_llm_config=llm_config)
        adjudicator = (
            LLMKnowledgeGraphExtractor(
                config=self.config,
                llm_config=resolved_llm_config,
                user_id=user_id,
                library_id=library_id,
            )
            if resolved_llm_config.get("small_model_name") and resolved_llm_config.get("small_api_key")
            else None
        )
        dummy_doc = StructuredKnowledgeDocument(
            document_id="__full_dedup__", source_type="text", source_path="", source_uri="",
            source_hash="", title="【全库去重】", summary="", tags=[], authority=0.7,
            valid_from=None, valid_until=None, metadata={}, sections=[],
        )

        all_mapping: dict[str, str] = {}
        cached_decisions = self._load_dedup_decisions(user_id=user_id, library_id=library_id)
        new_decisions: list[KnowledgeGraphDedupDecision] = []
        high_threshold = float(self.config.limits.graph_dedup_high_similarity)
        gray_threshold = float(self.config.limits.graph_dedup_gray_similarity)
        for idx, cluster_items in enumerate(batches, start=1):
            if len(cluster_items) <= 1:
                continue
            _set_dedup_progress(user_id, library_id, "running", total_batches, idx,
                                f"正在处理第 {idx}/{total_batches} 批 ({len(cluster_items)} 个实体)", 0)
            gray_pairs: list[tuple[KnowledgeGraphNode, KnowledgeGraphNode, float]] = []
            for left_index, (_left_label, left_row) in enumerate(cluster_items):
                for _right_label, right_row in cluster_items[left_index + 1:]:
                    if left_row.entity_type != right_row.entity_type:
                        continue
                    similarity = self._cosine_similarity(
                        vector_by_node_id[left_row.node_id],
                        vector_by_node_id[right_row.node_id],
                    )
                    decision_id = self._dedup_decision_id(
                        user_id=user_id,
                        library_id=library_id,
                        left_label=left_row.label,
                        right_label=right_row.label,
                        entity_type=left_row.entity_type,
                    )
                    cached = cached_decisions.get(decision_id)
                    if (
                        cached
                        and cached.adjudicator_version == self._DEDUP_ADJUDICATOR_VERSION
                        and cached.decision != "pending"
                    ):
                        if cached.decision == "merge" and cached.canonical_label:
                            source = right_row.label if cached.canonical_label == left_row.label else left_row.label
                            all_mapping[source] = cached.canonical_label
                        continue
                    if similarity >= high_threshold:
                        left_confidence = float((left_row.metadata_json or {}).get("confidence", 0.7))
                        right_confidence = float((right_row.metadata_json or {}).get("confidence", 0.7))
                        canonical, source = (
                            (left_row.label, right_row.label)
                            if left_confidence >= right_confidence
                            else (right_row.label, left_row.label)
                        )
                        all_mapping[source] = canonical
                        new_decisions.append(self._build_dedup_decision(
                            user_id=user_id,
                            library_id=library_id,
                            left_label=left_row.label,
                            right_label=right_row.label,
                            entity_type=left_row.entity_type,
                            decision="merge",
                            canonical_label=canonical,
                            similarity=similarity,
                        ))
                    elif similarity >= gray_threshold:
                        gray_pairs.append((left_row, right_row, similarity))

            gray_resolved = False
            if gray_pairs and adjudicator is not None:
                gray_rows = {row.node_id: row for pair in gray_pairs for row in pair[:2]}
                gray_batch = [
                    EntityCandidate(
                        name=row.label,
                        entity_type=row.entity_type,
                        aliases=(row.metadata_json or {}).get("aliases", []),
                        description="",
                        confidence=float((row.metadata_json or {}).get("confidence", 0.7)),
                    )
                    for row in gray_rows.values()
                ]
                try:
                    result = adjudicator.deduplicate_entities(gray_batch, document=dummy_doc)
                    remote_mapping = dict(result.get("name_mapping", {}) or {})
                    for left_row, right_row, similarity in gray_pairs:
                        left_target = self._normalize_label(remote_mapping.get(left_row.label, left_row.label))
                        right_target = self._normalize_label(remote_mapping.get(right_row.label, right_row.label))
                        should_merge = left_target == right_target
                        canonical = left_row.label if should_merge else ""
                        if should_merge:
                            all_mapping[right_row.label] = canonical
                        new_decisions.append(self._build_dedup_decision(
                            user_id=user_id,
                            library_id=library_id,
                            left_label=left_row.label,
                            right_label=right_row.label,
                            entity_type=left_row.entity_type,
                            decision="merge" if should_merge else "separate",
                            canonical_label=canonical,
                            similarity=similarity,
                        ))
                    gray_resolved = True
                except Exception as exc:  # noqa: BLE001 - local high-confidence merges remain valid
                    logger.warning("全库去重灰区裁决失败，保留本地结果 | batch=%s error=%s", idx, exc)
            if gray_pairs and not gray_resolved:
                new_decisions.extend(
                    self._build_dedup_decision(
                        user_id=user_id,
                        library_id=library_id,
                        left_label=left_row.label,
                        right_label=right_row.label,
                        entity_type=left_row.entity_type,
                        decision="pending",
                        canonical_label="",
                        similarity=similarity,
                    )
                    for left_row, right_row, similarity in gray_pairs
                )

        self._save_dedup_decisions(new_decisions)

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
