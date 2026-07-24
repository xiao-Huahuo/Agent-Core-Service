"""AgentService REST 接口层 — 按领域拆分路由模块。"""

from fastapi import APIRouter

from agent_service.api.rest.health import router as health_router
from agent_service.api.rest.sessions import router as sessions_router
from agent_service.api.rest.agent import router as agent_router
from agent_service.api.rest.debug import router as debug_router
from agent_service.api.rest.knowledge import router as knowledge_router
from agent_service.api.rest.settings import router as settings_router
from agent_service.api.rest.token_usage import router as token_usage_router
from agent_service.api.rest.todo import router as todo_router

router = APIRouter()
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(agent_router)
router.include_router(debug_router)
router.include_router(knowledge_router)
router.include_router(settings_router)
router.include_router(token_usage_router)
router.include_router(todo_router)

__all__ = ["router"]
