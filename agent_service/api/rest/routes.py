"""
AgentService REST 路由。

提供 FastAPI 端点:
- GET /          健康检查
- GET /agent/test  快速 LLM 连通性测试

注: _agent 引用由 main.py 在 lifespan 启动阶段注入,路由加载时可能为 None。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.agent_core.agent_core import AgentCore

router = APIRouter()

# 由 main.py 在 lifespan 启动后注入,避免循环导入。
_agent: AgentCore | None = None


@router.get("/")
async def root() -> dict[str, str]:
    """健康检查。"""

    return {"message": "Agent-Core-Service is running"}


@router.get("/agent/test")
async def agent_test(prompt: str = Query(default="你好,请用一句话回复。")) -> dict[str, Any]:
    """运行一次真实 LLM 调用,用于快速验证模型连接和 Agent 链路是否正常。"""

    if _agent is None:
        raise HTTPException(status_code=503, detail="AgentCore not initialized yet")
    return _agent.run_once(prompt=prompt, user_id="test-user", session_id="test-session")
