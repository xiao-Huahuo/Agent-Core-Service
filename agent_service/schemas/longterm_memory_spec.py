"""
统一长期记忆数据传输对象。

功能说明:
本文件定义 `LongTermMemorySpec` 对应的 DTO。该 DTO 用于在摘要服务、知识库
切片服务、RAG 检索服务和 API 层之间传递统一记忆结构。

使用说明:
`LongTermMemorySpecCreate` 用于创建会话摘要记忆或知识库切片记忆。
`LongTermMemorySpecUpdate` 用于更新有效期、评分、向量或扩展元数据。
`LongTermMemorySpecOut` 用于返回可溯源、可过滤、可检索的记忆记录。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel

from agent_service.models.longterm_memory_spec import LongTermMemorySpec


class LongTermMemorySpecCreate(SQLModel):
    """
    创建统一长期记忆 DTO。

    user_id: 记忆所属用户 ID。
    session_id: 可选会话 ID。
    tag: 记忆大类,例如 `Memory`、`Knowledge`。
    memory_type: 记忆子类型。
    content: 记忆正文。
    source_type: 来源类型。
    source_id: 来源 ID。
    source_uri: 来源 URI。
    source_hash: 来源哈希。
    source_range_json: 来源范围。
    metadata_json: 扩展元数据。
    valid_from: 记忆开始有效时间。
    valid_until: 记忆失效时间。
    confidence: 可信度。
    importance: 重要性。
    authority: 权威性。
    embedding_model: 向量模型名称。
    embedding_vector_json: 向量列表。
    """

    user_id: str = Field(min_length=1, max_length=128)
    session_id: str | None = Field(default=None, max_length=64)
    tag: str = Field(min_length=1, max_length=64)
    memory_type: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)
    source_type: str = Field(min_length=1, max_length=128)
    source_id: str | None = Field(default=None, max_length=255)
    source_uri: str | None = Field(default=None, max_length=1024)
    source_hash: str | None = Field(default=None, max_length=128)
    source_range_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding_model: str | None = Field(default=None, max_length=255)
    embedding_vector_json: list[float] = Field(default_factory=list)


class LongTermMemorySpecUpdate(SQLModel):
    """
    更新统一长期记忆 DTO。

    content: 可选的新记忆正文。
    metadata_json: 可选的新扩展元数据。
    valid_from: 可选的新生效时间。
    valid_until: 可选的新失效时间。
    confidence: 可选的新可信度。
    importance: 可选的新重要性。
    authority: 可选的新权威性。
    embedding_model: 可选的新向量模型名称。
    embedding_vector_json: 可选的新向量列表。
    """

    content: str | None = None
    metadata_json: dict[str, Any] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    authority: float | None = Field(default=None, ge=0.0, le=1.0)
    embedding_model: str | None = Field(default=None, max_length=255)
    embedding_vector_json: list[float] | None = None


class LongTermMemorySpecOut(SQLModel):
    """
    统一长期记忆输出 DTO。

    memory_id: 记忆 ID。
    user_id: 记忆所属用户 ID。
    session_id: 可选会话 ID。
    tag: 记忆大类。
    memory_type: 记忆子类型。
    content: 记忆正文。
    source_type: 来源类型。
    source_id: 来源 ID。
    source_uri: 来源 URI。
    source_hash: 来源哈希。
    source_range_json: 来源范围。
    metadata_json: 扩展元数据。
    valid_from: 生效时间。
    valid_until: 失效时间。
    confidence: 可信度。
    importance: 重要性。
    authority: 权威性。
    embedding_model: 向量模型名称。
    embedding_vector_json: 向量列表。
    created_at: 创建时间。
    updated_at: 更新时间。
    """

    memory_id: str
    user_id: str
    session_id: str | None
    tag: str
    memory_type: str
    content: str
    source_type: str
    source_id: str | None
    source_uri: str | None
    source_hash: str | None
    source_range_json: dict[str, Any]
    metadata_json: dict[str, Any]
    valid_from: datetime
    valid_until: datetime | None
    confidence: float
    importance: float
    authority: float
    embedding_model: str | None
    embedding_vector_json: list[float]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: LongTermMemorySpec) -> "LongTermMemorySpecOut":
        """从数据库模型转换为输出 DTO。"""

        return cls(
            memory_id=record.memory_id,
            user_id=record.user_id,
            session_id=record.session_id,
            tag=record.tag,
            memory_type=record.memory_type,
            content=record.content,
            source_type=record.source_type,
            source_id=record.source_id,
            source_uri=record.source_uri,
            source_hash=record.source_hash,
            source_range_json=record.source_range_json,
            metadata_json=record.metadata_json,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            confidence=record.confidence,
            importance=record.importance,
            authority=record.authority,
            embedding_model=record.embedding_model,
            embedding_vector_json=record.embedding_vector_json,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
