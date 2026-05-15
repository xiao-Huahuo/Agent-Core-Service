"""
健康检查 / 快速测试端点。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from agent_service.api.rest.deps import _require_agent

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    """健康检查。"""
    return {"message": "Agent-Core-Service is running"}


@router.get("/agent/test")
async def agent_test(prompt: str = Query(default="你好,请用一句话回复。")) -> dict[str, Any]:
    """运行一次真实 LLM 调用,快速验证模型连通性。"""
    return _require_agent().run_once(prompt=prompt, user_id="test-user", session_id="test-session")
