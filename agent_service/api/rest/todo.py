"""TODO 端点。提供增删改查接口供前端调用。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_todo_service

router = APIRouter()


@router.get("/todo/list")
async def api_list_todos(user_id: str = Query(..., min_length=1)) -> list[dict[str, Any]]:
    """获取用户的所有待办。"""
    svc = _require_todo_service()
    return svc.list_todos(user_id=user_id)


@router.post("/todo/add")
async def api_add_todo(body: dict[str, Any]) -> dict[str, Any]:
    """新增待办。"""
    user_id = body.get("user_id")
    text = body.get("text")
    if not user_id or not text:
        raise HTTPException(status_code=422, detail="user_id and text are required")
    svc = _require_todo_service()
    try:
        return svc.add_todo(
            user_id=str(user_id),
            text=str(text),
            due_date=body.get("due_date"),
            reminder_at=body.get("reminder_at"),
            recurrence=body.get("recurrence"),
            category=str(body.get("category") or "task"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/todo/toggle")
async def api_toggle_todo(body: dict[str, Any]) -> dict[str, Any]:
    """切换待办状态。"""
    user_id = body.get("user_id")
    todo_id = body.get("todo_id")
    if not user_id or not todo_id:
        raise HTTPException(status_code=422, detail="user_id and todo_id are required")
    svc = _require_todo_service()
    item = svc.toggle_todo(user_id=str(user_id), todo_id=str(todo_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return item


@router.post("/todo/edit")
async def api_edit_todo(body: dict[str, Any]) -> dict[str, Any]:
    """编辑待办。"""
    user_id = body.get("user_id")
    todo_id = body.get("todo_id")
    text = body.get("text", "")
    if not user_id or not todo_id:
        raise HTTPException(status_code=422, detail="user_id and todo_id are required")
    svc = _require_todo_service()
    try:
        item = svc.edit_todo(
            user_id=str(user_id),
            todo_id=str(todo_id),
            text=str(text),
            due_date=body.get("due_date"),
            reminder_at=body.get("reminder_at"),
            recurrence=body.get("recurrence"),
            category=str(body["category"]) if "category" in body else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return item


@router.post("/todo/delete")
async def api_delete_todo(body: dict[str, Any]) -> dict[str, Any]:
    """删除待办；自动化类别统一交给其所属服务做完整级联删除。"""
    user_id = body.get("user_id")
    todo_id = body.get("todo_id")
    if not user_id or not todo_id:
        raise HTTPException(status_code=422, detail="user_id and todo_id are required")
    svc = _require_todo_service()
    ok = svc.delete_todo(user_id=str(user_id), todo_id=str(todo_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"deleted": True}
