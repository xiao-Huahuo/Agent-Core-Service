"""Persistent user-owned Agent task queue records."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import utc_now


class AgentQueueTaskRecord(SQLModel, table=True):
    """One independently runnable Agent task and its dedicated session."""

    __tablename__ = "agent_queue_tasks"

    task_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    prompt: str
    priority: str = Field(default="medium", max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length, index=True)
    status: str = Field(default="pending", max_length=DEFAULT_BUSINESS_LIMITS.short_status_max_length, index=True)
    session_id: str | None = Field(default=None, index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    attachments_json: str = Field(default="[]")
    previous_task_id: str | None = Field(default=None, index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    terminated_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class AgentQueueSettingsRecord(SQLModel, table=True):
    """Per-user queue concurrency preference."""

    __tablename__ = "agent_queue_settings"

    user_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    max_concurrency: int = Field(
        default=DEFAULT_BUSINESS_LIMITS.agent_queue_default_concurrency,
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.agent_queue_max_concurrency,
    )
    updated_at: datetime = Field(default_factory=utc_now)
