"""REST endpoints for persisted Agent turn changes and guarded undo."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from agent_service.api.rest.deps import _require_agent_change_service

router = APIRouter(prefix="/sessions", tags=["agent-changes"])


@router.get("/{session_id}/changes")
async def get_latest_agent_change(session_id: str) -> dict[str, Any]:
    """Return the latest finalized Agent change snapshot for one session."""

    snapshot = await run_in_threadpool(
        _require_agent_change_service().latest_for_session,
        session_id=session_id,
    )
    return {"change_snapshot": snapshot}


@router.post("/{session_id}/changes/{snapshot_id}/undo")
async def undo_agent_change(session_id: str, snapshot_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Undo one snapshot after validating its session and user ownership."""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    current = await run_in_threadpool(
        _require_agent_change_service().latest_for_session,
        session_id=session_id,
    )
    if current is None or current.get("snapshot_id") != snapshot_id:
        raise HTTPException(status_code=404, detail="change snapshot not found")
    try:
        snapshot = await run_in_threadpool(
            _require_agent_change_service().undo_snapshot,
            snapshot_id=snapshot_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"change_snapshot": snapshot}
