"""Persist child Agent conversations as sessions owned by a root session.

Revision ID: 20260830_0005
Revises: 20260829_0004
Create Date: 2026-08-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260830_0005"
down_revision: str | Sequence[str] | None = "20260829_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the parent/run relationship used by hidden child conversations."""

    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("agent_sessions")}
    with op.batch_alter_table("agent_sessions") as batch_op:
        if "parent_session_id" not in columns:
            batch_op.add_column(sa.Column("parent_session_id", sa.String(length=64), nullable=True))
        if "child_agent_run_id" not in columns:
            batch_op.add_column(sa.Column("child_agent_run_id", sa.String(length=64), nullable=True))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("agent_sessions")}
    if "ix_agent_sessions_parent_session_id" not in indexes:
        op.create_index("ix_agent_sessions_parent_session_id", "agent_sessions", ["parent_session_id"])
    if "ix_agent_sessions_child_agent_run_id" not in indexes:
        op.create_index("ix_agent_sessions_child_agent_run_id", "agent_sessions", ["child_agent_run_id"])


def downgrade() -> None:
    """Remove child Agent conversation ownership fields."""

    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("agent_sessions")}
    with op.batch_alter_table("agent_sessions") as batch_op:
        if "ix_agent_sessions_child_agent_run_id" in indexes:
            batch_op.drop_index("ix_agent_sessions_child_agent_run_id")
        if "ix_agent_sessions_parent_session_id" in indexes:
            batch_op.drop_index("ix_agent_sessions_parent_session_id")
        batch_op.drop_column("child_agent_run_id")
        batch_op.drop_column("parent_session_id")
