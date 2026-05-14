"""
AgentService REST 路由。

提供 FastAPI 端点:
- GET  /                         健康检查
- GET  /agent/test                快速 LLM 连通性测试
- GET  /agent/stream              SSE 流式对话(带 session 上下文)
- GET  /agent/events              获取指定 session 的 trace 事件(供观测面板)
- GET  /sessions                  列出用户的所有会话
- POST /sessions                  创建新会话
- GET  /sessions/{session_id}/messages  获取会话消息历史

注: _agent / _session_service / _message_service 引用由 main.py 在 lifespan
启动阶段注入,路由加载时可能为 None。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from agent_service.agent_core.agent_core import AgentCore
from agent_service.schemas.message import MessageCreate
from agent_service.schemas.session import SessionCreate
from agent_service.services.message_service import MessageService
from agent_service.services.session_service import SessionService

router = APIRouter()
logger = logging.getLogger(__name__)

# 由 main.py 在 lifespan 启动后注入,避免循环导入。
_agent: AgentCore | None = None
_session_service: SessionService | None = None
_message_service: MessageService | None = None


def _require_agent() -> AgentCore:
    """获取已注入的 AgentCore 实例,未就绪时抛出 503。"""

    if _agent is None:
        raise HTTPException(status_code=503, detail="AgentCore not initialized yet")
    return _agent


def _require_session_service() -> SessionService:
    """获取已注入的 SessionService 实例,未就绪时抛出 503。"""

    if _session_service is None:
        raise HTTPException(status_code=503, detail="SessionService not initialized yet")
    return _session_service


def _require_message_service() -> MessageService:
    """获取已注入的 MessageService 实例,未就绪时抛出 503。"""

    if _message_service is None:
        raise HTTPException(status_code=503, detail="MessageService not initialized yet")
    return _message_service


# ------------------------------------------------------------------
# 健康检查 / 测试
# ------------------------------------------------------------------


@router.get("/")
async def root() -> dict[str, str]:
    """健康检查。"""

    return {"message": "Agent-Core-Service is running"}


@router.get("/agent/test")
async def agent_test(prompt: str = Query(default="你好,请用一句话回复。")) -> dict[str, Any]:
    """运行一次真实 LLM 调用,用于快速验证模型连接和 Agent 链路是否正常。"""

    return _require_agent().run_once(prompt=prompt, user_id="test-user", session_id="test-session")


# ------------------------------------------------------------------
# Session 管理
# ------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(user_id: str = Query(..., min_length=1, description="用户 ID")) -> list[dict[str, Any]]:
    """
    列出指定用户的所有会话,按更新时间倒序排列。

    user_id: 用户 ID。
    """

    service = _require_session_service()
    sessions = service.list_user_sessions(user_id)
    return [
        {
            "session_id": s.session_id,
            "user_id": s.user_id,
            "session_name": s.session_name,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.post("/sessions")
async def create_session(body: dict[str, Any]) -> dict[str, Any]:
    """
    创建新会话。

    body: 可包含 user_id (必填) 和 session_name (可选)。
    """

    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    session_name = body.get("session_name")
    service = _require_session_service()
    session = service.create_session(
        SessionCreate(user_id=str(user_id), session_name=session_name)
    )
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    limit: int = Query(default=50, ge=1, le=200, description="返回消息数量上限"),
) -> list[dict[str, Any]]:
    """
    获取指定会话的消息历史,供前端聊天面板加载历史记录。

    session_id: 会话 ID。
    user_id: 用户 ID,用于校验消息归属。
    limit: 返回数量上限,默认 50。
    """

    ms = _require_message_service()
    messages = ms.list_recent_messages(user_id=user_id, session_id=session_id, limit=limit)
    return [
        {
            "message_id": m.message_id,
            "session_id": m.session_id,
            "user_id": m.user_id,
            "role": m.role,
            "content": m.content,
            "tool_calls": m.tool_calls_json,
            "metadata": m.metadata_json,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# ------------------------------------------------------------------
# Agent 流式对话 (SSE)
# ------------------------------------------------------------------


@router.get("/agent/stream")
async def agent_stream(
    prompt: str = Query(..., min_length=1, description="用户输入"),
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    session_id: str = Query(..., min_length=1, description="会话 ID"),
) -> StreamingResponse:
    """
    SSE 流式对话接口。

    通过 Server-Sent Events 将 Agent 每个节点的执行结果实时推送到前端。
    事件流格式: data: <json>\n\n, 以 data: [DONE]\n\n 结束。

    prompt: 用户本轮输入。
    user_id: 用户 ID。
    session_id: 会话 ID,同一 session 内自动加载历史上下文。
    """

    agent = _require_agent()

    def _event_generator():
        try:
            for chunk in agent.stream_session_prompt(
                prompt=prompt,
                user_id=user_id,
                session_id=session_id,
            ):
                yield chunk
        except Exception:
            logger.exception(
                "SSE 流式对话异常 | user=%s session=%s",
                user_id,
                session_id,
            )
            error_payload = json.dumps(
                {"error": "internal server error"}, ensure_ascii=False
            )
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ------------------------------------------------------------------
# Agent 事件 / 观测接口
# ------------------------------------------------------------------


@router.get("/agent/events")
async def agent_events(
    session_id: str = Query(..., min_length=1, description="会话 ID"),
    user_id: str = Query(..., min_length=1, description="用户 ID"),
) -> dict[str, Any]:
    """
    获取指定会话的最新执行 trace 事件,供前端观测面板使用。

    从消息表中提取带有 node 信息的 metadata_json,按时间序排列,
    并合并成节点事件列表,用于还原智能体思考轨迹。

    session_id: 会话 ID。
    user_id: 用户 ID。
    """

    ms = _require_message_service()
    messages = ms.list_recent_messages(user_id=user_id, session_id=session_id, limit=200)

    events: list[dict[str, Any]] = []
    for m in messages:
        meta = m.metadata_json or {}
        node_name = meta.get("node", "")
        if not node_name:
            continue
        event = {
            "message_id": m.message_id,
            "role": m.role,
            "node": node_name,
            "content": m.content[:500] if m.role in ("assistant", "tool", "system") else "",
            "tool_calls": m.tool_calls_json,
            "created_at": m.created_at.isoformat(),
            "metadata": meta,
        }
        events.append(event)

    return {
        "session_id": session_id,
        "user_id": user_id,
        "event_count": len(events),
        "events": events,
    }
