"""REST endpoints for the persistent Agent task queue.

Usage:
All task mutations are validated with queue DTOs and delegated to the shared
service; the gRPC transport calls the same service methods.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_agent, _require_agent_queue_service
from agent_service.schemas.agent_queue import (
    AgentQueueSettingsUpdate,
    AgentQueueTaskContinue,
    AgentQueueTaskCreate,
    AgentQueueTaskTransitionRequest,
    AgentQueueTaskUpdate,
)

router = APIRouter()


@router.get("/agent-queue/tasks")
async def list_tasks(user_id: str = Query(..., min_length=1), history: bool = False) -> dict[str, Any]:
    """List the live board or terminal history for one user."""
    service = _require_agent_queue_service()
    return {"tasks": service.list_tasks(user_id=user_id, history=history), "settings": service.get_settings(user_id)}


@router.post("/agent-queue/tasks")
async def create_task(body: AgentQueueTaskCreate) -> dict[str, Any]:
    """Persist a pending task bound to its dedicated attachment session."""
    return _require_agent_queue_service().create_task(**body.model_dump())


@router.put("/agent-queue/tasks/{task_id}")
async def update_task(task_id: str, body: AgentQueueTaskUpdate) -> dict[str, Any]:
    """Edit a not-yet-claimed task and replace its attachment references."""
    try:
        task = _require_agent_queue_service().update_task(task_id=task_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/agent-queue/tasks/{task_id}/continue")
async def continue_task(task_id: str, body: AgentQueueTaskContinue) -> dict[str, Any]:
    """Queue a follow-up prompt in the reviewed task's retained session."""
    try:
        task = _require_agent_queue_service().restart_task(task_id=task_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/agent-queue/tasks/{task_id}/transition")
async def transition_task(task_id: str, body: AgentQueueTaskTransitionRequest) -> dict[str, Any]:
    """Confirm a result or terminate its live Agent session."""
    task = _require_agent_queue_service().transition(task_id=task_id, **body.model_dump())
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if body.status == "terminated" and task.get("session_id"):
        _require_agent().cancel_session(str(task["session_id"]))
    return task


@router.delete("/agent-queue/tasks/{task_id}")
async def delete_task(task_id: str, user_id: str = Query(..., min_length=1)) -> dict[str, bool]:
    """Delete an unclaimed task; live work must use termination instead."""
    try:
        deleted = _require_agent_queue_service().delete_task(user_id=user_id, task_id=task_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="task not found")
    return {"deleted": True}


@router.put("/agent-queue/settings")
async def update_settings(body: AgentQueueSettingsUpdate) -> dict[str, Any]:
    """Persist one user's maximum concurrent Agent jobs."""
    return _require_agent_queue_service().update_settings(**body.model_dump())
