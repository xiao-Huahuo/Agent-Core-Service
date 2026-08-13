"""Persistent user-owned Agent task queue records."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class AgentQueueTaskRecord(SQLModel, table=True):
    """One independently runnable Agent task and its dedicated session."""

    __tablename__ = "agent_queue_tasks"

    task_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=128)
    prompt: str
    priority: str = Field(default="medium", max_length=16, index=True)
    status: str = Field(default="pending", max_length=16, index=True)
    session_id: str | None = Field(default=None, index=True, max_length=64)
    attachments_json: str = Field(default="[]")
    previous_task_id: str | None = Field(default=None, index=True, max_length=64)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    terminated_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class AgentQueueSettingsRecord(SQLModel, table=True):
    """Per-user queue concurrency preference."""

    __tablename__ = "agent_queue_settings"

    user_id: str = Field(primary_key=True, max_length=128)
    max_concurrency: int = Field(default=5, ge=1, le=20)
    updated_at: datetime = Field(default_factory=utc_now)
