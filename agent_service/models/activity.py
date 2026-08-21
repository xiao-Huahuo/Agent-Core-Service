"""
Persisted daily activity event model.

Usage:
Business services and HTTP activity tracking append privacy-safe events here;
the dashboard aggregates these immutable rows into the yearly heatmap.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import utc_now


class ActivityEventRecord(SQLModel, table=True):
    """One scored, user-owned activity event without sensitive payload data."""

    __tablename__ = "activity_events"

    event_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    module: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    action: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    score: int = Field(default=1, ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, le=DEFAULT_BUSINESS_LIMITS.activity_event_score_max)
    object_id: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.summary_max_length)
    title: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)
    source: str = Field(default="runtime", index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    created_at: datetime = Field(default_factory=utc_now, index=True)
