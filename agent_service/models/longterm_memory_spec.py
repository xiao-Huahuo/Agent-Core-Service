"""
统一长期记忆数据库模型。

功能说明:
本文件定义统一长期记忆结构 `LongTermMemorySpec`。该结构用于同时承载会话摘要
记忆和知识库切片记忆,通过 `tag` 与 `memory_type` 区分来源和用途。它不是原始
消息日志,而是经过摘要、切片、提炼或向量化后可参与长期检索的记忆记录。

使用说明:
会话消息摘要应保存为 `tag=Memory`、`memory_type=session_summary`。
知识库切片应保存为 `tag=Knowledge`、`memory_type=knowledge_chunk`。
所有记录都应保留 source 字段、有效期字段和评分字段,用于可溯源、时效过滤和
README 中的相关性+时效性+权威性联合排序。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class LongTermMemorySpecBase(SQLModel):
    """
    统一长期记忆基础模型。

    user_id: 记忆所属用户 ID;知识库全局内容可使用约定的系统用户 ID。
    session_id: 可选会话 ID;会话摘要类记忆需要填写,知识库记忆可为空。
    tag: 记忆大类,例如 `Memory`、`Knowledge`。
    memory_type: 记忆子类型,例如 `session_summary`、`knowledge_chunk`。
    content: 可检索的记忆正文。
    source_type: 来源类型,例如 `session_messages`、`knowledge_file`。
    source_id: 来源 ID,例如 session_id、文件 ID 或外部文档 ID。
    source_uri: 来源 URI,例如知识库文件路径。
    source_hash: 来源内容哈希,用于判断知识库文件或摘要来源是否变化。
    source_range_json: 来源范围,例如 message_ids、chunk_index、start_char。
    metadata_json: 扩展元数据,用于保存 facts、preferences、open_tasks 等结构化内容。
    valid_from: 记忆开始有效时间。
    valid_until: 记忆失效时间;为空表示暂不过期。
    confidence: 记忆可信度,范围建议为 0 到 1。
    importance: 记忆重要性,范围建议为 0 到 1。
    authority: 来源权威性,范围建议为 0 到 1。
    embedding_model: 生成向量的模型名称。
    embedding_vector_json: 向量列表;与 ChromaDB 向量集合保持同步。
    """

    user_id: str = Field(index=True, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, index=True, max_length=64)
    tag: str = Field(index=True, min_length=1, max_length=64)
    memory_type: str = Field(index=True, min_length=1, max_length=128)
    content: str = Field(sa_column=Column(Text))
    source_type: str = Field(index=True, min_length=1, max_length=128)
    source_id: str | None = Field(default=None, index=True, max_length=255)
    source_uri: str | None = Field(default=None, max_length=1024)
    source_hash: str | None = Field(default=None, index=True, max_length=128)
    source_range_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    valid_from: datetime = Field(default_factory=utc_now, index=True)
    valid_until: datetime | None = Field(default=None, index=True)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding_model: str | None = Field(default=None, max_length=255)
    embedding_vector_json: list[float] = Field(default_factory=list, sa_column=Column(JSON))


class LongTermMemorySpec(LongTermMemorySpecBase, table=True):
    """
    统一长期记忆数据库模型。

    memory_id: 记忆主键,由业务层生成。
    created_at: 记忆创建时间。
    updated_at: 记忆最近更新时间。
    """

    __tablename__ = "longterm_memory_specs"

    memory_id: str = Field(primary_key=True, max_length=64)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
