"""
Daily activity heatmap response schemas.

Usage:
The REST endpoint validates the aggregation contract with these DTOs while the
gRPC endpoint serializes the same service payload into protobuf Struct.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ActivityModuleStatsOut(BaseModel):
    """Score and raw event count for one module on one day."""

    score: int = Field(ge=0)
    event_count: int = Field(ge=0)


class ActivityDetailOut(BaseModel):
    """Privacy-safe recent activity displayed in the selected-day panel."""

    module: str
    action: str
    score: int = Field(ge=1)
    title: str
    created_at: str


class ActivityDayOut(BaseModel):
    """One active calendar day with capped contribution totals."""

    date: str
    score: int = Field(ge=0)
    level: int = Field(ge=0, le=6)
    event_count: int = Field(ge=0)
    modules: dict[str, ActivityModuleStatsOut]
    activities: list[ActivityDetailOut]


class ActivitySummaryOut(BaseModel):
    """Four compact statistics displayed for one heatmap filter."""

    total_score: int = Field(ge=0)
    active_days: int = Field(ge=0)
    current_streak: int = Field(ge=0)
    peak_score: int = Field(ge=0)


class ActivityHeatmapOut(BaseModel):
    """Complete 53-week activity heatmap response."""

    timezone: str
    start_date: str
    end_date: str
    days: list[ActivityDayOut]
    summaries: dict[str, ActivitySummaryOut]
