"""Persist drawing-script language and optional cover relationships."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260905_0009"
down_revision = "20260831_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create component metadata without moving canonical source out of the knowledge library."""

    if "component_library_metadata" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "component_library_metadata",
        sa.Column("metadata_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("library_id", sa.String(length=96), nullable=False),
        sa.Column("component_id", sa.String(length=2048), nullable=False),
        sa.Column("script_language", sa.String(length=128), nullable=False),
        sa.Column("cover_asset_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("metadata_id"),
        sa.UniqueConstraint(
            "user_id", "library_id", "component_id",
            name="uq_component_library_metadata_scope",
        ),
    )
    op.create_index("ix_component_library_metadata_user_id", "component_library_metadata", ["user_id"])
    op.create_index("ix_component_library_metadata_library_id", "component_library_metadata", ["library_id"])
    op.create_index("ix_component_library_metadata_component_id", "component_library_metadata", ["component_id"])


def downgrade() -> None:
    """Remove drawing-script extension metadata."""

    op.drop_index("ix_component_library_metadata_component_id", table_name="component_library_metadata")
    op.drop_index("ix_component_library_metadata_library_id", table_name="component_library_metadata")
    op.drop_index("ix_component_library_metadata_user_id", table_name="component_library_metadata")
    op.drop_table("component_library_metadata")
