"""Privacy database model.

Usage:
PrivacyService persists user/library-scoped flags here for knowledge paths and
virtual-library items. The table is the authoritative cross-device state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC time for privacy creation timestamps."""

    return datetime.now(timezone.utc)


class PrivacyRecord(SQLModel, table=True):
    """Persist one private target for a user in a knowledge-library scope."""

    __tablename__ = "privacy_records"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", "target_type", "target_id", name="uq_privacy_target"),
    )

    privacy_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    library_id: str = Field(default="", index=True, max_length=128)
    target_type: str = Field(index=True, min_length=1, max_length=64)
    target_id: str = Field(index=True, min_length=1, max_length=2048)
    created_at: datetime = Field(default_factory=utc_now, index=True)
