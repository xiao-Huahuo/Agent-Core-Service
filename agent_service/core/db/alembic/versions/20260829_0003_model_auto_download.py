"""Add the persisted user preference for automatic model downloads.

Revision ID: 20260829_0003
Revises: 20260829_0002
Create Date: 2026-08-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260829_0003"
down_revision: str | Sequence[str] | None = "20260829_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist automatic model downloads as an opt-in user setting."""

    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(
            sa.Column("model_auto_download_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    """Remove the automatic model download preference."""

    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("model_auto_download_enabled")
