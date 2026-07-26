"""Skill management REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_skill_service

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillEnabledRequest(BaseModel):
    user_id: str = Field(default="default")
    enabled: bool


class SkillCreateRequest(BaseModel):
    user_id: str = Field(default="default")
    name: str
    description: str = ""
    body: str = ""


@router.get("")
def list_skills(user_id: str = Query(default="default")) -> dict[str, object]:
    service = _require_skill_service()
    skills = service.list_skills(user_id=user_id)
    return {"skills": skills, "count": len(skills)}


@router.post("/{skill_id}/enabled")
def set_skill_enabled(skill_id: str, payload: SkillEnabledRequest) -> dict[str, object]:
    service = _require_skill_service()
    return service.set_skill_enabled(user_id=payload.user_id, skill_id=skill_id, enabled=payload.enabled)


@router.post("")
def create_skill(payload: SkillCreateRequest) -> dict[str, object]:
    service = _require_skill_service()
    try:
        skill = service.create_user_skill(
            user_id=payload.user_id,
            name=payload.name,
            description=payload.description,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"skill": skill}


@router.get("/spec")
def get_skill_spec() -> dict[str, str]:
    service = _require_skill_service()
    return {"spec": service.spec_text()}
