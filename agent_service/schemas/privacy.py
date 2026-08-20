"""Privacy REST and gRPC DTO schemas.

Usage:
Use PrivacyCreate at write boundaries and PrivacyOut/PrivacyListOut for public
responses. Only knowledge files and library items can be private.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PrivacyTargetType = Literal["knowledge_path", "library_item"]


class PrivacyCreate(BaseModel):
    """Create one backend-persisted privacy flag."""

    user_id: str = Field(min_length=1, max_length=128)
    target_type: PrivacyTargetType
    target_id: str = Field(min_length=1, max_length=2048)
    library_id: str = Field(default="", max_length=128)


class PrivacyOut(BaseModel):
    """Public privacy record returned by REST and service callers."""

    privacy_id: str
    user_id: str
    library_id: str
    target_type: PrivacyTargetType
    target_id: str
    created_at: datetime


class PrivacyListOut(BaseModel):
    """List response wrapper for privacy records."""

    privacy: list[PrivacyOut]
