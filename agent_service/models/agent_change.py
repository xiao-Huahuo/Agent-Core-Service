"""
Agent turn change database models.

Each row is a durable, session-scoped edit snapshot.  It keeps the exact
before/after text needed for a guarded undo instead of deriving a broad Git
diff that may include unrelated user changes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for change snapshots."""

    return datetime.now(timezone.utc)


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class AgentChangeSnapshotRecord(SQLModel, table=True):
    """Persist the patch edits made during one Agent execution run."""

    __tablename__ = "agent_change_snapshots"

    snapshot_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    session_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    run_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    edits_json: str = Field(default="[]")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    is_finalized: bool = Field(default=False, index=True)
    is_undone: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    finalized_at: datetime | None = Field(default=None)
