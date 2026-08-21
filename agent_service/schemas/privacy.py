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


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class PrivacyCreate(BaseModel):
    """Create one backend-persisted privacy flag."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    target_type: PrivacyTargetType
    target_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    library_id: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)


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
