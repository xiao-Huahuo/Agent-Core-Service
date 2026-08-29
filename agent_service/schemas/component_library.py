"""
Component library request and response schemas.

Usage:
REST and gRPC adapters validate knowledge-directory file uploads with
ComponentLibraryItemCreate and serialize them with ComponentLibraryItemOut.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS


class ComponentLibraryItemBase(SQLModel):
    """Describe the user-provided fields shared by component DTOs."""

    user_id: str = Field(
        min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        max_length=DEFAULT_BUSINESS_LIMITS.user_id_max_length,
    )
    source: str = Field(
        min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        max_length=DEFAULT_BUSINESS_LIMITS.component_schema_source_max_length,
    )
    tag: str = Field(
        min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length,
    )


class ComponentLibraryItemCreate(ComponentLibraryItemBase):
    """Validate one component upload request."""

    filename: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.title_max_length)


class ComponentLibraryItemUpdate(SQLModel):
    """Validate one incremental component title, source, or tag update."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    component_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.summary_max_length)
    title: str | None = Field(default=None, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.component_filename_max_length)
    source: str | None = Field(default=None, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.component_schema_source_max_length)
    tag: str | None = Field(default=None, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)


class ComponentLibraryItemOut(ComponentLibraryItemBase):
    """Return a knowledge-directory component in the common card shape."""

    component_id: str
    title: str
    source_format: str
    builtin: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
