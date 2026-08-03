"""Favorite REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from agent_service.api.rest.deps import _require_favorite_service
from agent_service.schemas.favorite import FavoriteCreate, FavoriteListOut, FavoriteOut, FavoriteTargetType

router = APIRouter()


@router.get("/favorites")
async def list_favorites(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    target_type: FavoriteTargetType | None = Query(None, description="收藏目标类型"),
    library_id: str | None = Query(None, description="知识库作用域;不传则不过滤"),
) -> FavoriteListOut:
    """列出指定用户的收藏。"""

    try:
        favorites = await run_in_threadpool(
            _require_favorite_service().list_favorites,
            user_id=user_id,
            target_type=target_type,
            library_id=library_id,
        )
        return FavoriteListOut(favorites=favorites)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/favorites")
async def add_favorite(payload: FavoriteCreate) -> FavoriteOut:
    """创建收藏;已存在时返回已有收藏。"""

    try:
        return await run_in_threadpool(_require_favorite_service().add_favorite, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/favorites")
async def delete_favorite(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    target_type: FavoriteTargetType = Query(..., description="收藏目标类型"),
    target_id: str = Query(..., min_length=1, description="收藏目标 ID"),
    library_id: str = Query("", description="知识库作用域"),
) -> dict[str, bool]:
    """删除指定收藏。"""

    try:
        deleted = await run_in_threadpool(
            _require_favorite_service().delete_favorite,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            library_id=library_id,
        )
        return {"ok": True, "deleted": deleted}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
