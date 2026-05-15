"""
REST 路由共享依赖。

由 main.py 在 lifespan 启动后注入 AgentCore / SessionService / MessageService,
各子路由模块通过 _require_* 助手按需获取,未注入时抛出 503。
"""

from __future__ import annotations

from fastapi import HTTPException

from agent_service.agent_core.agent_core import AgentCore
from agent_service.services.message_service import MessageService
from agent_service.services.session_service import SessionService

_agent: AgentCore | None = None
_session_service: SessionService | None = None
_message_service: MessageService | None = None


def _require_agent() -> AgentCore:
    if _agent is None:
        raise HTTPException(status_code=503, detail="AgentCore not initialized yet")
    return _agent


def _require_session_service() -> SessionService:
    if _session_service is None:
        raise HTTPException(status_code=503, detail="SessionService not initialized yet")
    return _session_service


def _require_message_service() -> MessageService:
    if _message_service is None:
        raise HTTPException(status_code=503, detail="MessageService not initialized yet")
    return _message_service
