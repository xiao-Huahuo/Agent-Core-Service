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

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import SessionRecord


class SessionCreate(SQLModel):
    """
    创建会话 DTO。

    user_id: 会话所属用户 ID。
    session_name: 可选会话名称;为空时由业务层使用默认会话名。
    """

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    session_name: str | None = Field(default=None, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)


class SessionUpdate(SQLModel):
    """
    更新会话 DTO。

    session_name: 新的会话显示名称。
    """

    session_name: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.legacy_filename_max_length)


class SessionStateUpdate(SQLModel):
    """
    更新会话状态 DTO。

    state_json: Agent 探索状态 JSON 字符串。
    """

    state_json: str | None = Field(default=None)


class SessionStateOut(SQLModel):
    """
    会话状态输出 DTO。

    session_id: 会话 ID。
    state_json: Agent 探索状态 JSON 字符串。
    """

    session_id: str
    state_json: str | None


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
    parent_session_id: str | None = None
    child_agent_run_id: str | None = None
    child_agent_provider: str | None = None
    dsh_session_id: str | None = None
    child_workspace_root: str | None = None
    dsh_runtime_version: str | None = None

    @classmethod
    def from_record(cls, record: SessionRecord) -> "SessionOut":
        """从数据库模型转换为输出 DTO。"""

        return cls(
            session_id=record.session_id,
            user_id=record.user_id,
            session_name=record.session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            parent_session_id=record.parent_session_id,
            child_agent_run_id=record.child_agent_run_id,
            child_agent_provider=record.child_agent_provider,
            dsh_session_id=record.dsh_session_id,
            child_workspace_root=record.child_workspace_root,
            dsh_runtime_version=record.dsh_runtime_version,
        )
