"""
用户设置数据库模型。

功能说明:
- UserSystemPromptEntry: 用户自定义系统提示词条目，每条独立存储，启动时全部加载拼接。
- UserSettingsRecord: 保留用于未来扩展。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel, Column, Text

from agent_service.models.session import utc_now


class UserSystemPromptEntry(SQLModel, table=True):
    """用户自定义系统提示词条目。"""

    __tablename__ = "user_system_prompts"

    prompt_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)
