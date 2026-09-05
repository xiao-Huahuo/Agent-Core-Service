"""
Component library extension metadata models.

Usage:
Drawing-script source remains a managed knowledge-library file. This table
persists the script language and optional existing library cover asset link.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.models.session import utc_now


class ComponentLibraryMetadata(SQLModel, table=True):
    """Persist fields that cannot be derived from a component source path."""

    __tablename__ = "component_library_metadata"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", "component_id", name="uq_component_library_metadata_scope"),
    )

    metadata_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    library_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    component_id: str = Field(index=True, max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    script_language: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    cover_asset_id: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
