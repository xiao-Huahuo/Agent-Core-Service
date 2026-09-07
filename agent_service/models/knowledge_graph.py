"""
知识库图谱持久化模型。

功能说明:
本文件定义知识库图谱的 SQLite/SQLModel 表结构。图谱数据与向量库切片分开存储,
用于保存文档节点、实体节点、语义关系边、章节抽取缓存和单文档抽取状态。

使用说明:
`KnowledgeGraphService` 负责创建、清理和查询这些表;业务层不应直接操作表模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import utc_now


class KnowledgeGraphNode(SQLModel, table=True):
    """知识图谱节点表,同时承载文档节点和实体节点。"""

    __tablename__ = "knowledge_graph_nodes"

    node_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    node_type: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    label: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    normalized_label: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    entity_type: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    document_id: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    source_uri: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.secret_max_length)
    source_range_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeGraphEdge(SQLModel, table=True):
    """知识图谱关系边表。"""

    __tablename__ = "knowledge_graph_edges"

    edge_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    source_node_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    target_node_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    relation_type: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    weight: float = Field(default=0.7, ge=DEFAULT_BUSINESS_LIMITS.binary_score_min, le=DEFAULT_BUSINESS_LIMITS.binary_score_max)
    evidence: str = Field(default="", sa_column=Column(Text))
    source_document_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    source_section_id: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeGraphDocumentStatus(SQLModel, table=True):
    """单文档知识图谱抽取状态表。"""

    __tablename__ = "knowledge_graph_document_status"

    status_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    document_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    source_hash: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    status: str = Field(default="pending", index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    message: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.secret_max_length)
    entity_count: int = 0
    relation_count: int = 0
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeGraphSectionCache(SQLModel, table=True):
    """章节级图谱抽取缓存，支持只重算变化章节和单独重试灰区候选。"""

    __tablename__ = "knowledge_graph_section_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", "document_id", "section_id", name="uq_knowledge_graph_section_cache_scope"),
    )

    cache_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    document_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    section_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    section_hash: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    extractor_version: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    rule_version: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    result_version: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    status: str = Field(default="completed", index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    pending_candidates_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeGraphDedupDecision(SQLModel, table=True):
    """实体对去重判定缓存，避免重复联网裁决同一对名称。"""

    __tablename__ = "knowledge_graph_dedup_decisions"

    decision_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    left_label: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    right_label: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    entity_type: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    decision: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    canonical_label: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)
    similarity: float = Field(default=0.0, ge=DEFAULT_BUSINESS_LIMITS.binary_score_min, le=DEFAULT_BUSINESS_LIMITS.binary_score_max)
    adjudicator_version: str = Field(max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
