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


class AgentChangeSnapshotRecord(SQLModel, table=True):
    """Persist the patch edits made during one Agent execution run."""

    __tablename__ = "agent_change_snapshots"

    snapshot_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    session_id: str = Field(index=True, min_length=1, max_length=128)
    run_id: str = Field(index=True, min_length=1, max_length=128)
    edits_json: str = Field(default="[]")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    is_finalized: bool = Field(default=False, index=True)
    is_undone: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    finalized_at: datetime | None = Field(default=None)
