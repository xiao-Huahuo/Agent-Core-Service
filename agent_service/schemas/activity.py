"""
Daily activity heatmap response schemas.

Usage:
The REST endpoint validates the aggregation contract with these DTOs while the
gRPC endpoint serializes the same service payload into protobuf Struct.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class ActivityModuleStatsOut(BaseModel):
    """Score and raw event count for one module on one day."""

    score: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)
    event_count: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)


class ActivityDetailOut(BaseModel):
    """Privacy-safe recent activity displayed in the selected-day panel."""

    module: str
    action: str
    score: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    title: str
    created_at: str


class ActivityDayOut(BaseModel):
    """One active calendar day with capped contribution totals."""

    date: str
    score: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)
    level: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value, le=DEFAULT_BUSINESS_LIMITS.weekday_max_index)
    event_count: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)
    modules: dict[str, ActivityModuleStatsOut]
    activities: list[ActivityDetailOut]


class ActivitySummaryOut(BaseModel):
    """Four compact statistics displayed for one heatmap filter."""

    total_score: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)
    active_days: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)
    current_streak: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)
    peak_score: int = Field(ge=DEFAULT_BUSINESS_LIMITS.nonnegative_min_value)


class ActivityHeatmapOut(BaseModel):
    """Complete 53-week activity heatmap response."""

    timezone: str
    start_date: str
    end_date: str
    days: list[ActivityDayOut]
    summaries: dict[str, ActivitySummaryOut]
