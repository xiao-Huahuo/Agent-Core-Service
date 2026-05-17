"""用户设置端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_settings_service

router = APIRouter()

# ---- 系统提示词条目 ----

@router.get("/settings/system-prompt")
async def list_system_prompt_entries(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出用户的所有系统提示词条目。"""
    svc = _require_settings_service()
    entries = svc.list_system_prompt_entries(user_id=user_id)
    return {"entries": entries}


@router.post("/settings/system-prompt/entries")
async def add_system_prompt_entry(body: dict[str, Any]) -> dict[str, Any]:
    """添加一条系统提示词条目。body: user_id, content。"""
    user_id = body.get("user_id")
    content = body.get("content")
    if not user_id or not content:
        raise HTTPException(status_code=422, detail="user_id and content are required")
    svc = _require_settings_service()
    return svc.add_system_prompt_entry(user_id=str(user_id), content=str(content))


@router.delete("/settings/system-prompt/entries/{prompt_id}")
async def delete_system_prompt_entry(prompt_id: str) -> dict[str, Any]:
    """删除指定的系统提示词条目。"""
    svc = _require_settings_service()
    deleted = svc.delete_system_prompt_entry(prompt_id=prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}

# ---- 自定义长期记忆 ----

@router.get("/settings/memories")
async def list_memories(user_id: str = Query(..., min_length=1, description="用户 ID")) -> list[dict[str, Any]]:
    """列出用户的自定义长期记忆。"""
    svc = _require_settings_service()
    return svc.list_memories(user_id=user_id)


@router.post("/settings/memories")
async def add_memory(body: dict[str, Any]) -> dict[str, Any]:
    """添加一条自定义长期记忆。body: user_id, content, importance (可选)。"""
    user_id = body.get("user_id")
    content = body.get("content")
    if not user_id or not content:
        raise HTTPException(status_code=422, detail="user_id and content are required")
    svc = _require_settings_service()
    return svc.add_memory(
        user_id=str(user_id),
        content=str(content),
        importance=float(body.get("importance", 0.5)),
    )


@router.delete("/settings/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """删除指定的自定义长期记忆。"""
    svc = _require_settings_service()
    deleted = svc.remove_memory(memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}
