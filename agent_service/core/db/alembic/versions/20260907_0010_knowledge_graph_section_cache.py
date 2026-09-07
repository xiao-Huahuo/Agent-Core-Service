"""Add persistent graph section and entity-pair decision caches.

The cache stores validated local results and unresolved gray candidates so a
document edit recomputes only changed sections and remote failures can retry
without sending the original full section again. Entity-pair decisions avoid
repeating the same online semantic deduplication request.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260907_0010"
down_revision = "20260905_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the section and dedup-decision caches with lookup indexes."""

    if "knowledge_graph_section_cache" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "knowledge_graph_section_cache",
        sa.Column("cache_id", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("library_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=255), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=False),
        sa.Column("section_hash", sa.String(length=128), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("result_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("pending_candidates_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cache_id"),
        sa.UniqueConstraint(
            "user_id", "library_id", "document_id", "section_id",
            name="uq_knowledge_graph_section_cache_scope",
        ),
    )
    for column in ("user_id", "library_id", "document_id", "section_id", "section_hash", "status", "updated_at"):
        op.create_index(f"ix_knowledge_graph_section_cache_{column}", "knowledge_graph_section_cache", [column])
    op.create_table(
        "knowledge_graph_dedup_decisions",
        sa.Column("decision_id", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("library_id", sa.String(length=128), nullable=False),
        sa.Column("left_label", sa.String(length=255), nullable=False),
        sa.Column("right_label", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("canonical_label", sa.String(length=255), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("adjudicator_version", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    for column in ("user_id", "library_id", "decision", "updated_at"):
        op.create_index(f"ix_knowledge_graph_dedup_decisions_{column}", "knowledge_graph_dedup_decisions", [column])


def downgrade() -> None:
    """Remove both caches without touching persisted graph data."""

    for column in reversed(("user_id", "library_id", "decision", "updated_at")):
        op.drop_index(f"ix_knowledge_graph_dedup_decisions_{column}", table_name="knowledge_graph_dedup_decisions")
    op.drop_table("knowledge_graph_dedup_decisions")
    for column in reversed(("user_id", "library_id", "document_id", "section_id", "section_hash", "status", "updated_at")):
        op.drop_index(f"ix_knowledge_graph_section_cache_{column}", table_name="knowledge_graph_section_cache")
    op.drop_table("knowledge_graph_section_cache")
