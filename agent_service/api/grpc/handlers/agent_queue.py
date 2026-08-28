"""agent_queue 领域 gRPC RPC handlers。

方法体由主 servicer 机械迁移，协议行为不变。
"""

from __future__ import annotations
import logging
import json
from datetime import datetime, timezone
from typing import Any
from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from pydantic import ValidationError
from agent_service.agent_core.agent_core import AgentCore
from agent_service.api.recall_details import build_recall_details_payload
from agent_service.schemas.automation import (
    AutomationCreateRequest,
    AutomationDeleteRequest,
    AutomationToggleRequest,
)
from agent_service.api.grpc.agent_service_pb2 import (
    CancelRequest,
    CancelResponse,
    ChildAgentControlRequest,
    ChildAgentControlResponse,
    ChildAgentListRequest,
    ChildAgentListResponse,
    ChildAgentRecord,
    ChildAgentUpdateRequest,
    ChunkMessage,
    DeleteAllSessionsRequest,
    DeleteResponse,
    EventEntry,
    EventsRequest,
    EventsResponse,
    FavoriteCreateRequest,
    FavoriteDeleteRequest,
    FavoriteEntryResponse,
    FavoriteListRequest,
    FavoriteListResponse,
    PrivacyCreateRequest,
    PrivacyDeleteRequest,
    PrivacyEntryResponse,
    PrivacyListRequest,
    PrivacyListResponse,
    FeedbackCreateRequest,
    FeedbackDeleteRequest,
    FeedbackEntryResponse,
    FeedbackListRequest,
    FeedbackListResponse,
    FeedbackUpdateRequest,
    GitBranchRequest,
    GitCommitRequest,
    GitDiffRequest,
    GitHistoryRequest,
    GitInitRequest,
    GitPathsRequest,
    GitPullRequest,
    GitPushRequest,
    GitRemoteRequest,
    GitUserRequest,
    KnowledgeFileContentRequest,
    KnowledgeFileContentResponse,
    KnowledgeFileCreateRequest,
    KnowledgeFileNode,
    KnowledgeFileTreeRequest,
    KnowledgeFileTreeResponse,
    KnowledgeFileUploadRequest,
    KnowledgeFileWriteRequest,
    KnowledgeFolderCreateRequest,
    KnowledgeLibraryEntry,
    KnowledgePathCopyRequest,
    KnowledgePathDeleteRequest,
    KnowledgePathRenameRequest,
    KnowledgePdfPageRequest,
    KnowledgePdfPageResponse,
    KnowledgeRebuildRequest,
    KnowledgeRebuildResponse,
    LLMConfigPresetDeleteRequest,
    LLMConfigPresetListResponse,
    LLMConfigPresetResponse,
    LLMConfigPresetSaveRequest,
    LLMConfigRequest,
    LLMConfigResponse,
    LLMConfigSaveRequest,
    MemoryAddRequest,
    MemoryDeleteRequest,
    MemoryEntryResponse,
    MemoryListRequest,
    MemoryListResponse,
    RecallDetailsRequest,
    RecallDetailsResponse,
    ListMessagesRequest,
    ListMessagesResponse,
    ListSessionsRequest,
    ListSessionsResponse,
    MessageEntry,
    RunRequest,
    RunResult,
    SessionCreateRequest,
    SessionIdRequest,
    SessionResponse,
    SessionUpdateRequest,
    SystemPromptAddRequest,
    SystemPromptDeleteRequest,
    SystemPromptEntriesResponse,
    SystemPromptEntryResponse,
    SystemPromptRequest,
    TaskSuggestionsRequest,
    TaskSuggestionsResponse,
    TokenUsageRequest,
    ActivityHeatmapRequest,
    ToolInfo,
    ToolListRequest,
    ToolListResponse,
    ToolCall,
    TraceEntry,
    UserKnowledgeDirUpdateRequest,
    UserProfileRequest,
    UserProfileResponse,
)
from agent_service.api.grpc.agent_service_pb2_grpc import AgentServiceServicer as BaseServicer
from agent_service.schemas.session import SessionCreate, SessionUpdate
from agent_service.schemas.favorite import FavoriteCreate
from agent_service.schemas.privacy import PrivacyCreate
from agent_service.schemas.feedback import FeedbackCreate, FeedbackUpdate
from agent_service.services.message.service import MessageService
from agent_service.services.session.service import SessionService
from agent_service.services.settings.service import SettingsService
from agent_service.services.knowledge_library import KnowledgeLibraryService, KnowledgeLibraryRebuildResult
from agent_service.services.knowledge_ingestion_job.service import KnowledgeIngestionJobService
from agent_service.services.git.service import GitService, GitServiceError
from agent_service.services.task_suggestion.service import TaskSuggestionService
from agent_service.services.token_usage.service import SUPPORTED_INTERVALS, TokenUsageService
from agent_service.services.favorite.service import FavoriteService
from agent_service.services.privacy.service import PrivacyService
from agent_service.services.feedback.service import FeedbackService
from agent_service.services.vault.service import VaultService
from agent_service.services.agent_change.service import AgentChangeService
from agent_service.services.agent_queue.service import AgentQueueService
from agent_service.services.automation.service import AutomationService
from agent_service.services.activity.service import ActivityService
from agent_service.services.component_library.service import ComponentLibraryService
from agent_service.services.smart_form.service import SmartFormService
from agent_service.services.latex.service import LatexService
from agent_service.services.model_management.service import ModelManagementService
from agent_service.services.storage.service import StorageService

from agent_service.api.grpc.mappers.responses import (
    _build_tool_call_list, _feedback_to_response, _favorite_to_response,
    _knowledge_file_node_to_response, _knowledge_library_to_response,
    _knowledge_rebuild_to_response, _llm_config_preset_to_response,
    _llm_config_to_response, _privacy_to_response, _to_iso,
)

logger = logging.getLogger(__name__)

class AgentQueueGrpcHandlerMixin:
    def ListAgentQueueTasks(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Return the live board or terminal history through the shared queue service."""
        payload = MessageToDict(request)
        service = self._require_agent_queue_service(context)
        user_id = str(payload.get("user_id", ""))
        return ParseDict(
            {"tasks": service.list_tasks(user_id=user_id, history=bool(payload.get("history", False))), "settings": service.get_settings(user_id)},
            Struct(),
        )
    def CreateAgentQueueTask(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Create a durable pending task using the same fields as REST."""
        return ParseDict(self._queue_call(context, self._require_agent_queue_service(context).create_task, MessageToDict(request)), Struct())
    def UpdateAgentQueueTask(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Update a pending task using its task_id from the Struct payload."""
        return ParseDict(self._queue_call(context, self._require_agent_queue_service(context).update_task, MessageToDict(request)), Struct())
    def ContinueAgentQueueTask(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Return a reviewed task to the pending priority queue."""
        return ParseDict(self._queue_call(context, self._require_agent_queue_service(context).restart_task, MessageToDict(request)), Struct())
    def TransitionAgentQueueTask(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Confirm or terminate a task, cancelling its live Agent when required."""
        payload = MessageToDict(request)
        task = self._queue_call(context, self._require_agent_queue_service(context).transition, payload)
        if payload.get("status") == "terminated" and task.get("session_id"):
            self._agent.cancel_session(str(task["session_id"]))
        return ParseDict(task, Struct())
    def DeleteAgentQueueTask(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Delete one pending task and report whether it existed."""
        payload = MessageToDict(request)
        try:
            deleted = self._require_agent_queue_service(context).delete_task(
                user_id=str(payload.get("user_id", "")), task_id=str(payload.get("task_id", ""))
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict({"deleted": deleted}, Struct())
    def UpdateAgentQueueSettings(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Persist a user's queue concurrency setting."""
        return ParseDict(self._queue_call(context, self._require_agent_queue_service(context).update_settings, MessageToDict(request)), Struct())
