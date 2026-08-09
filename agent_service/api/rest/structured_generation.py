"""Structured field generation REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from agent_service.api.rest.deps import _require_structured_generation_service
from agent_service.schemas.structured_generation import StructuredGenerationRequest, StructuredGenerationResponse

router = APIRouter()


@router.post("/structured-generation/fields")
async def generate_structured_fields(payload: StructuredGenerationRequest) -> StructuredGenerationResponse:
    """根据上下文和字段定义生成结构化字段值。"""

    try:
        return await run_in_threadpool(_require_structured_generation_service().generate_fields, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
