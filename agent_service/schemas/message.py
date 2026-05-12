"""
Message 数据传输对象。

功能说明:
本文件定义会话消息在业务层和 API 层之间传递的 DTO。DTO 与数据库模型分离,
用于避免接口层直接暴露 `MessageRecord`。

使用说明:
`MessageCreate` 用于新增消息,`MessageUpdate` 用于更新消息摘要状态或元数据,
`MessageOut` 用于向 API 层、ContextBuilder 或调试面板返回消息信息。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel

from agent_service.models.message import MessageRecord


class MessageCreate(SQLModel):
    """
    创建消息 DTO。

    session_id: 消息所属会话 ID。
    user_id: 消息所属用户 ID。
    role: 消息角色,例如 `user`、`assistant`、`tool`、`system`。
    content: 消息正文。
    tool_call_id: 工具结果对应的 tool_call ID。
    tool_calls_json: assistant 消息中的工具调用列表。
    metadata_json: 扩展元数据。
    """

    session_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=32)
    content: str = ""
    tool_call_id: str | None = Field(default=None, max_length=128)
    tool_calls_json: list[dict[str, Any]] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MessageUpdate(SQLModel):
    """
    更新消息 DTO。

    content: 可选的新消息正文。
    metadata_json: 可选的新扩展元数据。
    is_summarized: 是否已经被摘要覆盖。
    """

    content: str | None = None
    metadata_json: dict[str, Any] | None = None
    is_summarized: bool | None = None


class MessageOut(SQLModel):
    """
    消息输出 DTO。

    message_id: 消息 ID。
    session_id: 所属会话 ID。
    user_id: 所属用户 ID。
    role: 消息角色。
    content: 消息正文。
    tool_call_id: 工具调用 ID。
    tool_calls_json: 工具调用列表。
    metadata_json: 扩展元数据。
    is_summarized: 是否已经被摘要覆盖。
    created_at: 消息创建时间。
    """

    message_id: str
    session_id: str
    user_id: str
    role: str
    content: str
    tool_call_id: str | None
    tool_calls_json: list[dict[str, Any]]
    metadata_json: dict[str, Any]
    is_summarized: bool
    created_at: datetime

    @classmethod
    def from_record(cls, record: MessageRecord) -> "MessageOut":
        """从数据库模型转换为输出 DTO。"""

        return cls(
            message_id=record.message_id,
            session_id=record.session_id,
            user_id=record.user_id,
            role=record.role,
            content=record.content,
            tool_call_id=record.tool_call_id,
            tool_calls_json=record.tool_calls_json,
            metadata_json=record.metadata_json,
            is_summarized=record.is_summarized,
            created_at=record.created_at,
        )
