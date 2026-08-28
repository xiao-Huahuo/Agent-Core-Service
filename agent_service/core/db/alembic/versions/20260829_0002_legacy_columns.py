"""Migrate supported pre-Alembic databases to the current column set.

Revision ID: 20260829_0002
Revises: 20260829_0001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260829_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table_name: str) -> set[str]:
    """Return the current column names for one existing table."""

    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_missing_column(table_name: str, column: sa.Column) -> bool:
    """Add one column only when a supported legacy database lacks it."""

    if column.name in _column_names(table_name):
        return False
    op.add_column(table_name, column)
    return True


def upgrade() -> None:
    """Apply every historical in-Service ALTER TABLE as one versioned migration."""

    _add_missing_column("user_llm_config", sa.Column("small_api_key", sa.String(1024), nullable=False, server_default=""))
    _add_missing_column("user_llm_config", sa.Column("small_base_url", sa.String(1024), nullable=False, server_default=""))
    _add_missing_column("user_llm_config", sa.Column("small_model_name", sa.String(256), nullable=False, server_default=""))

    user_settings_columns = [
        sa.Column("proxy_url", sa.String(1024), nullable=False, server_default=""),
        sa.Column("browser_proxy_url", sa.String(1024), nullable=False, server_default=""),
        sa.Column("browser_home_url", sa.String(2048), nullable=False, server_default="https://www.google.com"),
        sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_ingest_on_upload", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ocr_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("long_term_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("knowledge_ignore_patterns", sa.Text(), nullable=False, server_default=""),
        sa.Column("disabled_tools", sa.Text(), nullable=False, server_default=""),
        sa.Column("terminal_sandbox_config", sa.Text(), nullable=False, server_default=""),
        sa.Column("ui_font_families", sa.Text(), nullable=False, server_default=""),
        sa.Column("text_font_families", sa.Text(), nullable=False, server_default=""),
        sa.Column("ui_font_size_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("text_font_size_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("font_size_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("theme_primary_color", sa.String(16), nullable=False, server_default=""),
        sa.Column("theme_soft_color", sa.String(16), nullable=False, server_default=""),
        sa.Column("background_cover_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("show_backlinks", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("graph_node_limit", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("floating_launch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("editor_image_assets_dir", sa.String(1024), nullable=False, server_default="./assets/"),
        sa.Column("web_search_max_results", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("storage_path_overrides", sa.Text(), nullable=False, server_default=""),
    ]
    had_ui_size = "ui_font_size_percent" in _column_names("user_settings")
    had_text_size = "text_font_size_percent" in _column_names("user_settings")
    for column in user_settings_columns:
        _add_missing_column("user_settings", column)
    if not had_ui_size:
        op.execute("UPDATE user_settings SET ui_font_size_percent = font_size_percent")
    if not had_text_size:
        op.execute("UPDATE user_settings SET text_font_size_percent = font_size_percent")

    _add_missing_column(
        "user_knowledge_libraries",
        sa.Column("library_storage_dir", sa.String(1024), nullable=False, server_default=""),
    )
    _add_missing_column(
        "library_items",
        sa.Column("storage_path", sa.String(2048), nullable=False, server_default=""),
    )
    _add_missing_column("smart_forms", sa.Column("library_id", sa.String(), nullable=False, server_default=""))
    _add_missing_column(
        "smart_forms",
        sa.Column("form_kind", sa.String(), nullable=False, server_default="literature"),
    )
    op.execute(
        "UPDATE smart_forms SET library_id = COALESCE((SELECT library_id FROM user_knowledge_libraries "
        "WHERE user_knowledge_libraries.user_id = smart_forms.user_id AND is_active = 1 LIMIT 1), '') "
        "WHERE library_id = ''"
    )
    _add_missing_column("smart_form_rows", sa.Column("created_at", sa.DateTime(), nullable=True))
    _add_missing_column("smart_form_rows", sa.Column("updated_at", sa.DateTime(), nullable=True))
    _add_missing_column("smart_form_rows", sa.Column("height", sa.Integer(), nullable=False, server_default="72"))
    op.execute("UPDATE smart_form_rows SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE smart_form_rows SET updated_at = created_at WHERE updated_at IS NULL")
    _add_missing_column(
        "smart_form_columns",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    _add_missing_column("vault_assets", sa.Column("item_id", sa.String(64), nullable=False, server_default=""))
    _add_missing_column(
        "vault_profiles",
        sa.Column("debug_master_password", sa.String(512), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Keep the baseline schema intact when stepping back from compatibility revision."""

    # Revision 0001 already defines the complete target schema. Revision 0002 only fills
    # columns in unversioned legacy databases stamped at 0001, so dropping those columns
    # would make a downgraded database contradict the 0001 schema contract. Legacy rollback
    # uses the verified pre-migration SQLite backup instead.
    pass
