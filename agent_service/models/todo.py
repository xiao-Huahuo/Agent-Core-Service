"""
TODO 数据库模型。

功能说明:
- TodoRecord: 用户待办及其提醒、循环规则。
- TodoImportRecord: 标记旧 JSON TODO 是否已经导入,避免重复迁移。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.models.session import utc_now


class TodoRecord(SQLModel, table=True):
    """持久化一条用户 TODO。"""

    __tablename__ = "todos"

    todo_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    text: str
    category: str = Field(default="task", max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    done: bool = Field(default=False)
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    recurrence_frequency: str = Field(default="none", max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length)
    recurrence_interval: int = Field(
        default=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.todo_recurrence_max_interval,
    )
    last_completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TodoImportRecord(SQLModel, table=True):
    """记录某个用户的旧 JSON TODO 是否已经完成导入。"""

    __tablename__ = "todo_imports"

    user_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    imported_at: datetime = Field(default_factory=utc_now)
