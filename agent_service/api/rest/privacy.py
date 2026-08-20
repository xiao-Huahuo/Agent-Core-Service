"""Privacy REST endpoints.

Usage:
The editor lists, creates, and deletes private knowledge/library targets through
the shared /privacy route.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from agent_service.api.rest.deps import _require_privacy_service
from agent_service.schemas.privacy import PrivacyCreate, PrivacyListOut, PrivacyOut, PrivacyTargetType

router = APIRouter()


@router.get("/privacy")
async def list_privacy(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    target_type: PrivacyTargetType | None = Query(None, description="隐私目标类型"),
    library_id: str | None = Query(None, description="知识库作用域;不传则不过滤"),
) -> PrivacyListOut:
    """List privacy flags for a user and optional library/type scope."""

    try:
        privacy = await run_in_threadpool(
            _require_privacy_service().list_privacy,
            user_id=user_id,
            target_type=target_type,
            library_id=library_id,
        )
        return PrivacyListOut(privacy=privacy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/privacy")
async def add_privacy(payload: PrivacyCreate) -> PrivacyOut:
    """Create an idempotent privacy flag."""

    try:
        return await run_in_threadpool(_require_privacy_service().add_privacy, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/privacy")
async def delete_privacy(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    target_type: PrivacyTargetType = Query(..., description="隐私目标类型"),
    target_id: str = Query(..., min_length=1, description="隐私目标 ID"),
    library_id: str = Query("", description="知识库作用域"),
) -> dict[str, bool]:
    """Delete one privacy flag."""

    try:
        deleted = await run_in_threadpool(
            _require_privacy_service().delete_privacy,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            library_id=library_id,
        )
        return {"ok": True, "deleted": deleted}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
