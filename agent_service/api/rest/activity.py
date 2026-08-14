"""
Daily activity heatmap REST endpoint.

Usage:
Dashboard clients request the current user's persisted, capped activity rows
for up to 371 days and render category filters locally from one response.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from agent_service.api.rest.deps import _require_activity_service
from agent_service.schemas.activity import ActivityHeatmapOut

router = APIRouter()


@router.get("/activity/heatmap", response_model=ActivityHeatmapOut)
async def get_activity_heatmap(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    days: int = Query(default=371, ge=7, le=371, description="统计天数"),
    timezone_name: str = Query(default="Asia/Shanghai", alias="timezone", description="IANA 时区"),
) -> dict[str, Any]:
    """Return the user's persisted daily activity heatmap and filter summaries."""

    service = _require_activity_service()
    await run_in_threadpool(service.sync_existing_records, user_id=user_id)
    return await run_in_threadpool(
        service.get_heatmap,
        user_id=user_id,
        days=days,
        timezone_name=timezone_name,
    )
