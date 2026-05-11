"""
Session 数据传输对象。

功能说明:
本文件定义会话管理 API 和业务层之间传递的数据结构。DTO 与数据库模型分离,
避免接口层直接暴露数据库模型。

使用说明:
`SessionCreate` 用于创建会话,`SessionUpdate` 用于更新会话,`SessionOut` 用于
服务层向 API 层或其他调用方返回会话信息。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.models.session import SessionRecord


class SessionCreate(SQLModel):
    """
    创建会话 DTO。

    user_id: 会话所属用户 ID。
    session_name: 可选会话名称;为空时由业务层使用默认会话名。
    """

    user_id: str = Field(min_length=1, max_length=128)
    session_name: str | None = Field(default=None, max_length=255)


class SessionUpdate(SQLModel):
    """
    更新会话 DTO。

    session_name: 新的会话显示名称。
    """

    session_name: str = Field(min_length=1, max_length=255)


class SessionOut(SQLModel):
    """
    会话输出 DTO。

    session_id: 会话 ID。
    user_id: 会话所属用户 ID。
    session_name: 会话显示名称。
    created_at: 会话创建时间。
    updated_at: 会话最近更新时间。
    """

    session_id: str
    user_id: str
    session_name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: SessionRecord) -> "SessionOut":
        """从数据库模型转换为输出 DTO。"""

        return cls(
            session_id=record.session_id,
            user_id=record.user_id,
            session_name=record.session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
