"""用户设置端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_knowledge_library_service, _require_settings_service

router = APIRouter()

# ---- 系统提示词条目 ----

@router.get("/settings/profile")
async def get_user_profile(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取或初始化用户设置档案。"""
    svc = _require_settings_service()
    try:
        return svc.ensure_user_profile(user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/settings/profile")
async def ensure_user_profile(body: dict[str, Any]) -> dict[str, Any]:
    """根据 user_id 获取或初始化用户设置档案。"""
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    svc = _require_settings_service()
    try:
        return svc.ensure_user_profile(user_id=str(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/settings/profile/knowledge-dir")
async def update_user_knowledge_dir(body: dict[str, Any]) -> dict[str, Any]:
    """
    更新用户 active 知识库目录并持久化。

    body: user_id 必填,knowledge_dir 必填,name 可选。该接口只更新设置,不执行灌库。
    """

    user_id = str(body.get("user_id") or "").strip()
    knowledge_dir = str(body.get("knowledge_dir") or "").strip()
    name = str(body.get("name") or "").strip() or None
    if not user_id or not knowledge_dir:
        raise HTTPException(status_code=422, detail="user_id and knowledge_dir are required")
    svc = _require_settings_service()
    try:
        return svc.update_knowledge_dir(user_id=user_id, knowledge_dir=knowledge_dir, name=name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/settings/knowledge-ingestion")
async def get_knowledge_ingestion_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取知识库灌库配置。"""

    svc = _require_settings_service()
    return svc.get_knowledge_ingestion_config(user_id=user_id)


@router.put("/settings/knowledge-ingestion")
async def save_knowledge_ingestion_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存知识库灌库配置。body: user_id 必填,auto_ingest_on_upload/ocr_enabled 可选。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    svc = _require_settings_service()
    result = svc.save_knowledge_ingestion_config(
        user_id=user_id,
        auto_ingest_on_upload=body.get("auto_ingest_on_upload"),
        ocr_enabled=body.get("ocr_enabled"),
        knowledge_ignore_patterns=body.get("knowledge_ignore_patterns"),
    )
    if "knowledge_ignore_patterns" in body:
        try:
            cleanup_result = _require_knowledge_library_service().cleanup_ignored_sources(user_id=user_id)
            result["ignore_cleanup"] = cleanup_result
        except RuntimeError:
            result["ignore_cleanup"] = {"files_seen": 0, "chunks_deleted": 0}
    return result

@router.get("/settings/system-prompt")
async def list_system_prompt_entries(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出用户的所有系统提示词条目。"""
    svc = _require_settings_service()
    entries = svc.list_system_prompt_entries(user_id=user_id)
    return {"entries": entries}


@router.post("/settings/system-prompt/entries")
async def add_system_prompt_entry(body: dict[str, Any]) -> dict[str, Any]:
    """添加一条系统提示词条目。body: user_id, content。"""
    user_id = body.get("user_id")
    content = body.get("content")
    if not user_id or not content:
        raise HTTPException(status_code=422, detail="user_id and content are required")
    svc = _require_settings_service()
    return svc.add_system_prompt_entry(user_id=str(user_id), content=str(content))


@router.delete("/settings/system-prompt/entries/{prompt_id}")
async def delete_system_prompt_entry(prompt_id: str) -> dict[str, Any]:
    """删除指定的系统提示词条目。"""
    svc = _require_settings_service()
    deleted = svc.delete_system_prompt_entry(prompt_id=prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}


# ---- 用户 LLM 配置 ----

@router.get("/settings/model-config")
async def get_llm_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户的 LLM 配置（返回明文 API Key）。"""
    svc = _require_settings_service()
    return svc.get_llm_config(user_id=user_id)


@router.put("/settings/model-config")
async def save_llm_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户的 LLM 配置。body: user_id 必填，其余字段可选。"""
    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    def _unwrap(value: Any) -> str | None:
        if value is None or isinstance(value, bool):
            return None
        s = str(value).strip()
        return s if s else None

    svc = _require_settings_service()
    return svc.save_llm_config(
        user_id=user_id,
        api_key=_unwrap(body.get("api_key")),
        base_url=_unwrap(body.get("base_url")),
        model_name=_unwrap(body.get("model_name")),
        small_api_key=_unwrap(body.get("small_api_key")),
        small_base_url=_unwrap(body.get("small_base_url")),
        small_model_name=_unwrap(body.get("small_model_name")),
    )


# ---- 联网搜索配置 ----

@router.get("/settings/web-search")
async def get_web_search_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户的联网搜索配置（代理地址 + 开关状态）。"""
    svc = _require_settings_service()
    return svc.get_web_search_config(user_id=user_id)


@router.put("/settings/web-search")
async def save_web_search_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户的联网搜索配置。body: user_id 必填，其余字段可选。"""
    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")

    def _unwrap(value: Any) -> str | None:
        if value is None or isinstance(value, bool):
            return None
        s = str(value).strip()
        return s if s else None

    svc = _require_settings_service()
    return svc.save_web_search_config(
        user_id=user_id,
        proxy_url=_unwrap(body.get("proxy_url")),
        web_search_enabled=body.get("web_search_enabled"),
    )


# ---- 可开关工具 ----

@router.get("/settings/disabled-tools")
async def get_disabled_tools(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户关闭的工具名称列表。"""
    svc = _require_settings_service()
    return {"disabled_tools": svc.get_disabled_tools(user_id=user_id)}


@router.put("/settings/disabled-tools")
async def save_disabled_tools(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户关闭的工具列表。body: user_id 必填, tool_names 为关闭的工具名称数组。"""
    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    raw_tool_names = body.get("tool_names", [])
    tool_names = [str(name) for name in raw_tool_names if isinstance(name, str) and name.strip()]
    svc = _require_settings_service()
    return {"disabled_tools": svc.save_disabled_tools(user_id=user_id, tool_names=tool_names)}


@router.get("/settings/available-tools")
async def list_available_tools(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出全部内置工具及当前用户的开关状态。"""
    svc = _require_settings_service()
    return {"tools": svc.list_available_tools(user_id=user_id)}

# ---- 自定义长期记忆 ----

@router.get("/settings/memories")
async def list_memories(user_id: str = Query(..., min_length=1, description="用户 ID")) -> list[dict[str, Any]]:
    """列出用户的自定义长期记忆。"""
    svc = _require_settings_service()
    return svc.list_memories(user_id=user_id)


@router.post("/settings/memories")
async def add_memory(body: dict[str, Any]) -> dict[str, Any]:
    """添加一条自定义长期记忆。body: user_id, content, importance (可选)。"""
    user_id = body.get("user_id")
    content = body.get("content")
    if not user_id or not content:
        raise HTTPException(status_code=422, detail="user_id and content are required")
    svc = _require_settings_service()
    return svc.add_memory(
        user_id=str(user_id),
        content=str(content),
        importance=float(body.get("importance", 0.5)),
    )


@router.delete("/settings/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """删除指定的自定义长期记忆。"""
    svc = _require_settings_service()
    deleted = svc.remove_memory(memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}
