"""AgentService REST 接口层 — 按领域拆分路由模块。"""

from fastapi import APIRouter

from agent_service.api.rest.health import router as health_router
from agent_service.api.rest.sessions import router as sessions_router
from agent_service.api.rest.agent import router as agent_router

router = APIRouter()
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(agent_router)

__all__ = ["router"]
