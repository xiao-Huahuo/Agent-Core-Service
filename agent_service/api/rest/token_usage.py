"""
Token usage REST endpoints.

Usage:
The dashboard calls this module to read persisted token call rows, uniform
time-bucket totals, and per-session totals.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.services.token_usage_service import SUPPORTED_INTERVALS, TokenUsageService

router = APIRouter()


@router.get("/agent/token-usage")
async def get_agent_token_usage(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="用户 ID"),
    session_id: str | None = Query(default=None, description="可选 session ID,用于每次调用表过滤"),
    interval: str = Query(default="5m", description="时间聚合刻度"),
    limit: int = Query(
        default=DEFAULT_BUSINESS_LIMITS.token_usage_default_limit,
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.token_usage_max_limit,
        description="每次调用表返回上限",
    ),
    lookback_hours: int | None = Query(default=None, description="时间刻度范围筛选(小时数,为空不过滤)"),
    session_sort: str = Query(default="time", description="Session 排序方式: time|tokens"),
) -> dict[str, Any]:
    """Return persisted Agent token usage statistics."""

    service = TokenUsageService(config=AgentConfig.load_config())
    interval_key = interval if interval in SUPPORTED_INTERVALS else "5m"
    return service.get_dashboard_stats(
        user_id=user_id,
        session_id=session_id,
        interval=interval_key,
        limit=limit,
        lookback_hours=lookback_hours,
        session_sort=session_sort,
    )
