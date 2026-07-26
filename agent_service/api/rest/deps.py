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
from agent_service.services.library_service import LibraryService
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.session_attachment_service import SessionAttachmentService
from agent_service.services.task_list_service import TaskListService
from agent_service.services.todo_service import TodoService

_agent: AgentCore | None = None
_session_service: SessionService | None = None
_message_service: MessageService | None = None
_settings_service: SettingsService | None = None
_knowledge_library_service: KnowledgeLibraryService | None = None
_knowledge_graph_service: KnowledgeGraphService | None = None
_library_service: LibraryService | None = None
_retrieval_service: MemoryRetrievalService | None = None
_attachment_service: SessionAttachmentService | None = None
_task_list_service: TaskListService | None = None
_grpc_running = False
_todo_service: TodoService | None = None


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


def _require_library_service() -> LibraryService:
    if _library_service is None:
        raise HTTPException(status_code=503, detail="LibraryService not initialized yet")
    return _library_service


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


def _require_task_list_service() -> TaskListService:
    if _task_list_service is None:
        raise HTTPException(status_code=503, detail="TaskListService not initialized yet")
    return _task_list_service
