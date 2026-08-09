"""
服务入口。

本文件启动 FastAPI + gRPC 双协议微服务:
- FastAPI (HTTP): 健康检查、测试调用。
- gRPC (50051): AgentCore 全量方法和 Session 管理。

启动方式:
    uvicorn main:app --host 0.0.0.0 --port 8002

环境变量:
    AGENT_MODEL_NAME / AGENT_MODEL_API_KEY / AGENT_MODEL_BASE_URL: 主模型配置。
    可选: AGENT_DATABASE_URL、AGENT_REDIS_URL 等,详见 AgentConfig。
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

import grpc
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

warnings.filterwarnings("ignore", message=".*allowed_objects.*")

# Patch langchain_openai to preserve reasoning_content for DeepSeek thinking mode.
# ChatOpenAI explicitly drops this field per its OpenAI-spec-only policy; DeepSeek
# requires it back on every subsequent assistant message in the same conversation.
import langchain_openai.chat_models.base as _lc_openai_base

# 1) Response parsing: capture reasoning_content from API response into additional_kwargs
_original_convert_dict = _lc_openai_base._convert_dict_to_message
_original_convert_delta = _lc_openai_base._convert_delta_to_message_chunk


def _patched_convert_dict_to_message(_dict: dict, **kwargs: Any) -> Any:
    message = _original_convert_dict(_dict, **kwargs)
    reasoning = _dict.get("reasoning_content")
    if reasoning:
        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
        additional_kwargs["reasoning_content"] = reasoning
        message.additional_kwargs = additional_kwargs
    return message


def _patched_convert_delta_to_message_chunk(_dict: dict, default_class: Any) -> Any:
    chunk = _original_convert_delta(_dict, default_class)
    reasoning = _dict.get("reasoning_content")
    if reasoning:
        additional_kwargs = getattr(chunk, "additional_kwargs", None) or {}
        additional_kwargs["reasoning_content"] = reasoning
        chunk.additional_kwargs = additional_kwargs
    return chunk


_lc_openai_base._convert_dict_to_message = _patched_convert_dict_to_message
_lc_openai_base._convert_delta_to_message_chunk = _patched_convert_delta_to_message_chunk

# 2) Request formatting: include reasoning_content from additional_kwargs in API payload
_original_convert_message = _lc_openai_base._convert_message_to_dict


def _patched_convert_message_to_dict(message: Any, api: Any = "chat/completions") -> dict[str, Any]:
    result = _original_convert_message(message, api=api)
    additional_kwargs = getattr(message, "additional_kwargs", None) or {}
    reasoning = additional_kwargs.get("reasoning_content")
    if reasoning:
        result["reasoning_content"] = reasoning
    return result


_lc_openai_base._convert_message_to_dict = _patched_convert_message_to_dict

from agent_service.agent_core import AgentCore
from agent_service.api.grpc.agent_service_pb2_grpc import add_AgentServiceServicer_to_server
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.api.rest import router as rest_router
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.settings_service import SettingsService
from agent_service.services.knowledge_library_service import KnowledgeLibraryService
from agent_service.services.git_service import GitService
from agent_service.services.knowledge_graph_service import KnowledgeGraphService
from agent_service.services.library_service import LibraryService
import agent_service.api.rest.deps as rest_deps
from agent_service.core.agent_config import AgentConfig
from agent_service.services.session_service import SessionService
from agent_service.services.message_service import MessageService
from agent_service.services.session_attachment_service import SessionAttachmentService
from agent_service.services.skill_service import SkillService
from agent_service.services.task_list_service import TaskListService
from agent_service.services.logging_service import setup_logging
from agent_service.services.favorite_service import FavoriteService
from agent_service.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)

_grpc_server: grpc.Server | None = None
_grpc_servicer: AgentServiceServicer | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> Any:  # noqa: ARG001
    """管理 gRPC server 和 AgentCore 的启动与优雅关闭。"""

    global _grpc_server, _grpc_servicer

    config = AgentConfig.load_config(ensure_models=False)
    setup_logging(config)

    # 首次启动自动生成 .env 模板
    env_path = config.storage.project_root / ".env"
    if not env_path.exists():
        env_path.write_text(
            "# AgentService 环境配置\n"
            "# AGENT_MODEL_API_KEY=sk-xxxxxxxx\n"
            "# AGENT_SMALL_MODEL_API_KEY=sk-yyyyyyyy\n",
            encoding="utf-8",
        )
        logger.info(".env 模板已创建 | path=%s", env_path)

    logger.info("AgentService 启动中...")
    logger.info("配置加载完成 | app=%s model=%s", config.constants.app_name, config.model.model_name)

    # 提前创建 MessageService,以便 AgentCore 在初始化阶段预加载 Embedding/ReRank 模型
    message_service = MessageService(config=config)

    session_service = SessionService(config=config)
    task_list_service = TaskListService(session_service=session_service)
    agent = AgentCore(
        config=config,
        message_service=message_service,
        session_service=session_service,
        task_list_service=task_list_service,
    )
    logger.info("AgentCore 初始化完成 | graph_diagram=%s", agent.graph_diagram_path)

    memory_service = LongTermMemoryService(config=config)
    settings_service = SettingsService(config=config, memory_service=memory_service)
    skill_service = SkillService(config=config, settings_service=settings_service)
    agent.skill_service = skill_service

    # 启动时迁移：将用户覆盖的旧路径内容移动到新路径
    from agent_service.services.storage_service import migrate_storage_paths
    config = migrate_storage_paths(config, settings_service)
    attachment_service = SessionAttachmentService(config=config, settings_service=settings_service)
    agent.attachment_service = attachment_service
    if agent.context_builder is not None:
        agent.context_builder.attachment_service = attachment_service
    knowledge_graph_service = KnowledgeGraphService(config=config)
    knowledge_library_service = KnowledgeLibraryService(
        config=config,
        memory_service=memory_service,
        settings_service=settings_service,
        knowledge_graph_service=knowledge_graph_service,
    )
    git_service = GitService(knowledge_library_service=knowledge_library_service)
    library_service = LibraryService(
        config=config,
        settings_service=settings_service,
        knowledge_library_service=knowledge_library_service,
        knowledge_graph_service=knowledge_graph_service,
    )
    favorite_service = FavoriteService(engine=settings_service.engine)
    feedback_service = FeedbackService(engine=settings_service.engine)
    from agent_service.services.smart_form_service import SmartFormService
    smart_form_service = SmartFormService(engine=settings_service.engine)
    rest_deps._settings_service = settings_service
    rest_deps._attachment_service = attachment_service
    rest_deps._skill_service = skill_service
    rest_deps._knowledge_library_service = knowledge_library_service
    rest_deps._knowledge_graph_service = knowledge_graph_service
    rest_deps._git_service = git_service
    rest_deps._library_service = library_service
    rest_deps._favorite_service = favorite_service
    rest_deps._feedback_service = feedback_service
    rest_deps._smart_form_service = smart_form_service
    rest_deps._task_list_service = task_list_service
    retrieval_service = MemoryRetrievalService(config=config, memory_service=memory_service)
    rest_deps._retrieval_service = retrieval_service
    from agent_service.services.todo_service import TodoService
    from agent_service.services.automation_service import AutomationService
    from agent_service.services.automation_scheduler import AutomationScheduler
    rest_deps._todo_service = TodoService(
        engine=memory_service.engine,
        legacy_data_dir=str(config.storage.base_data_dir),
    )
    rest_deps._automation_service = AutomationService(
        engine=memory_service.engine,
        todo_service=rest_deps._todo_service,
    )
    automation_scheduler = AutomationScheduler(
        automation_service=rest_deps._automation_service,
        agent=agent,
        session_service=session_service,
    )
    automation_scheduler.start()
    logger.info("SettingsService 初始化完成")

    # 启动不执行任何自动灌库。知识库由前端 /knowledge/rebuild、单文件灌库与
    # 上传灌库按需触发,避免启动阶段占用 embedding/rerank 与磁盘资源。

    # 启动时自动加载已有 Embedding / ReRank 模型
    try:
        from agent_service.core.model_status import ModelState, set_model_state
        from agent_service.scripts.download_model import is_model_available, model_target_dir
        from agent_service.api.rest.settings import _trigger_embedding_load, _trigger_rerank_load

        for model_key, model_name, model_dir, trigger_fn in [
            ("embedding", config.model.embedding_model_name, config.storage.embedding_model_dir, _trigger_embedding_load),
            ("rerank", config.model.rerank_model_name, config.storage.rerank_model_dir, _trigger_rerank_load),
        ]:
            if not model_name or not str(model_dir):
                continue
            target = model_target_dir(model_name, model_dir)
            if is_model_available(target):
                set_model_state(model_key, ModelState.DOWNLOADED)
                logger.info("已检测到 %s 模型文件，触发后台加载", model_key)
                trigger_fn(config)
    except Exception:
        logger.exception("模型自动加载失败，服务继续运行")

    _grpc_servicer = AgentServiceServicer(
        agent=agent,
        session_service=session_service,
        message_service=message_service,
        settings_service=settings_service,
        knowledge_library_service=knowledge_library_service,
        git_service=git_service,
        favorite_service=favorite_service,
        feedback_service=feedback_service,
    )
    rest_deps._agent = agent
    rest_deps._session_service = session_service
    rest_deps._message_service = message_service

    grpc_host = config.server.grpc_host
    if grpc_host == "[::]" and sys.platform == "win32":
        grpc_host = "0.0.0.0"  # Windows does not support IPv6 wildcard
    grpc_address = f"{grpc_host}:{config.server.grpc_port}"
    try:
        _grpc_server = grpc.server(ThreadPoolExecutor(max_workers=10))
        add_AgentServiceServicer_to_server(_grpc_servicer, _grpc_server)
        _grpc_server.add_insecure_port(grpc_address)
        _grpc_server.start()
        rest_deps._grpc_running = True
        logger.info("gRPC server 已启动 | address=%s", grpc_address)
    except RuntimeError as exc:
        logger.warning("gRPC server 启动失败，HTTP 服务继续运行 | address=%s error=%s", grpc_address, exc)
        _grpc_server = None
        rest_deps._grpc_running = False

    # 前端端口: 打包模式下后端托管静态文件(8002), 开发模式下 editor Vite dev server(5173)
    if _static_dir is not None:
        logger.info("前端静态文件已挂载 | path=%s", _static_dir)
    else:
        logger.info("未找到前端静态文件,开发时请单独启动 editor Vite dev server (npm run dev:electron --prefix editor)")

    try:
        yield
    finally:
        logger.info("AgentService 正在关闭...")
        if automation_scheduler is not None:
            automation_scheduler.shutdown()
        if _grpc_server is not None:
            _grpc_server.stop(0)
            rest_deps._grpc_running = False
            logger.info("gRPC server 已停止")
        if _grpc_servicer is not None:
            _grpc_servicer.shutdown()
            logger.info("AgentCore 资源已释放")
        rest_deps._agent = None
        rest_deps._session_service = None
        rest_deps._message_service = None
        rest_deps._settings_service = None
        rest_deps._attachment_service = None
        rest_deps._skill_service = None
        rest_deps._knowledge_library_service = None
        rest_deps._knowledge_graph_service = None
        rest_deps._git_service = None
        rest_deps._library_service = None
        rest_deps._favorite_service = None
        rest_deps._feedback_service = None
        rest_deps._smart_form_service = None
        rest_deps._todo_service = None
        rest_deps._automation_service = None
        logger.info("AgentService 已关闭")


app = FastAPI(title="Agent-Core-Service", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_origin_regex=r"^(https?://(127\.0\.0\.1|localhost)(:\d+)?|null)$",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)


@app.middleware("http")
async def _allow_local_private_network_requests(request: Any, call_next: Any) -> Any:
    """允许 Electron/file renderer 访问本机后端的 Private Network 预检。"""

    response = await call_next(request)
    origin = request.headers.get("origin", "")
    if origin == "null" or origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


app.include_router(rest_router)

_runtime_config = AgentConfig.load_config(ensure_directories=False, ensure_models=False)
_knowledge_assets_dir = _runtime_config.storage.assets_dir / "knowledge"
_knowledge_assets_dir.mkdir(parents=True, exist_ok=True)

_downloads_dir = _runtime_config.storage.assets_dir / "downloads"
_downloads_dir.mkdir(parents=True, exist_ok=True)

_library_assets_dir = _runtime_config.storage.assets_dir / "library"
_library_assets_dir.mkdir(parents=True, exist_ok=True)

_visualizations_dir = _runtime_config.storage.base_data_dir / "visualizations"
_visualizations_dir.mkdir(parents=True, exist_ok=True)

from fastapi.staticfiles import StaticFiles

app.mount(
    "/knowledge/assets",
    StaticFiles(directory=str(_knowledge_assets_dir)),
    name="knowledge_assets",
)

app.mount(
    "/downloads",
    StaticFiles(directory=str(_downloads_dir)),
    name="downloads",
)

app.mount(
    "/library/assets",
    StaticFiles(directory=str(_library_assets_dir)),
    name="library_assets",
)

app.mount(
    "/visualizations",
    StaticFiles(directory=str(_visualizations_dir)),
    name="visualizations",
)


def _resolve_static_dir() -> Path | None:
    """定位前端静态资源目录。

    优先级:
    1. PyInstaller 打包环境: _MEIPASS/editor/dist
    2. 开发环境: 项目根目录/editor/dist
    如果目录不存在则返回 None,跳过静态文件挂载。
    """
    if getattr(sys, "frozen", False):
        candidate = Path(sys._MEIPASS) / "editor" / "dist"
        # 尝试修正: datas 有时展平到 _MEIPASS 根目录
        if not candidate.is_dir():
            alt = Path(sys._MEIPASS) / "dist"
            if alt.is_dir():
                candidate = alt
    else:
        candidate = Path(__file__).resolve().parent / "editor" / "dist"
    return candidate if candidate.is_dir() else None


_static_dir = _resolve_static_dir()

if _static_dir is not None:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/favicon.ico", include_in_schema=False)
    async def _favicon() -> FileResponse:
        return FileResponse(_static_dir / "favicon.ico")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        """SPA 兜底: 非 API 路径返回 index.html,由 Vue Router 接管。"""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")

if __name__ == "__main__":
    import uvicorn

    temp_config = AgentConfig.load_config(ensure_models=False)
    uvicorn.run(app, host=temp_config.server.http_host, port=temp_config.server.http_port, timeout_keep_alive=temp_config.server.uvicorn_timeout_keep_alive)
