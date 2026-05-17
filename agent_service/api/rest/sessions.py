"""
Session 管理端点。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_message_service, _require_session_service
from agent_service.schemas.session import SessionCreate, SessionUpdate

router = APIRouter()


@router.get("/sessions")
async def list_sessions(user_id: str = Query(..., min_length=1, description="用户 ID")) -> list[dict[str, Any]]:
    """列出指定用户的所有会话,按更新时间倒序。"""
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
    """创建新会话。body: user_id (必填), session_name (可选)。"""
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    session_name = body.get("session_name")
    service = _require_session_service()
    session = service.create_session(SessionCreate(user_id=str(user_id), session_name=session_name))
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取指定会话详情。"""
    service = _require_session_service()
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """删除指定会话。"""
    service = _require_session_service()
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "deleted_count": 1}


@router.delete("/sessions")
async def clear_all_sessions(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """清空指定用户的所有会话。"""
    service = _require_session_service()
    count = service.delete_all_user_sessions(user_id)
    return {"ok": True, "deleted_count": count}


@router.put("/sessions/{session_id}/name")
async def update_session_name(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """更新会话显示名称。body: session_name 字段。"""
    session_name = body.get("session_name")
    if not session_name:
        raise HTTPException(status_code=422, detail="session_name is required")
    service = _require_session_service()
    session = service.update_session_name(session_id, SessionUpdate(session_name=str(session_name)))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
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
    """获取指定会话的消息历史。"""
    ms = _require_message_service()
    messages = ms.list_session_messages(user_id=user_id, session_id=session_id, limit=limit)
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
