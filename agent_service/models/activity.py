"""
Persisted daily activity event model.

Usage:
Business services and HTTP activity tracking append privacy-safe events here;
the dashboard aggregates these immutable rows into the yearly heatmap.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class ActivityEventRecord(SQLModel, table=True):
    """One scored, user-owned activity event without sensitive payload data."""

    __tablename__ = "activity_events"

    event_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    module: str = Field(index=True, min_length=1, max_length=32)
    action: str = Field(index=True, min_length=1, max_length=64)
    score: int = Field(default=1, ge=1, le=20)
    object_id: str = Field(default="", index=True, max_length=512)
    title: str = Field(default="", max_length=256)
    source: str = Field(default="runtime", index=True, max_length=32)
    created_at: datetime = Field(default_factory=utc_now, index=True)
