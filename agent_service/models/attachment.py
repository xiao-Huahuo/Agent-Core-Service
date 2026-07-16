"""Session-scoped uploaded file records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel

from agent_service.models.session import utc_now


class SessionAttachmentRecord(SQLModel, table=True):
    """Uploaded files that belong to one Agent session and only enter chat context."""

    __tablename__ = "session_attachments"

    attachment_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    session_id: str = Field(foreign_key="agent_sessions.session_id", index=True, max_length=64)
    library_id: str = Field(index=True, max_length=128)
    library_name: str = Field(default="", max_length=255)
    filename: str = Field(min_length=1, max_length=512)
    stored_name: str = Field(min_length=1, max_length=512)
    path: str = Field(sa_column=Column(Text))
    text_path: str = Field(default="", sa_column=Column(Text))
    uri: str = Field(default="", sa_column=Column(Text))
    mime_type: str = Field(default="", max_length=255)
    size: int = Field(default=0)
    source_type: str = Field(default="", max_length=64)
    summary: str = Field(default="", sa_column=Column(Text))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, index=True)
