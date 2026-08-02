"""定时自动化任务 REST 接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_automation_service

router = APIRouter()


@router.get("/automation/list")
async def api_list_automations(user_id: str = Query(..., min_length=1)) -> list[dict[str, Any]]:
    """列出用户的自动化任务。"""

    return _require_automation_service().list_tasks(user_id=user_id)


@router.post("/automation/add")
async def api_add_automation(body: dict[str, Any]) -> dict[str, Any]:
    """创建一个定时唤醒 Agent 的自动化任务。"""

    user_id = body.get("user_id")
    text = body.get("text")
    if not user_id or not text:
        raise HTTPException(status_code=422, detail="user_id and text are required")
    try:
        return _require_automation_service().create_task(
            user_id=str(user_id),
            text=str(text),
            prompt=str(body.get("prompt") or ""),
            next_run_at=str(body.get("next_run_at") or ""),
            timezone_name=str(body.get("timezone") or "UTC"),
            recurrence=body.get("recurrence"),
            access_mode=str(body.get("access_mode") or "sandbox"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/automation/toggle")
async def api_toggle_automation(body: dict[str, Any]) -> dict[str, Any]:
    """启用或停用自动化任务。"""

    user_id = body.get("user_id")
    automation_id = body.get("automation_id")
    if not user_id or not automation_id or "enabled" not in body:
        raise HTTPException(status_code=422, detail="user_id, automation_id and enabled are required")
    task = _require_automation_service().set_enabled(
        user_id=str(user_id), automation_id=str(automation_id), enabled=bool(body["enabled"])
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Automation task not found")
    return task


@router.get("/automation/runs")
async def api_list_automation_runs(
    user_id: str = Query(..., min_length=1),
    automation_id: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """列出自动化任务最近的运行记录。"""

    return _require_automation_service().list_runs(
        user_id=str(user_id), automation_id=str(automation_id), limit=limit
    )


@router.post("/automation/delete")
async def api_delete_automation(body: dict[str, Any]) -> dict[str, Any]:
    """删除自动化任务及其关联 TODO。"""

    user_id = body.get("user_id")
    automation_id = body.get("automation_id")
    if not user_id or not automation_id:
        raise HTTPException(status_code=422, detail="user_id and automation_id are required")
    deleted = _require_automation_service().delete_task(
        user_id=str(user_id), automation_id=str(automation_id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Automation task not found")
    return {"deleted": True}
