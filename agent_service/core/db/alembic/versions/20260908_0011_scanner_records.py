"""Add persistent scanner records.

Revision ID: 20260908_0011
Revises: 20260907_0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260908_0011"
down_revision = "20260907_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scanner history and editable Markdown storage."""

    op.create_table(
        "scanner_records",
        sa.Column("scan_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=256), nullable=False),
        sa.Column("library_id", sa.String(length=256), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=2048), nullable=False),
        sa.Column("source_path", sa.String(length=2048), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("ocr_enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("stage_label", sa.String(length=4096), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("no_ocr_markdown", sa.Text(), nullable=False),
        sa.Column("ocr_markdown", sa.Text(), nullable=False),
        sa.Column("assets_json", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("scan_id"),
    )
    op.create_index(op.f("ix_scanner_records_user_id"), "scanner_records", ["user_id"], unique=False)
    op.create_index(op.f("ix_scanner_records_library_id"), "scanner_records", ["library_id"], unique=False)
    op.create_index(op.f("ix_scanner_records_status"), "scanner_records", ["status"], unique=False)
    op.create_index(op.f("ix_scanner_records_created_at"), "scanner_records", ["created_at"], unique=False)


def downgrade() -> None:
    """Remove scanner history storage."""

    op.drop_index(op.f("ix_scanner_records_created_at"), table_name="scanner_records")
    op.drop_index(op.f("ix_scanner_records_status"), table_name="scanner_records")
    op.drop_index(op.f("ix_scanner_records_library_id"), table_name="scanner_records")
    op.drop_index(op.f("ix_scanner_records_user_id"), table_name="scanner_records")
    op.drop_table("scanner_records")
