"""sessions 领域 gRPC RPC handlers。

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

class SessionsGrpcHandlerMixin:
    def CreateSession(  # noqa: N802
        self, request: SessionCreateRequest, context: grpc.ServicerContext
    ) -> SessionResponse:
        logger.info("CreateSession user=%s", request.user_id)
        session = self._session_service.create_session(
            SessionCreate(user_id=request.user_id, session_name=request.session_name or None)
        )
        return self._session_to_response(session)
    def GetSession(self, request: SessionIdRequest, context: grpc.ServicerContext) -> SessionResponse:  # noqa: N802
        logger.info("GetSession session=%s", request.session_id)
        session = self._session_service.get_session(request.session_id)
        if session is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"session {request.session_id} not found")
        return self._session_to_response(session)
    def ListUserSessions(  # noqa: N802
        self, request: ListSessionsRequest, context: grpc.ServicerContext,  # noqa: ARG002
    ) -> ListSessionsResponse:
        logger.info("ListUserSessions user=%s", request.user_id)
        sessions = self._session_service.list_user_sessions(request.user_id)
        return ListSessionsResponse(
            sessions=[self._session_to_response(s) for s in sessions]
        )
    def UpdateSessionName(  # noqa: N802
        self, request: SessionUpdateRequest, context: grpc.ServicerContext
    ) -> SessionResponse:
        logger.info("UpdateSessionName session=%s", request.session_id)
        session = self._session_service.update_session_name(
            request.session_id,
            SessionUpdate(session_name=request.session_name),
        )
        if session is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"session {request.session_id} not found")
        return self._session_to_response(session)
    def DeleteSession(  # noqa: N802
        self, request: SessionIdRequest, context: grpc.ServicerContext,  # noqa: ARG002
    ) -> DeleteResponse:
        logger.info("DeleteSession session=%s", request.session_id)
        success = self._session_service.delete_session(request.session_id)
        return DeleteResponse(ok=success, deleted_count=1 if success else 0)
    def DeleteAllSessions(  # noqa: N802
        self, request: DeleteAllSessionsRequest, context: grpc.ServicerContext,  # noqa: ARG002
    ) -> DeleteResponse:
        logger.info("DeleteAllSessions user=%s", request.user_id)
        count = self._session_service.delete_all_user_sessions(request.user_id)
        return DeleteResponse(ok=True, deleted_count=count)
    def GetSessionChanges(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Read the latest durable Agent change snapshot for a session."""

        payload = MessageToDict(request)
        snapshot = self._require_agent_change_service(context).latest_for_session(
            session_id=str(payload.get("session_id", "")),
        )
        return ParseDict({"change_snapshot": snapshot or {}}, Struct())
    def UndoSessionChange(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Guardedly undo a single Agent change snapshot."""

        payload = MessageToDict(request)
        try:
            snapshot = self._require_agent_change_service(context).undo_snapshot(
                snapshot_id=str(payload.get("snapshot_id", "")),
                user_id=str(payload.get("user_id", "")),
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict({"change_snapshot": snapshot}, Struct())
    def ListMessages(  # noqa: N802
        self, request: ListMessagesRequest, context: grpc.ServicerContext
    ) -> ListMessagesResponse:
        logger.info("ListMessages user=%s session=%s", request.user_id, request.session_id)
        ms = self._require_message_service(context)
        if request.session_id:
            observability_scope = False
            messages = ms.list_session_messages(
                user_id=request.user_id,
                session_id=request.session_id,
                limit=request.limit or self._limits.api_default_list_limit,
            )
        else:
            observability_scope = True
            messages = ms.list_user_observability_messages(
                user_id=request.user_id,
                turn_limit=request.limit or None,
            )
        entries = []
        for m in messages:
            metadata = (
                ms.compact_observability_metadata(m.metadata_json)
                if observability_scope
                else (m.metadata_json or {})
            )
            tool_calls = (
                ms.compact_observability_tool_calls(m.tool_calls_json)
                if observability_scope
                else m.tool_calls_json
            )
            entries.append(
                MessageEntry(
                    message_id=m.message_id,
                    session_id=m.session_id,
                    user_id=m.user_id,
                    role=m.role,
                    content=m.content if not observability_scope or m.role in {"user", "assistant"} else "",
                    tool_calls=_build_tool_call_list(tool_calls),
                    metadata=metadata,
                    created_at=_to_iso(m.created_at),
                )
            )
        return ListMessagesResponse(messages=entries)
