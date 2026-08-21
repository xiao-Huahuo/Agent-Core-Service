"""图书馆虚拟编目 REST 端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.api.rest.deps import _require_library_service

router = APIRouter()


@router.get("/library/items")
async def list_library_items(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="用户 ID"),
    parent_id: str = Query("", description="虚拟集锦 ID"),
    query: str = Query("", description="名称、描述或真实文件名查找"),
    tag: str = Query("", description="标签名"),
    content_type: str = Query("", description="真实内容类型"),
    sort: str = Query("updated_at", description="排序字段"),
    direction: str = Query("desc", description="asc/desc"),
) -> dict[str, Any]:
    """列出图书馆虚拟条目。"""

    try:
        return await run_in_threadpool(
            _require_library_service().list_items,
            user_id=user_id,
            parent_id=parent_id,
            query=query,
            tag=tag,
            content_type=content_type,
            sort=sort,
            direction=direction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/library/tags")
async def list_library_tags(user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="用户 ID")) -> dict[str, Any]:
    """列出当前 active 知识库的图书馆标签。"""

    try:
        return await run_in_threadpool(_require_library_service().list_tags, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/library/items/book")
async def create_library_book(body: dict[str, Any]) -> dict[str, Any]:
    """创建虚拟图书条目。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    try:
        return await run_in_threadpool(
            _require_library_service().create_item,
            user_id=user_id,
            parent_id=str(body.get("parent_id") or ""),
            content_type=str(body.get("content_type") or "knowledge_file"),
            source_path=str(body.get("source_path") or ""),
            source_url=str(body.get("source_url") or ""),
            title=str(body.get("title") or ""),
            description=str(body.get("description") or ""),
            cover_mode=str(body.get("cover_mode") or "icon"),
            cover_asset_id=str(body.get("cover_asset_id") or ""),
            tags=[str(tag) for tag in body.get("tags", [])] if isinstance(body.get("tags"), list) else [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/library/items/collection")
async def create_library_collection(body: dict[str, Any]) -> dict[str, Any]:
    """创建虚拟集锦。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    try:
        return await run_in_threadpool(
            _require_library_service().create_collection,
            user_id=user_id,
            parent_id=str(body.get("parent_id") or ""),
            title=str(body.get("title") or ""),
            description=str(body.get("description") or ""),
            cover_mode=str(body.get("cover_mode") or "icon"),
            cover_asset_id=str(body.get("cover_asset_id") or ""),
            tags=[str(tag) for tag in body.get("tags", [])] if isinstance(body.get("tags"), list) else [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/library/items/{item_id}")
async def update_library_item(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """更新图书馆虚拟条目。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    payload = dict(body)
    payload.pop("user_id", None)
    try:
        return await run_in_threadpool(
            _require_library_service().update_item,
            user_id=user_id,
            item_id=item_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/library/items/{item_id}")
async def delete_library_item(
    item_id: str,
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="用户 ID"),
) -> dict[str, Any]:
    """将条目移出图书馆,不删除真实文件。"""

    try:
        return await run_in_threadpool(_require_library_service().delete_item, user_id=user_id, item_id=item_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/library/assets/cover")
async def upload_library_cover(
    user_id: str = Form(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """上传图书馆封面图片。"""

    content = await file.read()
    try:
        return await run_in_threadpool(
            _require_library_service().upload_cover,
            user_id=user_id,
            filename=file.filename or "cover.bin",
            content=content,
            mime_type=file.content_type or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
