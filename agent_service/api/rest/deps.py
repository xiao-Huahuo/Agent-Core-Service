"""
REST 路由共享依赖。

由 main.py 在 lifespan 启动后注入 AgentCore / SessionService / MessageService,
各子路由模块通过 _require_* 助手按需获取,未注入时抛出 503。
"""

from __future__ import annotations

from fastapi import HTTPException

from agent_service.agent_core.agent_core import AgentCore
from agent_service.services.message_service import MessageService
from agent_service.services.session_service import SessionService
from agent_service.services.settings_service import SettingsService
from agent_service.services.knowledge_library_service import KnowledgeLibraryService
from agent_service.services.knowledge_graph_service import KnowledgeGraphService
from agent_service.services.git_service import GitService
from agent_service.services.library_service import LibraryService
from agent_service.services.vault_service import VaultService
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.session_attachment_service import SessionAttachmentService
from agent_service.services.skill_service import SkillService
from agent_service.services.task_list_service import TaskListService
from agent_service.services.todo_service import TodoService
from agent_service.services.automation_service import AutomationService
from agent_service.services.favorite_service import FavoriteService
from agent_service.services.feedback_service import FeedbackService
from agent_service.services.smart_form_service import SmartFormService
from agent_service.services.structured_generation_service import StructuredGenerationService
from agent_service.services.agent_change_service import AgentChangeService
from agent_service.services.agent_queue_service import AgentQueueService
from agent_service.services.activity_service import ActivityService

_agent: AgentCore | None = None
_session_service: SessionService | None = None
_message_service: MessageService | None = None
_settings_service: SettingsService | None = None
_knowledge_library_service: KnowledgeLibraryService | None = None
_knowledge_graph_service: KnowledgeGraphService | None = None
_git_service: GitService | None = None
_library_service: LibraryService | None = None
_vault_service: VaultService | None = None
_retrieval_service: MemoryRetrievalService | None = None
_attachment_service: SessionAttachmentService | None = None
_skill_service: SkillService | None = None
_task_list_service: TaskListService | None = None
_grpc_running = False
_todo_service: TodoService | None = None
_automation_service: AutomationService | None = None
_favorite_service: FavoriteService | None = None
_feedback_service: FeedbackService | None = None
_smart_form_service: SmartFormService | None = None
_structured_generation_service: StructuredGenerationService | None = None
_agent_change_service: AgentChangeService | None = None
_agent_queue_service: AgentQueueService | None = None
_activity_service: ActivityService | None = None


def _require_agent() -> AgentCore:
    if _agent is None:
        raise HTTPException(status_code=503, detail="AgentCore not initialized yet")
    return _agent


def _require_session_service() -> SessionService:
    if _session_service is None:
        raise HTTPException(status_code=503, detail="SessionService not initialized yet")
    return _session_service


def _require_message_service() -> MessageService:
    if _message_service is None:
        raise HTTPException(status_code=503, detail="MessageService not initialized yet")
    return _message_service


def _require_settings_service() -> SettingsService:
    if _settings_service is None:
        raise HTTPException(status_code=503, detail="SettingsService not initialized yet")
    return _settings_service


def _require_knowledge_library_service() -> KnowledgeLibraryService:
    if _knowledge_library_service is None:
        raise HTTPException(status_code=503, detail="KnowledgeLibraryService not initialized yet")
    return _knowledge_library_service


def _require_knowledge_graph_service() -> KnowledgeGraphService:
    if _knowledge_graph_service is None:
        raise HTTPException(status_code=503, detail="KnowledgeGraphService not initialized yet")
    return _knowledge_graph_service


def _require_git_service() -> GitService:
    """返回启动阶段注入的知识库 Git 服务。"""

    if _git_service is None:
        raise HTTPException(status_code=503, detail="GitService not initialized yet")
    return _git_service


def _require_library_service() -> LibraryService:
    if _library_service is None:
        raise HTTPException(status_code=503, detail="LibraryService not initialized yet")
    return _library_service


def _require_vault_service() -> VaultService:
    """返回启动阶段注入的密码库服务。"""

    if _vault_service is None:
        raise HTTPException(status_code=503, detail="VaultService not initialized yet")
    return _vault_service


def _require_retrieval_service() -> MemoryRetrievalService:
    if _retrieval_service is None:
        raise HTTPException(status_code=503, detail="MemoryRetrievalService not initialized yet")
    return _retrieval_service


def _require_attachment_service() -> SessionAttachmentService:
    if _attachment_service is None:
        raise HTTPException(status_code=503, detail="SessionAttachmentService not initialized yet")
    return _attachment_service


def _require_todo_service() -> TodoService:
    if _todo_service is None:
        raise HTTPException(status_code=503, detail="TodoService not initialized yet")
    return _todo_service


def _require_automation_service() -> AutomationService:
    """返回启动阶段注入的自动化任务服务。"""

    if _automation_service is None:
        raise HTTPException(status_code=503, detail="AutomationService not initialized yet")
    return _automation_service


def _require_task_list_service() -> TaskListService:
    if _task_list_service is None:
        raise HTTPException(status_code=503, detail="TaskListService not initialized yet")
    return _task_list_service


def _require_skill_service() -> SkillService:
    if _skill_service is None:
        raise HTTPException(status_code=503, detail="SkillService not initialized yet")
    return _skill_service


def _require_favorite_service() -> FavoriteService:
    """返回启动阶段注入的用户收藏服务。"""

    if _favorite_service is None:
        raise HTTPException(status_code=503, detail="FavoriteService not initialized yet")
    return _favorite_service


def _require_feedback_service() -> FeedbackService:
    """返回启动阶段注入的用户反馈服务。"""

    if _feedback_service is None:
        raise HTTPException(status_code=503, detail="FeedbackService not initialized yet")
    return _feedback_service


def _require_smart_form_service() -> SmartFormService:
    """返回启动阶段注入的智能表格服务。"""

    if _smart_form_service is None:
        raise HTTPException(status_code=503, detail="SmartFormService not initialized yet")
    return _smart_form_service


def _require_structured_generation_service() -> StructuredGenerationService:
    """返回启动阶段注入的通用结构化字段生成服务。"""

    if _structured_generation_service is None:
        raise HTTPException(status_code=503, detail="StructuredGenerationService not initialized yet")
    return _structured_generation_service


def _require_agent_change_service() -> AgentChangeService:
    """Return the persistent Agent change service injected at application startup."""

    if _agent_change_service is None:
        raise HTTPException(status_code=503, detail="AgentChangeService not initialized yet")
    return _agent_change_service


def _require_agent_queue_service() -> AgentQueueService:
    """Return the persistent Agent task queue service injected at startup."""

    if _agent_queue_service is None:
        raise HTTPException(status_code=503, detail="AgentQueueService not initialized yet")
    return _agent_queue_service


def _require_activity_service() -> ActivityService:
    """Return the persistent daily activity service injected at startup."""

    if _activity_service is None:
        raise HTTPException(status_code=503, detail="ActivityService not initialized yet")
    return _activity_service
