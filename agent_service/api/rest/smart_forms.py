"""Smart form REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.api.rest.deps import _require_smart_form_service
from agent_service.schemas.smart_form import SmartFormOut, SmartFormSaveRequest

router = APIRouter()


@router.get("/smart-forms/list")
async def list_smart_forms(user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)) -> list[dict]:
    """列出用户智能表格。"""

    try:
        return await run_in_threadpool(_require_smart_form_service().list_forms, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/smart-forms/{form_id}")
async def get_smart_form(form_id: str, user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)) -> SmartFormOut:
    """读取单张智能表格。"""

    try:
        result = await run_in_threadpool(_require_smart_form_service().get_form, user_id=user_id, form_id=form_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Smart form not found")
    return SmartFormOut(**result)


@router.post("/smart-forms/save")
async def save_smart_form(payload: SmartFormSaveRequest) -> SmartFormOut:
    """创建或覆盖保存智能表格。"""

    try:
        result = await run_in_threadpool(
            _require_smart_form_service().save_form,
            user_id=payload.user_id,
            form_id=payload.form_id,
            asset_dir=payload.asset_dir,
            form=payload.form,
        )
        return SmartFormOut(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/smart-forms/{form_id}", status_code=204)
async def delete_smart_form(form_id: str, user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)) -> Response:
    """删除当前用户拥有的智能表格。"""

    try:
        deleted = await run_in_threadpool(
            _require_smart_form_service().delete_form,
            user_id=user_id,
            form_id=form_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Smart form not found")
    return Response(status_code=204)
