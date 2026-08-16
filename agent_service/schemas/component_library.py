"""
Component library request and response schemas.

Usage:
REST and gRPC adapters validate knowledge-directory file uploads with
ComponentLibraryItemCreate and serialize them with ComponentLibraryItemOut.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class ComponentLibraryItemBase(SQLModel):
    """Describe the user-provided fields shared by component DTOs."""

    user_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=250_000)
    tag: str = Field(min_length=1, max_length=32)


class ComponentLibraryItemCreate(ComponentLibraryItemBase):
    """Validate one component upload request."""

    filename: str = Field(default="", max_length=256)


class ComponentLibraryItemUpdate(SQLModel):
    """Validate one persistent component-file rename request."""

    user_id: str = Field(min_length=1, max_length=128)
    component_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=180)


class ComponentLibraryItemOut(ComponentLibraryItemBase):
    """Return a knowledge-directory component in the common card shape."""

    component_id: str
    title: str
    source_format: str
    builtin: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
