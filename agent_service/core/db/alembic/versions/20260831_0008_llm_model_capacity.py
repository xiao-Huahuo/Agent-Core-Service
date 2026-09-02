"""Persist explicit main and small model capacity overrides."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260831_0008"
down_revision = "20260831_0007"
branch_labels = None
depends_on = None


CAPACITY_COLUMNS = (
    "model_context_window_tokens",
    "model_max_output_tokens",
    "small_model_context_window_tokens",
    "small_model_max_output_tokens",
)


def upgrade() -> None:
    """Add nullable-by-value capacity overrides; zero means inherit service policy."""

    with op.batch_alter_table("user_llm_config") as batch_op:
        for column_name in CAPACITY_COLUMNS:
            batch_op.add_column(
                sa.Column(column_name, sa.Integer(), nullable=False, server_default="0")
            )


def downgrade() -> None:
    """Remove model capacity override columns."""

    with op.batch_alter_table("user_llm_config") as batch_op:
        for column_name in reversed(CAPACITY_COLUMNS):
            batch_op.drop_column(column_name)
