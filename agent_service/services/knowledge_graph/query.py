"""KnowledgeGraphService 的 query 职责。

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
    RelationCandidate, StructuredKnowledgeDocument, StructuredKnowledgeSection,
)

class KnowledgeGraphQueryMixin:
    def get_graph(self, *, user_id: str, library_id: str, limit: int | None = None) -> dict[str, Any]:
        """返回前端 Canvas 可直接消费的图谱数据。"""

        safe_limit = max(
            self.config.limits.graph_min_node_limit,
            min(
                int(limit or self.config.limits.graph_default_node_limit),
                self.config.limits.graph_max_node_limit,
            ),
        )
        with Session(self.engine) as db:
            raw_nodes = list(db.exec(
                select(KnowledgeGraphNode)
                .where(KnowledgeGraphNode.user_id == user_id)
                .where(KnowledgeGraphNode.library_id == library_id)
                .order_by(KnowledgeGraphNode.node_id)
                .limit(safe_limit)
            ).all())
            nodes, node_id_aliases = self._coalesce_entity_nodes(raw_nodes)
            node_ids = {node.node_id for node in nodes} | set(node_id_aliases)
            raw_edges = [
                edge
                for edge in db.exec(
                    select(KnowledgeGraphEdge)
                    .where(KnowledgeGraphEdge.user_id == user_id)
                    .where(KnowledgeGraphEdge.library_id == library_id)
                    .order_by(KnowledgeGraphEdge.edge_id)
                    .limit(safe_limit * 2)
                ).all()
                if edge.source_node_id in node_ids and edge.target_node_id in node_ids
            ]
            edges = self._coalesce_edges(raw_edges, node_id_aliases)
            statuses = db.exec(
                select(KnowledgeGraphDocumentStatus)
                .where(KnowledgeGraphDocumentStatus.user_id == user_id)
                .where(KnowledgeGraphDocumentStatus.library_id == library_id)
            ).all()
        return {
            "nodes": [self._serialize_node(node) for node in nodes],
            "links": [self._serialize_edge(edge) for edge in edges],
            "stats": {
                "nodes": len(nodes),
                "links": len(edges),
                "documents": sum(1 for node in nodes if node.node_type == "document"),
                "entities": sum(1 for node in nodes if node.node_type == "entity"),
                "completed_documents": sum(1 for status in statuses if status.status == "completed"),
                "failed_documents": sum(1 for status in statuses if status.status == "failed"),
                "skipped_documents": sum(1 for status in statuses if status.status == "skipped"),
            },
        }
    @staticmethod
    def _serialize_node(node: KnowledgeGraphNode) -> dict[str, Any]:
        """序列化图谱节点。"""

        return {
            "id": node.node_id,
            "label": node.label,
            "kind": node.node_type,
            "entity_type": node.entity_type,
            "document_id": node.document_id,
            "source_uri": node.source_uri,
            "source_range": node.source_range_json,
            "metadata": node.metadata_json,
        }
    @staticmethod
    def _serialize_edge(edge: KnowledgeGraphEdge) -> dict[str, Any]:
        """序列化图谱关系边。"""

        return {
            "id": edge.edge_id,
            "source": edge.source_node_id,
            "target": edge.target_node_id,
            "kind": edge.relation_type,
            "weight": edge.weight,
            "evidence": edge.evidence,
            "source_document_id": edge.source_document_id,
            "source_section_id": edge.source_section_id,
            "metadata": edge.metadata_json,
        }
    @classmethod
    def _coalesce_entity_nodes(
        cls,
        nodes: list[KnowledgeGraphNode],
    ) -> tuple[list[KnowledgeGraphNode], dict[str, str]]:
        """按规范化实体名合并历史同名实体节点并返回旧 ID 到规范 ID 的映射。"""

        result: list[KnowledgeGraphNode] = []
        entity_by_label: dict[str, KnowledgeGraphNode] = {}
        aliases: dict[str, str] = {}
        for node in nodes:
            if node.node_type != "entity":
                result.append(node)
                continue
            key = cls._normalize_label(node.label)
            canonical = entity_by_label.get(key)
            if canonical is None:
                entity_by_label[key] = node
                result.append(node)
                continue
            aliases[node.node_id] = canonical.node_id
            if canonical.entity_type in {"", "other"} and node.entity_type not in {"", "other"}:
                canonical.entity_type = node.entity_type
        return result, aliases
    @staticmethod
    def _coalesce_edges(
        edges: list[KnowledgeGraphEdge],
        node_id_aliases: dict[str, str],
    ) -> list[KnowledgeGraphEdge]:
        """把边两端映射到合并后的实体节点,并删除合并后重复或自环的边。"""

        result: list[KnowledgeGraphEdge] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for edge in edges:
            source_id = node_id_aliases.get(edge.source_node_id, edge.source_node_id)
            target_id = node_id_aliases.get(edge.target_node_id, edge.target_node_id)
            if source_id == target_id:
                continue
            key = (
                source_id,
                target_id,
                edge.relation_type,
                edge.source_document_id,
                edge.source_section_id,
            )
            if key in seen:
                continue
            seen.add(key)
            edge.source_node_id = source_id
            edge.target_node_id = target_id
            result.append(edge)
        return result
