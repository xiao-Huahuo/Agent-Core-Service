"""Persist the opt-in DSH coding-agent preference.

Users remain opted out after upgrade; enabling is an explicit per-user action.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260831_0007"
down_revision = "20260831_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the non-null, default-off DSH coding-agent preference."""

    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(
            sa.Column("dsh_coding_agent_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    """Remove the DSH coding-agent preference."""

    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("dsh_coding_agent_enabled")
