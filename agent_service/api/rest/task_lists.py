"""Session task list endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from agent_service.api.rest.deps import _require_task_list_service

router = APIRouter()


@router.get("/sessions/{session_id}/task-list")
async def get_session_task_list(session_id: str) -> dict[str, Any]:
    """Return the current task list for a session."""

    task_list = _require_task_list_service().get_task_list(session_id)
    return {"task_list": task_list}


@router.post("/sessions/{session_id}/task-list")
async def create_session_task_list(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Create a new task list for a session."""

    raw_items = body.get("items")
    if isinstance(raw_items, str):
        items = [line.strip("- \t") for line in raw_items.splitlines() if line.strip("- \t")]
    elif isinstance(raw_items, list):
        items = [str(item).strip() for item in raw_items if str(item).strip()]
    else:
        items = []
    if not items:
        raise HTTPException(status_code=422, detail="items is required")
    try:
        task_list = _require_task_list_service().create_task_list(
            session_id=session_id,
            title=str(body.get("title") or ""),
            items=items,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"task_list": task_list}


@router.post("/sessions/{session_id}/task-list/complete-item")
async def complete_session_task_list_item(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Mark a session task list item complete."""

    item_id = str(body.get("item_id") or "").strip()
    completion_summary = str(body.get("completion_summary") or "").strip()
    if not item_id or not completion_summary:
        raise HTTPException(status_code=422, detail="item_id and completion_summary are required")
    try:
        task_list = _require_task_list_service().complete_task_list_item(
            session_id=session_id,
            item_id=item_id,
            completion_summary=completion_summary,
            next_item_id=str(body.get("next_item_id") or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"task_list": task_list}


@router.post("/sessions/{session_id}/task-list/finish")
async def finish_session_task_list(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Finish a session task list."""

    try:
        task_list = _require_task_list_service().finish_task_list(
            session_id=session_id,
            final_summary=str(body.get("final_summary") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"task_list": task_list}
