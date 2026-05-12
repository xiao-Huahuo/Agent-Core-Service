"""
Message 数据库模型。

功能说明:
本文件定义会话消息相关的 SQLModel 模型。`MessageRecord` 映射 PostgreSQL
中的 `agent_messages` 表,用于保存一个 Session 下的用户消息、模型回复、
工具调用消息和工具返回消息。Message 是 Session 的原始事件日志,后续摘要、
长期记忆和前端可观测轨迹都应从这些原始记录溯源。

使用说明:
`session_id` 通过外键关联 `agent_sessions.session_id`,表示一段会话包含多条
消息。业务层后续应通过 MessageService 或 ContextBuilder 读写本模型,
不要在 AgentCore 节点中直接操作数据库表。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class MessageBase(SQLModel):
    """
    消息基础模型。

    user_id: 消息所属用户 ID,用于用户级检索和数据隔离。
    role: 消息角色,例如 `user`、`assistant`、`tool`、`system`。
    content: 消息正文;工具调用消息允许为空,但工具结果应写入正文。
    tool_call_id: 工具结果对应的 tool_call ID,仅 role 为 `tool` 时通常有值。
    tool_calls_json: assistant 消息中模型请求调用工具的结构化列表。
    metadata_json: 扩展元数据,用于保存模型名、节点名、trace 或来源信息。
    is_summarized: 当前消息是否已经被短期摘要覆盖,用于避免重复压缩。
    """

    user_id: str = Field(index=True, min_length=1, max_length=128)
    role: str = Field(index=True, min_length=1, max_length=32)
    content: str = Field(default="", sa_column=Column(Text))
    tool_call_id: str | None = Field(default=None, index=True, max_length=128)
    tool_calls_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    is_summarized: bool = Field(default=False, index=True)


class MessageRecord(MessageBase, table=True):
    """
    消息数据库模型。

    message_id: 消息主键,由业务层生成。
    session_id: 所属会话 ID,外键关联 `agent_sessions.session_id`。
    created_at: 消息创建时间。
    session_id 字段通过数据库外键保证消息属于指定会话。
    """

    __tablename__ = "agent_messages"

    message_id: str = Field(primary_key=True, max_length=64)
    session_id: str = Field(foreign_key="agent_sessions.session_id", index=True, max_length=64)
    created_at: datetime = Field(default_factory=utc_now, index=True)
