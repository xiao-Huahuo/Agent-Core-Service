"""Smart form REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.api.rest.deps import _require_smart_form_service
from agent_service.schemas.smart_form import SmartFormOut, SmartFormSaveRequest

router = APIRouter()


@router.get("/literature-reading/entries")
async def list_literature_entries(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
    library_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
) -> list[dict]:
    """列出当前知识库中由智能文献表行派生的阅读条目。"""

    try:
        return await run_in_threadpool(
            _require_smart_form_service().list_literature_entries,
            user_id=user_id,
            library_id=library_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/literature-reading/{form_id}/rows/{row_id}/view")
async def touch_literature_entry(
    form_id: str,
    row_id: str,
    user_id: str = Body(...),
    library_id: str = Body(...),
) -> dict:
    """记录一条表格文献的最近浏览时间。"""

    try:
        return await run_in_threadpool(
            _require_smart_form_service().touch_literature_entry,
            user_id=user_id,
            library_id=library_id,
            form_id=form_id,
            row_id=row_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/literature-reading/{form_id}/rows/{row_id}")
async def patch_literature_row(form_id: str, row_id: str, payload: dict = Body(...)) -> SmartFormOut:
    """增量更新文献行的指定单元格。"""

    try:
        result = await run_in_threadpool(
            _require_smart_form_service().patch_literature_row,
            user_id=str(payload.get("user_id") or ""),
            form_id=form_id,
            row_id=row_id,
            cells=dict(payload.get("cells") or {}),
        )
        return SmartFormOut(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/literature-reading/{form_id}/rows/{row_id}/duplicate")
async def duplicate_literature_row(form_id: str, row_id: str, user_id: str = Body(..., embed=True)) -> SmartFormOut:
    """复制文献行及其真实文件。"""

    try:
        result = await run_in_threadpool(
            _require_smart_form_service().duplicate_literature_row,
            user_id=user_id,
            form_id=form_id,
            row_id=row_id,
        )
        return SmartFormOut(**result)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/literature-reading/{form_id}/rows/{row_id}", status_code=204)
async def delete_literature_row(
    form_id: str,
    row_id: str,
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
    delete_file: bool = Query(default=True),
) -> Response:
    """删除文献行，并按请求同步删除真实文件。"""

    try:
        deleted = await run_in_threadpool(
            _require_smart_form_service().delete_literature_row,
            user_id=user_id,
            form_id=form_id,
            row_id=row_id,
            delete_file=delete_file,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Literature row not found")
    return Response(status_code=204)


@router.get("/smart-forms/list")
async def list_smart_forms(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
    library_id: str = Query(default=""),
    form_kind: str = Query(default=""),
) -> list[dict]:
    """列出用户智能表格。"""

    try:
        return await run_in_threadpool(
            _require_smart_form_service().list_forms,
            user_id=user_id,
            library_id=library_id,
            form_kind=form_kind,
        )
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
            library_id=payload.library_id,
            form_kind=payload.form_kind,
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
