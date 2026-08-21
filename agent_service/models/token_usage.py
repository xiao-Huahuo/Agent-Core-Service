"""
Token usage persistence models.

Usage:
`TokenUsageRecord` stores one normalized model-call token event extracted from
assistant message trace metadata. Statistics endpoints aggregate this table
instead of recalculating token usage in the front-end.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

from agent_service.models.session import utc_now


class TokenUsageRecord(SQLModel, table=True):
    """
    Persisted token usage event.

    token_usage_id: Deterministic primary key, normally based on message id and
        trace index so backfill is idempotent.
    user_id/session_id/message_id: Ownership and source message reference.
    node/event: Agent graph node and trace event that produced the model call.
    model_tier/model_name: Normalized model pool and concrete provider model.
    input/output/total_tokens: Normalized token usage numbers.
    created_at: Event time. Trace timestamps are preferred, message timestamps
        are used as fallback.
    """

    __tablename__ = "agent_token_usage"

    token_usage_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    session_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    message_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    node: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    event: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    model_tier: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    model_name: str = Field(default="", index=True, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
