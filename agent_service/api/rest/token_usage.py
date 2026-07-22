"""
Token usage REST endpoints.

Usage:
The dashboard calls this module to read persisted token call rows, uniform
time-bucket totals, and per-session totals.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from agent_service.core.agent_config import AgentConfig
from agent_service.services.token_usage_service import SUPPORTED_INTERVALS, TokenUsageService

router = APIRouter()


@router.get("/agent/token-usage")
async def get_agent_token_usage(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    session_id: str | None = Query(default=None, description="可选 session ID,用于每次调用表过滤"),
    interval: str = Query(default="5m", description="时间聚合刻度"),
    limit: int = Query(default=120, ge=1, le=500, description="每次调用表返回上限"),
) -> dict[str, Any]:
    """Return persisted Agent token usage statistics."""

    service = TokenUsageService(config=AgentConfig.load_config())
    interval_key = interval if interval in SUPPORTED_INTERVALS else "5m"
    return service.get_dashboard_stats(
        user_id=user_id,
        session_id=session_id,
        interval=interval_key,
        limit=limit,
    )
