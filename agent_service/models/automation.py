"""
定时自动化任务数据库模型。

功能说明:
- AutomationTaskRecord: 描述一个按时间唤醒 Agent 的自动化任务。
- AutomationRunRecord: 记录每次自动化执行的状态、输出和错误。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class AutomationTaskRecord(SQLModel, table=True):
    """持久化一个用户自动化任务及其下一次执行时间。"""

    __tablename__ = "automation_tasks"

    automation_id: str = Field(primary_key=True, max_length=64)
    todo_id: str = Field(index=True, unique=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    prompt: str
    timezone_name: str = Field(default="UTC", max_length=64)
    recurrence_frequency: str = Field(default="none", max_length=16)
    recurrence_interval: int = Field(default=1, ge=1, le=365)
    next_run_at: datetime = Field(index=True)
    access_mode: str = Field(default="sandbox", max_length=16)
    enabled: bool = Field(default=True, index=True)
    lease_id: str | None = Field(default=None, index=True, max_length=64)
    lease_until: datetime | None = Field(default=None, index=True)
    last_run_at: datetime | None = None
    last_status: str | None = Field(default=None, max_length=16)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AutomationRunRecord(SQLModel, table=True):
    """持久化一次自动化任务执行结果。"""

    __tablename__ = "automation_runs"

    run_id: str = Field(primary_key=True, max_length=64)
    automation_id: str = Field(index=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    status: str = Field(default="running", max_length=16)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    output: str | None = None
    error: str | None = None
