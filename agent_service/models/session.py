"""
Session 数据库模型。

功能说明:
本文件定义会话管理相关的 SQLModel 模型。`SessionRecord` 映射 SQLite
中的 `agent_sessions` 表,用于保存用户会话的生命周期信息。

使用说明:
业务层应通过 `agent_service.services.session_service.SessionService` 操作本模型,
不要在 API 层或 AgentCore 中直接操作数据库表。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间,用于数据库记录的创建和更新时间。"""

    return datetime.now(timezone.utc)


class SessionBase(SQLModel):
    """
    会话基础模型。

    user_id: 会话所属用户 ID。
    session_name: 会话显示名称。
    """

    user_id: str = Field(index=True, min_length=1, max_length=128)
    session_name: str = Field(min_length=1, max_length=255)


class SessionRecord(SessionBase, table=True):
    """
    会话数据库模型。

    session_id: 会话主键,由业务层生成。
    created_at: 会话创建时间。
    updated_at: 会话最近更新时间。
    state_json: Agent 探索状态 JSON,跨轮持久化。
    """

    __tablename__ = "agent_sessions"

    session_id: str = Field(primary_key=True, max_length=64)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    state_json: str | None = Field(default=None, nullable=True)
