"""KnowledgeGraphService 的 repository 职责。

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
    WEAK_RELATION_TYPES, EntityCandidate, GraphExtractionResult, KnowledgeGraphExtractor,
    RelationCandidate, StructuredKnowledgeDocument, StructuredKnowledgeSection,
)

class KnowledgeGraphRepositoryMixin:
    def delete_document_graph(self, *, user_id: str, library_id: str, document_id: str) -> int:
        """删除单文档来源的图谱点边和状态。"""

        document_node_id = self._document_node_id(user_id=user_id, library_id=library_id, document_id=document_id)
        with Session(self.engine) as db:
            edge_ids = [
                edge.edge_id
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_document_id == document_id)
                ).all()
            ]
            edge_ids.extend(
                edge.edge_id
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .where(KnowledgeGraphEdge.source_node_id == document_node_id)
                ).all()
            )
            for edge_id in set(edge_ids):
                edge = db.get(KnowledgeGraphEdge, edge_id)
                if edge:
                    db.delete(edge)
            for node in db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .where(KnowledgeGraphNode.document_id == document_id)
            ).all():
                db.delete(node)
            self._delete_orphan_entity_nodes(db=db, user_id=user_id, library_id=library_id)
            status = db.get(
                KnowledgeGraphDocumentStatus,
                self._status_id(user_id=user_id, library_id=library_id, document_id=document_id),
            )
            if status:
                db.delete(status)
            db.commit()
            return len(set(edge_ids))
    def delete_graph_except_documents(
        self,
        *,
        user_id: str,
        library_id: str,
        keep_document_ids: set[str],
    ) -> int:
        """全库重建后清理已经不存在的文档来源图谱数据。"""

        with Session(self.engine) as db:
            stale_statuses = db.exec(
                select(KnowledgeGraphDocumentStatus)
                .where(KnowledgeGraphDocumentStatus.user_id == user_id)
                .where(KnowledgeGraphDocumentStatus.library_id == library_id)
            ).all()
        deleted = 0
        for status in stale_statuses:
            if status.document_id not in keep_document_ids:
                deleted += self.delete_document_graph(
                    user_id=user_id,
                    library_id=library_id,
                    document_id=status.document_id,
                )
        return deleted
    @staticmethod
    def _delete_orphan_entity_nodes(*, db: Session, user_id: str, library_id: str) -> None:
        """删除没有任何入边或出边的实体节点。"""

        edges = db.exec(
            select(KnowledgeGraphEdge)
            .where(KnowledgeGraphEdge.user_id == user_id)
            .where(KnowledgeGraphEdge.library_id == library_id)
        ).all()
        linked_node_ids = {edge.source_node_id for edge in edges} | {edge.target_node_id for edge in edges}
        for node in db.exec(
            select(KnowledgeGraphNode)
            .where(KnowledgeGraphNode.user_id == user_id)
            .where(KnowledgeGraphNode.library_id == library_id)
            .where(KnowledgeGraphNode.node_type == "entity")
        ).all():
            if node.node_id not in linked_node_ids:
                db.delete(node)
    def _write_graph(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        entities: list[EntityCandidate],
        relations: list[tuple[RelationCandidate, StructuredKnowledgeSection]],
    ) -> tuple[int, int]:
        """写入文档节点、实体节点和关系边。"""

        now = utc_now()
        document_node_id = self._document_node_id(user_id=user_id, library_id=library_id, document_id=document.document_id)
        entity_node_ids: dict[str, str] = {}
        written_entity_node_ids: set[str] = set()
        with Session(self.engine) as db:
            db.merge(self._build_document_node(user_id=user_id, library_id=library_id, document=document, now=now))
            for entity in entities:
                node_id = self._entity_node_id(
                    user_id=user_id,
                    library_id=library_id,
                    entity_type=entity.entity_type,
                    label=entity.name,
                )
                entity_node_ids[entity.name] = node_id
                entity_node_ids[self._normalize_label(entity.name)] = node_id
                written_entity_node_ids.add(node_id)
                db.merge(
                    KnowledgeGraphNode(
                        node_id=node_id,
                        user_id=user_id,
                        library_id=library_id,
                        node_type="entity",
                        label=entity.name,
                        normalized_label=self._normalize_label(entity.name),
                        entity_type=entity.entity_type,
                        document_id="",
                        source_uri=document.source_uri,
                        metadata_json={
                            "aliases": entity.aliases,
                            "description": entity.description,
                            "confidence": entity.confidence,
                        },
                        created_at=now,
                        updated_at=now,
                    )
                )
                db.merge(
                    KnowledgeGraphEdge(
                        edge_id=self._edge_id(
                            user_id,
                            library_id,
                            document_node_id,
                            node_id,
                            "mentions",
                            document.document_id,
                            "",
                        ),
                        user_id=user_id,
                        library_id=library_id,
                        source_node_id=document_node_id,
                        target_node_id=node_id,
                        relation_type="mentions",
                        weight=max(0.2, entity.confidence * 0.5),
                        evidence="",
                        source_document_id=document.document_id,
                        source_section_id="",
                        metadata_json={"edge_role": "document_entity"},
                        created_at=now,
                        updated_at=now,
                    )
                )
            written_relations = 0
            for relation, section in relations:
                source_id = entity_node_ids.get(relation.source) or entity_node_ids.get(self._normalize_label(relation.source))
                target_id = entity_node_ids.get(relation.target) or entity_node_ids.get(self._normalize_label(relation.target))
                if not source_id or not target_id:
                    continue
                db.merge(
                    KnowledgeGraphEdge(
                        edge_id=self._edge_id(
                            user_id,
                            library_id,
                            source_id,
                            target_id,
                            relation.relation_type,
                            document.document_id,
                            section.section_id,
                        ),
                        user_id=user_id,
                        library_id=library_id,
                        source_node_id=source_id,
                        target_node_id=target_id,
                        relation_type=relation.relation_type,
                        weight=self._relation_weight(relation),
                        evidence=relation.evidence,
                        source_document_id=document.document_id,
                        source_section_id=section.section_id,
                        metadata_json={"title_path": section.title_path},
                        created_at=now,
                        updated_at=now,
                    )
                )
                written_relations += 1
            db.commit()
        return len(written_entity_node_ids), written_relations
    def _write_document_node(self, *, user_id: str, library_id: str, document: StructuredKnowledgeDocument) -> None:
        """Persist a document node before best-effort semantic extraction."""

        with Session(self.engine) as db:
            db.merge(
                self._build_document_node(
                    user_id=user_id,
                    library_id=library_id,
                    document=document,
                    now=utc_now(),
                )
            )
            db.commit()
    def _build_document_node(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        now: Any,
    ) -> KnowledgeGraphNode:
        """Build the stable graph node representing a source document."""

        return KnowledgeGraphNode(
            node_id=self._document_node_id(user_id=user_id, library_id=library_id, document_id=document.document_id),
            user_id=user_id,
            library_id=library_id,
            node_type="document",
            label=document.title,
            normalized_label=self._normalize_label(document.title),
            entity_type="document",
            document_id=document.document_id,
            source_uri=document.source_uri,
            metadata_json={"source_type": document.source_type, "tags": document.tags, **document.metadata},
            created_at=now,
            updated_at=now,
        )
    def _is_document_current(self, *, user_id: str, library_id: str, document_id: str, source_hash: str) -> bool:
        """判断当前文档图谱是否已按相同 hash 完成抽取。"""

        with Session(self.engine) as db:
            status = db.get(
                KnowledgeGraphDocumentStatus,
                self._status_id(user_id=user_id, library_id=library_id, document_id=document_id),
            )
            return bool(status and status.source_hash == source_hash and status.status in {"completed", "skipped"})
    def list_document_statuses(self, *, user_id: str, library_id: str) -> dict[str, KnowledgeGraphDocumentStatus]:
        """Return graph extraction status records keyed by source document id."""

        with Session(self.engine) as db:
            statuses = db.exec(
                select(KnowledgeGraphDocumentStatus)
                .where(KnowledgeGraphDocumentStatus.user_id == user_id)
                .where(KnowledgeGraphDocumentStatus.library_id == library_id)
            ).all()
            return {status.document_id: status for status in statuses}
    def _write_status(
        self,
        *,
        user_id: str,
        library_id: str,
        document: StructuredKnowledgeDocument,
        status: str,
        message: str,
        entity_count: int,
        relation_count: int,
    ) -> None:
        """写入单文档图谱抽取状态。"""

        with Session(self.engine) as db:
            db.merge(
                KnowledgeGraphDocumentStatus(
                    status_id=self._status_id(user_id=user_id, library_id=library_id, document_id=document.document_id),
                    user_id=user_id,
                    library_id=library_id,
                    document_id=document.document_id,
                    source_hash=document.ingestion_hash,
                    status=status,
                    message=message,
                    entity_count=entity_count,
                    relation_count=relation_count,
                    updated_at=utc_now(),
                )
            )
            db.commit()
    @staticmethod
    def _relation_weight(relation: RelationCandidate) -> float:
        """根据关系类型和置信度计算边权重。"""

        if relation.relation_type in WEAK_RELATION_TYPES:
            return max(0.2, min(0.55, relation.confidence * 0.55))
        return max(0.4, min(1.0, relation.confidence))
    @classmethod
    def _document_node_id(cls, *, user_id: str, library_id: str, document_id: str) -> str:
        """生成稳定文档节点 ID。"""

        return cls._hashed_id("kgdoc", user_id, library_id, document_id)
    @classmethod
    def _entity_node_id(cls, *, user_id: str, library_id: str, entity_type: str, label: str) -> str:
        """生成稳定实体节点 ID。"""

        return cls._hashed_id("kgent", user_id, library_id, cls._normalize_label(label))
    @classmethod
    def _edge_id(
        cls,
        user_id: str,
        library_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
        document_id: str,
        section_id: str,
    ) -> str:
        """生成稳定关系边 ID。"""

        return cls._hashed_id("kgedge", user_id, library_id, source_id, target_id, relation_type, document_id, section_id)
    @classmethod
    def _status_id(cls, *, user_id: str, library_id: str, document_id: str) -> str:
        """生成稳定状态记录 ID。"""

        return cls._hashed_id("kgstat", user_id, library_id, document_id)
    @staticmethod
    def _hashed_id(prefix: str, *parts: str) -> str:
        """生成短 hash ID。"""

        digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:40]
        return f"{prefix}_{digest}"
