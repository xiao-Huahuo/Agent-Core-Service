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


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class PrivacyRecord(SQLModel, table=True):
    """Persist one private target for a user in a knowledge-library scope."""

    __tablename__ = "privacy_records"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", "target_type", "target_id", name="uq_privacy_target"),
    )

    privacy_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    target_type: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    target_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    created_at: datetime = Field(default_factory=utc_now, index=True)
