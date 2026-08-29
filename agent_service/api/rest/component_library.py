"""Component library REST endpoints for listing and uploading live components."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.api.rest.deps import _require_component_library_service
from agent_service.schemas.component_library import ComponentLibraryItemCreate, ComponentLibraryItemUpdate

router = APIRouter()


@router.get("/component-library/components")
async def list_component_library_items(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="用户 ID"),
    tag: str = Query("any", description="固定组件标签；any 表示全部"),
) -> dict[str, Any]:
    """List component files from the current user's active knowledge library."""

    try:
        return await run_in_threadpool(
            _require_component_library_service().list_components,
            user_id=user_id,
            tag=tag,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/component-library/components")
async def create_component_library_item(body: ComponentLibraryItemCreate) -> dict[str, Any]:
    """Persist one Vue SFC or standalone HTML file below knowledge/components."""

    try:
        return await run_in_threadpool(
            _require_component_library_service().create_component,
            user_id=body.user_id,
            source=body.source,
            tag=body.tag,
            filename=body.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/component-library/components")
async def rename_component_library_item(body: ComponentLibraryItemUpdate) -> dict[str, Any]:
    """Persist an incremental component title, source, or tag update."""

    try:
        return await run_in_threadpool(
            _require_component_library_service().update_component,
            user_id=body.user_id,
            component_id=body.component_id,
            title=body.title,
            source=body.source,
            tag=body.tag,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/component-library/components")
async def delete_component_library_item(
    user_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="用户 ID"),
    component_id: str = Query(..., min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, description="组件 ID"),
) -> dict[str, object]:
    """Delete one canonical component file from the active component library."""

    try:
        return await run_in_threadpool(
            _require_component_library_service().delete_component,
            user_id=user_id,
            component_id=component_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
