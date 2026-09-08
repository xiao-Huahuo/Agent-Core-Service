"""REST 路由共享的应用服务依赖。

FastAPI 在每个请求开始时通过 ``bind_application_services`` 从
``request.app.state.services`` 获取 ``ApplicationServices``，并绑定到请求级
``ContextVar``。现有路由继续调用 ``_require_*``，但不再依赖模块级 Service 实例。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import AsyncIterator, TypeVar, cast

from fastapi import HTTPException, Request

from agent_service.agent_core.agent_core import AgentCore
from agent_service.core.bootstrap.services_bootstrap import ApplicationServices
from agent_service.services.activity.service import ActivityService
from agent_service.services.agent_change.service import AgentChangeService
from agent_service.services.agent_queue.service import AgentQueueService
from agent_service.services.automation.service import AutomationService
from agent_service.services.component_library.service import ComponentLibraryService
from agent_service.services.dsh_runtime import DshRuntimePackageManager
from agent_service.services.dsh_adapter import DshChildAgentExecutor
from agent_service.services.favorite.service import FavoriteService
from agent_service.services.feedback.service import FeedbackService
from agent_service.services.git.service import GitService
from agent_service.services.knowledge_graph import KnowledgeGraphQueueService, KnowledgeGraphService
from agent_service.services.knowledge_ingestion_job.service import KnowledgeIngestionJobService
from agent_service.services.knowledge_library import KnowledgeLibraryService
from agent_service.services.latex.service import LatexService
from agent_service.services.library.service import LibraryService
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.message.service import MessageService
from agent_service.services.model_management.service import ModelManagementService
from agent_service.services.privacy.service import PrivacyService
from agent_service.services.scanner import ScannerService
from agent_service.services.session_attachment.service import SessionAttachmentService
from agent_service.services.session.service import SessionService
from agent_service.services.settings.service import SettingsService
from agent_service.services.skill.service import SkillService
from agent_service.services.smart_form.service import SmartFormService
from agent_service.services.structured_generation.service import StructuredGenerationService
from agent_service.services.task_list.service import TaskListService
from agent_service.services.todo.service import TodoService
from agent_service.services.unified_search import UnifiedSearchService
from agent_service.services.vault.service import VaultService

ServiceT = TypeVar("ServiceT")
_current_services: ContextVar[ApplicationServices | None] = ContextVar(
    "agent_service_rest_services",
    default=None,
)


def get_application_services(request: Request) -> ApplicationServices:
    """从当前 FastAPI app 获取已初始化的应用服务容器。"""

    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Application services not initialized yet")
    return cast(ApplicationServices, services)


async def bind_application_services(request: Request) -> AsyncIterator[ApplicationServices]:
    """在一个请求的完整生命周期内绑定应用服务容器。"""

    services = get_application_services(request)
    token = _current_services.set(services)
    try:
        yield services
    finally:
        _current_services.reset(token)


def _require(attribute: str, label: str) -> ServiceT:
    """从当前请求容器取得一个具名 Service，未绑定时返回 503。"""

    services = _current_services.get()
    if services is None:
        raise HTTPException(status_code=503, detail="Application services not bound to request")
    service = getattr(services, attribute, None)
    if service is None:
        raise HTTPException(status_code=503, detail=f"{label} not initialized yet")
    return cast(ServiceT, service)


def _require_agent() -> AgentCore:
    """返回当前请求的 AgentCore。"""

    return _require("agent", "AgentCore")


def _require_session_service() -> SessionService:
    """返回当前请求的 SessionService。"""

    return _require("session_service", "SessionService")


def _require_message_service() -> MessageService:
    """返回当前请求的 MessageService。"""

    return _require("message_service", "MessageService")


def _require_settings_service() -> SettingsService:
    """返回当前请求的 SettingsService。"""

    return _require("settings_service", "SettingsService")


def _require_knowledge_library_service() -> KnowledgeLibraryService:
    """返回当前请求的 KnowledgeLibraryService。"""

    return _require("knowledge_library_service", "KnowledgeLibraryService")


def _require_knowledge_graph_service() -> KnowledgeGraphService:
    """返回当前请求的 KnowledgeGraphService。"""

    return _require("knowledge_graph_service", "KnowledgeGraphService")


def _require_knowledge_graph_queue_service() -> KnowledgeGraphQueueService:
    """返回当前请求的 KnowledgeGraphQueueService。"""

    return _require("knowledge_graph_queue_service", "KnowledgeGraphQueueService")


def _require_git_service() -> GitService:
    """返回当前请求的 GitService。"""

    return _require("git_service", "GitService")


def _require_library_service() -> LibraryService:
    """返回当前请求的 LibraryService。"""

    return _require("library_service", "LibraryService")


def _require_component_library_service() -> ComponentLibraryService:
    """返回当前请求的 ComponentLibraryService。"""

    return _require("component_library_service", "ComponentLibraryService")


def _require_unified_search_service() -> UnifiedSearchService:
    """返回当前请求的 UnifiedSearchService。"""

    return _require("unified_search_service", "UnifiedSearchService")


def _require_vault_service() -> VaultService:
    """返回当前请求的 VaultService。"""

    return _require("vault_service", "VaultService")


def _require_retrieval_service() -> MemoryRetrievalService:
    """返回当前请求的 MemoryRetrievalService。"""

    return _require("retrieval_service", "MemoryRetrievalService")


def _require_attachment_service() -> SessionAttachmentService:
    """返回当前请求的 SessionAttachmentService。"""

    return _require("attachment_service", "SessionAttachmentService")


def _require_todo_service() -> TodoService:
    """返回当前请求的 TodoService。"""

    return _require("todo_service", "TodoService")


def _require_automation_service() -> AutomationService:
    """返回当前请求的 AutomationService。"""

    return _require("automation_service", "AutomationService")


def _require_task_list_service() -> TaskListService:
    """返回当前请求的 TaskListService。"""

    return _require("task_list_service", "TaskListService")


def _require_skill_service() -> SkillService:
    """返回当前请求的 SkillService。"""

    return _require("skill_service", "SkillService")


def _require_favorite_service() -> FavoriteService:
    """返回当前请求的 FavoriteService。"""

    return _require("favorite_service", "FavoriteService")


def _require_scanner_service() -> ScannerService:
    """返回当前请求的 ScannerService。"""

    return _require("scanner_service", "ScannerService")


def _require_privacy_service() -> PrivacyService:
    """返回当前请求的 PrivacyService。"""

    return _require("privacy_service", "PrivacyService")


def _require_feedback_service() -> FeedbackService:
    """返回当前请求的 FeedbackService。"""

    return _require("feedback_service", "FeedbackService")


def _require_smart_form_service() -> SmartFormService:
    """返回当前请求的 SmartFormService。"""

    return _require("smart_form_service", "SmartFormService")


def _require_structured_generation_service() -> StructuredGenerationService:
    """返回当前请求的 StructuredGenerationService。"""

    return _require("structured_generation_service", "StructuredGenerationService")


def _require_agent_change_service() -> AgentChangeService:
    """返回当前请求的 AgentChangeService。"""

    return _require("agent_change_service", "AgentChangeService")


def _require_agent_queue_service() -> AgentQueueService:
    """返回当前请求的 AgentQueueService。"""

    return _require("agent_queue_service", "AgentQueueService")


def _require_activity_service() -> ActivityService:
    """返回当前请求的 ActivityService。"""

    return _require("activity_service", "ActivityService")


def _require_knowledge_ingestion_job_service() -> KnowledgeIngestionJobService:
    """返回当前请求的 KnowledgeIngestionJobService。"""

    return _require("knowledge_ingestion_job_service", "KnowledgeIngestionJobService")


def _require_latex_service() -> LatexService:
    """返回当前请求的 LatexService。"""

    return _require("latex_service", "LatexService")


def _require_model_management_service() -> ModelManagementService:
    """返回当前请求的 ModelManagementService。"""

    return _require("model_management_service", "ModelManagementService")


def _require_dsh_runtime_manager() -> DshRuntimePackageManager:
    """返回当前应用拥有的 DSH Runtime受管资源服务。"""

    return _require("dsh_runtime_manager", "DshRuntimePackageManager")


def _require_dsh_executor() -> DshChildAgentExecutor:
    """返回当前应用拥有的 DSH Child Agent执行器。"""

    return _require("dsh_executor", "DshChildAgentExecutor")
