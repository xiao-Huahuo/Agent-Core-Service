"""用户设置端点。"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent_service.api.rest.deps import _require_agent, _require_knowledge_library_service, _require_settings_service

router = APIRouter()

logger = logging.getLogger(__name__)

# ---- 系统提示词条目 ----

@router.get("/settings/models/status")
async def get_model_status() -> dict[str, Any]:
    """返回 Embedding / ReRank / PaddleOCR 模型加载状态快照。"""

    from agent_service.core.model_status import get_model_status as _get_model_status

    return _get_model_status().to_dict()


@router.post("/settings/models/download")
async def download_model(body: dict[str, Any]) -> dict[str, Any]:
    """异步触发指定模型的后台下载。

    body: { "model": "embedding" | "rerank" | "paddleocr" }
    返回后前端轮询 GET /settings/models/status 获取进度。
    """

    model = str(body.get("model") or "").strip()
    if model not in ("embedding", "rerank", "paddleocr"):
        raise HTTPException(status_code=422, detail="model 必须是 embedding / rerank / paddleocr")

    from agent_service.core.model_status import ModelState, set_model_state

    svc = _require_settings_service()
    config = svc.config

    def _download_embedding() -> None:
        try:
            from agent_service.scripts.download_model import ensure_model, model_target_dir, is_model_available

            model_name = config.model.embedding_model_name
            model_dir = config.storage.embedding_model_dir
            set_model_state("embedding", ModelState.DOWNLOADING)
            ensure_model(model_name, model_dir, model_type="embedding")
            target = model_target_dir(model_name, model_dir)
            if is_model_available(target):
                set_model_state("embedding", ModelState.DOWNLOADED)
                _trigger_embedding_load(config)
            else:
                set_model_state("embedding", ModelState.ERROR)
        except Exception:
            set_model_state("embedding", ModelState.ERROR)

    def _download_rerank() -> None:
        try:
            from agent_service.scripts.download_model import ensure_model, model_target_dir, is_model_available

            model_name = config.model.rerank_model_name
            model_dir = config.storage.rerank_model_dir
            set_model_state("rerank", ModelState.DOWNLOADING)
            ensure_model(model_name, model_dir, model_type="rerank")
            target = model_target_dir(model_name, model_dir)
            if is_model_available(target):
                set_model_state("rerank", ModelState.DOWNLOADED)
                _trigger_rerank_load(config)
            else:
                set_model_state("rerank", ModelState.ERROR)
        except Exception:
            set_model_state("rerank", ModelState.ERROR)

    def _download_paddleocr() -> None:
        try:
            from agent_service.scripts.download_model import ensure_paddleocr_models

            set_model_state("paddleocr", ModelState.DOWNLOADING)
            ensure_paddleocr_models(
                paddleocr_model_dir=config.storage.paddleocr_model_dir,
                language=config.ocr.language,
                text_detection_model_name=config.ocr.text_detection_model_name,
                text_recognition_model_name=config.ocr.text_recognition_model_name,
                device=config.ocr.device,
            )
            set_model_state("paddleocr", ModelState.READY)
        except Exception:
            set_model_state("paddleocr", ModelState.ERROR)

    t = threading.Thread(target={
        "embedding": _download_embedding,
        "rerank": _download_rerank,
        "paddleocr": _download_paddleocr,
    }[model], daemon=True)
    t.start()

    return {"status": "started", "model": model}


def _trigger_embedding_load(config: Any) -> None:
    """触发 Embedding 模型后台加载。"""
    try:
        from agent_service.services.memory.rag.embedding import _get_shared_provider
        provider = _get_shared_provider(config)
        provider.warmup()
        # warmup 后如果模型已就绪，同步状态（防止状态漂移）
        if provider._model is not None:
            from agent_service.core.model_status import ModelState, set_model_state
            set_model_state("embedding", ModelState.READY)
    except Exception:
        pass


def _trigger_rerank_load(config: Any) -> None:
    """触发 ReRank 模型后台加载。"""
    try:
        from agent_service.services.memory.rag.rerank import _get_shared_rerank_provider
        provider = _get_shared_rerank_provider(config)
        provider.warmup()
        if provider._model is not None:
            from agent_service.core.model_status import ModelState, set_model_state
            set_model_state("rerank", ModelState.READY)
    except Exception:
        pass


@router.post("/settings/models/load")
async def load_model(body: dict[str, Any]) -> dict[str, Any]:
    """触发指定模型的后台加载（不下载，只加载到内存）。

    body: { "model": "embedding" | "rerank" }
    """
    model = str(body.get("model") or "").strip()
    if model not in ("embedding", "rerank"):
        raise HTTPException(status_code=422, detail="model 必须是 embedding / rerank")

    from agent_service.core.model_status import ModelState, set_model_state

    svc = _require_settings_service()
    config = svc.config

    if model == "embedding":
        _trigger_embedding_load(config)
    else:
        _trigger_rerank_load(config)

    return {"status": "triggered", "model": model}


@router.get("/settings/models/download-progress")
async def get_download_progress() -> dict[str, float]:
    """返回各模型下载进度百分比。"""

    from agent_service.scripts.download_model import get_all_download_progress

    return get_all_download_progress()


@router.post("/settings/models/check")
async def check_model_disk() -> dict[str, Any]:
    """磁盘级检测模型文件是否存在，同步真实状态。"""

    from agent_service.core.model_status import ModelState, set_model_state, get_model_status
    from agent_service.scripts.download_model import is_model_available, model_target_dir

    svc = _require_settings_service()
    config = svc.config

    models = {"embedding": config.model.embedding_model_name, "rerank": config.model.rerank_model_name}
    dirs = {"embedding": config.storage.embedding_model_dir, "rerank": config.storage.rerank_model_dir}

    for key in ("embedding", "rerank"):
        target = model_target_dir(models[key], dirs[key])
        available = is_model_available(target)
        if available:
            current = get_model_status().to_dict().get(key)
            if current in ("ready", "loading", "downloading"):
                continue
            set_model_state(key, ModelState.DOWNLOADED)
        else:
            set_model_state(key, ModelState.NOT_DOWNLOADED)

    # paddleocr 用 marker 文件检测
    paddleocr_available = False
    from agent_service.scripts.download_model import PADDLEOCR_MARKER_FILE
    marker = Path(config.storage.paddleocr_model_dir) / PADDLEOCR_MARKER_FILE
    if marker.exists():
        paddleocr_available = True
    set_model_state("paddleocr", ModelState.READY if paddleocr_available else ModelState.NOT_DOWNLOADED)

    return get_model_status().to_dict()


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


@router.post("/settings/appearance/font")
@router.put("/settings/appearance/font")
async def save_font_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户 editor 字体家族配置。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    ui_font_families = body.get("ui_font_families")
    text_font_families = body.get("text_font_families")
    font_size_percent = body.get("font_size_percent")
    if ui_font_families is not None and not isinstance(ui_font_families, list):
        raise HTTPException(status_code=422, detail="ui_font_families must be a list")
    if text_font_families is not None and not isinstance(text_font_families, list):
        raise HTTPException(status_code=422, detail="text_font_families must be a list")
    if font_size_percent is not None and not isinstance(font_size_percent, int):
        raise HTTPException(status_code=422, detail="font_size_percent must be an integer")
    svc = _require_settings_service()
    try:
        return svc.save_font_config(
            user_id=user_id,
            ui_font_families=ui_font_families,
            text_font_families=text_font_families,
            font_size_percent=font_size_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/settings/appearance/config")
@router.put("/settings/appearance/config")
async def save_appearance_config(body: dict[str, Any]) -> dict[str, Any]:
    """Persist editor appearance colors for a user."""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    svc = _require_settings_service()
    try:
        return svc.save_appearance_config(
            user_id=user_id,
            theme_primary_color=body.get("theme_primary_color"),
            theme_soft_color=body.get("theme_soft_color"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/settings/editor/paste")
@router.put("/settings/editor/paste")
async def save_editor_paste_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存编辑器粘贴设置。body: user_id 必填,editor_image_assets_dir 可选。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    svc = _require_settings_service()
    try:
        return svc.save_editor_paste_config(
            user_id=user_id,
            editor_image_assets_dir=body.get("editor_image_assets_dir"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/settings/profile/ingestion")
async def get_knowledge_ingestion_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取知识库灌库配置。"""

    svc = _require_settings_service()
    return svc.get_knowledge_ingestion_config(user_id=user_id)


@router.put("/settings/profile/ingestion")
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


@router.post("/settings/floating/config")
@router.put("/settings/floating/config")
async def save_floating_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户悬浮窗启动配置。body: user_id 必填,floating_launch_enabled 可选。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    svc = _require_settings_service()
    try:
        return svc.save_floating_config(
            user_id=user_id,
            floating_launch_enabled=body.get("floating_launch_enabled"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/settings/graph/config")
async def save_graph_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户图谱配置。body: user_id 必填,graph_node_limit 可选。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    svc = _require_settings_service()
    result = svc.save_graph_config(
        user_id=user_id,
        graph_node_limit=body.get("graph_node_limit"),
    )
    return result


@router.get("/settings/memory/system-prompts")
async def list_system_prompt_entries(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出用户的所有系统提示词条目。"""
    svc = _require_settings_service()
    entries = svc.list_system_prompt_entries(user_id=user_id)
    return {"entries": entries}


@router.post("/settings/memory/system-prompts")
async def add_system_prompt_entry(body: dict[str, Any]) -> dict[str, Any]:
    """添加一条系统提示词条目。body: user_id, content。"""
    user_id = body.get("user_id")
    content = body.get("content")
    if not user_id or not content:
        raise HTTPException(status_code=422, detail="user_id and content are required")
    svc = _require_settings_service()
    return svc.add_system_prompt_entry(user_id=str(user_id), content=str(content))


@router.delete("/settings/memory/system-prompts/{prompt_id}")
async def delete_system_prompt_entry(prompt_id: str) -> dict[str, Any]:
    """删除指定的系统提示词条目。"""
    svc = _require_settings_service()
    deleted = svc.delete_system_prompt_entry(prompt_id=prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}


# ---- 用户 LLM 配置 ----

@router.get("/settings/llm/config")
async def get_llm_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户的 LLM 配置（返回明文 API Key）。"""
    svc = _require_settings_service()
    return svc.get_llm_config(user_id=user_id)


@router.put("/settings/llm/config")
async def save_llm_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户的 LLM 配置。body: user_id 必填，其余字段可选。"""
    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    def _unwrap(field: str) -> str | None:
        if field not in body:
            return None
        value = body.get(field)
        if value is None or isinstance(value, bool):
            return None
        s = str(value).strip()
        return s

    svc = _require_settings_service()
    return svc.save_llm_config(
        user_id=user_id,
        api_key=_unwrap("api_key"),
        base_url=_unwrap("base_url"),
        model_name=_unwrap("model_name"),
        small_api_key=_unwrap("small_api_key"),
        small_base_url=_unwrap("small_base_url"),
        small_model_name=_unwrap("small_model_name"),
    )


# ---- 联网搜索配置 ----

@router.get("/settings/llm/config/saved")
async def list_llm_config_presets(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出用户保存的可复用 LLM 配置。"""

    svc = _require_settings_service()
    return {"configs": svc.list_llm_config_presets(user_id=user_id)}


@router.post("/settings/llm/config/saved")
async def save_llm_config_preset(body: dict[str, Any]) -> dict[str, Any]:
    """保存一条可复用的单模型 LLM 配置。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")

    def _unwrap(value: Any) -> str | None:
        if value is None or isinstance(value, bool):
            return None
        s = str(value).strip()
        return s if s else None

    svc = _require_settings_service()
    try:
        return svc.save_llm_config_preset(
            user_id=user_id,
            label=_unwrap(body.get("label")),
            api_key=_unwrap(body.get("api_key")),
            base_url=_unwrap(body.get("base_url")),
            model_name=_unwrap(body.get("model_name")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/settings/llm/config/saved/{config_id}")
async def delete_llm_config_preset(config_id: str) -> dict[str, Any]:
    """删除一条已保存的 LLM 配置。"""

    svc = _require_settings_service()
    deleted = svc.delete_llm_config_preset(config_id=config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"ok": True}


@router.get("/settings/web-search/config")
async def get_web_search_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户的联网搜索配置（代理地址 + 开关状态）。"""
    svc = _require_settings_service()
    return svc.get_web_search_config(user_id=user_id)


@router.put("/settings/web-search/config")
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
    raw_max = body.get("web_search_max_results")
    web_search_max_results: int | None = (
        int(raw_max) if raw_max is not None and not isinstance(raw_max, bool) else None
    )

    svc = _require_settings_service()
    return svc.save_web_search_config(
        user_id=user_id,
        proxy_url=_unwrap(body.get("proxy_url")),
        web_search_enabled=body.get("web_search_enabled"),
        web_search_max_results=web_search_max_results,
    )


# ---- 可开关工具 ----

@router.get("/settings/tools/disabled")
async def get_disabled_tools(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户关闭的工具名称列表。"""
    svc = _require_settings_service()
    return {"disabled_tools": svc.get_disabled_tools(user_id=user_id)}


@router.put("/settings/tools/disabled")
async def save_disabled_tools(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户关闭的工具列表。body: user_id 必填, tool_names 为关闭的工具名称数组。"""
    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    raw_tool_names = body.get("tool_names", [])
    tool_names = [str(name) for name in raw_tool_names if isinstance(name, str) and name.strip()]
    svc = _require_settings_service()
    return {"disabled_tools": svc.save_disabled_tools(user_id=user_id, tool_names=tool_names)}


@router.get("/settings/tools/available")
async def list_available_tools(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出全部内置工具及当前用户的开关状态。"""
    svc = _require_settings_service()
    return svc.list_available_tools(user_id=user_id)


@router.get("/settings/terminal/sandbox")
async def get_terminal_sandbox_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户的 Agent 终端沙盒配置和支持的结构化指令段目录。"""

    svc = _require_settings_service()
    return svc.get_terminal_sandbox_config(user_id=user_id)


@router.put("/settings/terminal/sandbox")
async def save_terminal_sandbox_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户的 Agent 终端沙盒配置。body: user_id 必填,config 为配置对象。"""

    user_id = str(body.get("user_id") or "").strip()
    config_payload = body.get("config")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    if not isinstance(config_payload, dict):
        raise HTTPException(status_code=422, detail="config must be an object")
    svc = _require_settings_service()
    try:
        return svc.save_terminal_sandbox_config(user_id=user_id, config_payload=config_payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

# ---- 长期记忆配置与自定义内容 ----

@router.get("/settings/memory/config")
async def get_memory_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """获取用户的长期记忆总开关。"""
    return _require_settings_service().get_memory_config(user_id=user_id)


@router.put("/settings/memory/config")
async def save_memory_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户的长期记忆总开关。"""
    user_id = str(body.get("user_id") or "").strip()
    if not user_id or not isinstance(body.get("long_term_memory_enabled"), bool):
        raise HTTPException(status_code=422, detail="user_id and long_term_memory_enabled are required")
    return _require_settings_service().save_memory_config(
        user_id=user_id,
        long_term_memory_enabled=body["long_term_memory_enabled"],
    )


# ---- 自定义长期记忆 ----

@router.get("/settings/memory/memories")
async def list_memories(user_id: str = Query(..., min_length=1, description="用户 ID")) -> list[dict[str, Any]]:
    """列出用户的自定义长期记忆。"""
    svc = _require_settings_service()
    return svc.list_memories(user_id=user_id)


@router.post("/settings/memory/memories")
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


@router.delete("/settings/memory/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """删除指定的自定义长期记忆。"""
    svc = _require_settings_service()
    deleted = svc.remove_memory(memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


# ---- 安全配置（敏感词库） ----

_SENSITIVE_WORDS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "resources" / "safety" / "sensitive_words.json"


@router.get("/settings/safety/sensitive-words")
async def get_sensitive_words() -> dict[str, Any]:
    """读取敏感词库 JSON。"""
    try:
        data = json.loads(_SENSITIVE_WORDS_PATH.read_text(encoding="utf-8"))
        return data
    except FileNotFoundError:
        return {"_description": "敏感词库,按类别分组。支持 exact 精确匹配 + regex 正则匹配", "categories": {}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取敏感词库失败: {exc}") from exc


@router.post("/settings/safety/sensitive-words")
async def save_sensitive_words(body: dict[str, Any]) -> dict[str, Any]:
    """保存敏感词库 JSON,并触发 SafetyService 热重载。"""
    try:
        _SENSITIVE_WORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SENSITIVE_WORDS_PATH.write_text(
            json.dumps(body, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            _require_agent().safety_service.reload_sensitive_words()
        except Exception:
            logger.warning("敏感词库已保存,但 SafetyService 热重载失败", exc_info=True)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存敏感词库失败: {exc}") from exc


# ---- 存储管理 ----

@router.get("/settings/storage/config")
async def get_storage_config(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """返回所有存储路径的当前值、大小和元数据。"""

    svc = _require_settings_service()
    from agent_service.services.storage_service import StorageService
    storage_svc = StorageService(config=svc.config, settings_service=svc)
    return storage_svc.get_storage_config(user_id=user_id)


@router.put("/settings/storage/config")
async def save_storage_config(body: dict[str, Any]) -> dict[str, Any]:
    """保存用户存储路径覆盖（knowledge_dir 除外）。"""

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    paths = body.get("paths", {})
    if not isinstance(paths, dict):
        raise HTTPException(status_code=422, detail="paths must be a dict")
    svc = _require_settings_service()
    from agent_service.services.storage_service import StorageService
    storage_svc = StorageService(config=svc.config, settings_service=svc)
    try:
        return storage_svc.save_storage_config(user_id=user_id, paths=paths)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/settings/storage/clear")
async def clear_storage_path(body: dict[str, Any]) -> dict[str, Any]:
    """清空指定存储路径的内容，保留目录本身。"""

    path_key = str(body.get("path_key") or "").strip()
    if not path_key:
        raise HTTPException(status_code=422, detail="path_key is required")
    svc = _require_settings_service()
    from agent_service.services.storage_service import StorageService
    storage_svc = StorageService(config=svc.config, settings_service=svc)
    try:
        return storage_svc.clear_path(path_key=path_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
