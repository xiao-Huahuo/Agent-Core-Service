"""
知识库图谱持久化模型。

功能说明:
本文件定义知识库图谱的 SQLite/SQLModel 表结构。图谱数据与向量库切片分开存储,
用于保存文档节点、实体节点、语义关系边和单文档抽取状态。

使用说明:
`KnowledgeGraphService` 负责创建、清理和查询这些表;业务层不应直接操作表模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class KnowledgeGraphNode(SQLModel, table=True):
    """知识图谱节点表,同时承载文档节点和实体节点。"""

    __tablename__ = "knowledge_graph_nodes"

    node_id: str = Field(primary_key=True, max_length=96)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    library_id: str = Field(index=True, min_length=1, max_length=128)
    node_type: str = Field(index=True, min_length=1, max_length=32)
    label: str = Field(index=True, min_length=1, max_length=255)
    normalized_label: str = Field(index=True, min_length=1, max_length=255)
    entity_type: str = Field(default="", index=True, max_length=64)
    document_id: str = Field(default="", index=True, max_length=255)
    source_uri: str = Field(default="", max_length=1024)
    source_range_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeGraphEdge(SQLModel, table=True):
    """知识图谱关系边表。"""

    __tablename__ = "knowledge_graph_edges"

    edge_id: str = Field(primary_key=True, max_length=96)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    library_id: str = Field(index=True, min_length=1, max_length=128)
    source_node_id: str = Field(index=True, min_length=1, max_length=96)
    target_node_id: str = Field(index=True, min_length=1, max_length=96)
    relation_type: str = Field(index=True, min_length=1, max_length=64)
    weight: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence: str = Field(default="", sa_column=Column(Text))
    source_document_id: str = Field(index=True, min_length=1, max_length=255)
    source_section_id: str = Field(default="", index=True, max_length=128)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class KnowledgeGraphDocumentStatus(SQLModel, table=True):
    """单文档知识图谱抽取状态表。"""

    __tablename__ = "knowledge_graph_document_status"

    status_id: str = Field(primary_key=True, max_length=96)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    library_id: str = Field(index=True, min_length=1, max_length=128)
    document_id: str = Field(index=True, min_length=1, max_length=255)
    source_hash: str = Field(default="", index=True, max_length=128)
    status: str = Field(default="pending", index=True, max_length=32)
    message: str = Field(default="", max_length=1024)
    entity_count: int = 0
    relation_count: int = 0
    updated_at: datetime = Field(default_factory=utc_now, index=True)
