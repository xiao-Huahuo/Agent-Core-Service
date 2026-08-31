"""Persist DSH provider identity and cold-resume metadata on child sessions.

Revision ID: 20260831_0006
Revises: 20260830_0005
Create Date: 2026-08-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260831_0006"
down_revision: str | Sequence[str] | None = "20260830_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add DSH provider, Session, workspace and Runtime version fields."""

    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("agent_sessions")}
    additions = {
        "child_agent_provider": sa.Column("child_agent_provider", sa.String(length=32), nullable=True),
        "dsh_session_id": sa.Column("dsh_session_id", sa.String(length=64), nullable=True),
        "child_workspace_root": sa.Column("child_workspace_root", sa.String(length=1024), nullable=True),
        "dsh_runtime_version": sa.Column("dsh_runtime_version", sa.String(length=64), nullable=True),
    }
    with op.batch_alter_table("agent_sessions") as batch_op:
        for name, column in additions.items():
            if name not in columns:
                batch_op.add_column(column)
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("agent_sessions")}
    if "ix_agent_sessions_child_agent_provider" not in indexes:
        op.create_index("ix_agent_sessions_child_agent_provider", "agent_sessions", ["child_agent_provider"])
    if "ix_agent_sessions_dsh_session_id" not in indexes:
        op.create_index("ix_agent_sessions_dsh_session_id", "agent_sessions", ["dsh_session_id"])


def downgrade() -> None:
    """Remove DSH child-session metadata."""

    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("agent_sessions")}
    with op.batch_alter_table("agent_sessions") as batch_op:
        if "ix_agent_sessions_dsh_session_id" in indexes:
            batch_op.drop_index("ix_agent_sessions_dsh_session_id")
        if "ix_agent_sessions_child_agent_provider" in indexes:
            batch_op.drop_index("ix_agent_sessions_child_agent_provider")
        batch_op.drop_column("dsh_runtime_version")
        batch_op.drop_column("child_workspace_root")
        batch_op.drop_column("dsh_session_id")
        batch_op.drop_column("child_agent_provider")
