"""
定时自动化任务数据库模型。

功能说明:
- AutomationTaskRecord: 描述一个按时间唤醒 Agent 的自动化任务。
- AutomationRunRecord: 记录每次自动化执行的状态、输出和错误。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.models.session import utc_now


class AutomationTaskRecord(SQLModel, table=True):
    """持久化一个用户自动化任务及其下一次执行时间。"""

    __tablename__ = "automation_tasks"

    automation_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    todo_id: str = Field(index=True, unique=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    prompt: str
    timezone_name: str = Field(default="UTC", max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    recurrence_frequency: str = Field(default="none", max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length)
    recurrence_interval: int = Field(
        default=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.todo_recurrence_max_interval,
    )
    next_run_at: datetime = Field(index=True)
    access_mode: str = Field(default="sandbox", max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length)
    enabled: bool = Field(default=True, index=True)
    lease_id: str | None = Field(default=None, index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    lease_until: datetime | None = Field(default=None, index=True)
    last_run_at: datetime | None = None
    last_status: str | None = Field(default=None, max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AutomationRunRecord(SQLModel, table=True):
    """持久化一次自动化任务执行结果。"""

    __tablename__ = "automation_runs"

    run_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    automation_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    status: str = Field(default="running", max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    output: str | None = None
    error: str | None = None
