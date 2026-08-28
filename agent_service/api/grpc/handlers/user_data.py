"""user_data 领域 gRPC RPC handlers。

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

class UserDataGrpcHandlerMixin:
    def ListFavorites(  # noqa: N802
        self, request: FavoriteListRequest, context: grpc.ServicerContext,
    ) -> FavoriteListResponse:
        """列出用户收藏,与 REST /favorites 共用 FavoriteService。"""

        try:
            favorites = self._require_favorite_service(context).list_favorites(
                user_id=request.user_id,
                target_type=request.target_type or None,
                library_id=request.library_id if request.filter_library else None,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return FavoriteListResponse(favorites=[_favorite_to_response(item) for item in favorites])
    def AddFavorite(  # noqa: N802
        self, request: FavoriteCreateRequest, context: grpc.ServicerContext,
    ) -> FavoriteEntryResponse:
        """创建收藏;重复收藏返回已有记录。"""

        try:
            favorite = self._require_favorite_service(context).add_favorite(
                FavoriteCreate(
                    user_id=request.user_id,
                    library_id=request.library_id,
                    target_type=request.target_type,  # type: ignore[arg-type]
                    target_id=request.target_id,
                )
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _favorite_to_response(favorite)
    def DeleteFavorite(  # noqa: N802
        self, request: FavoriteDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        """删除用户收藏。"""

        try:
            deleted = self._require_favorite_service(context).delete_favorite(
                user_id=request.user_id,
                library_id=request.library_id,
                target_type=request.target_type,
                target_id=request.target_id,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return DeleteResponse(ok=True, deleted_count=1 if deleted else 0)
    def ListPrivacy(  # noqa: N802
        self, request: PrivacyListRequest, context: grpc.ServicerContext,
    ) -> PrivacyListResponse:
        """列出用户隐私标记,与 REST /privacy 共用 PrivacyService。"""

        try:
            records = self._require_privacy_service(context).list_privacy(
                user_id=request.user_id,
                target_type=request.target_type or None,
                library_id=request.library_id if request.filter_library else None,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return PrivacyListResponse(privacy=[_privacy_to_response(item) for item in records])
    def AddPrivacy(  # noqa: N802
        self, request: PrivacyCreateRequest, context: grpc.ServicerContext,
    ) -> PrivacyEntryResponse:
        """创建隐私标记;重复请求返回已有记录。"""

        try:
            record = self._require_privacy_service(context).add_privacy(
                PrivacyCreate(
                    user_id=request.user_id,
                    library_id=request.library_id,
                    target_type=request.target_type,  # type: ignore[arg-type]
                    target_id=request.target_id,
                )
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _privacy_to_response(record)
    def DeletePrivacy(  # noqa: N802
        self, request: PrivacyDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        """删除用户隐私标记。"""

        try:
            deleted = self._require_privacy_service(context).delete_privacy(
                user_id=request.user_id,
                library_id=request.library_id,
                target_type=request.target_type,
                target_id=request.target_id,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return DeleteResponse(ok=True, deleted_count=1 if deleted else 0)
    def ListFeedback(  # noqa: N802
        self, request: FeedbackListRequest, context: grpc.ServicerContext,
    ) -> FeedbackListResponse:
        """List the current user's feedback entries."""

        try:
            feedback = self._require_feedback_service(context).list_feedback(
                user_id=request.user_id,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return FeedbackListResponse(feedback=[_feedback_to_response(item) for item in feedback])
    def AddFeedback(  # noqa: N802
        self, request: FeedbackCreateRequest, context: grpc.ServicerContext,
    ) -> FeedbackEntryResponse:
        """提交并持久化一条用户反馈。"""

        try:
            feedback = self._require_feedback_service(context).add_feedback(
                FeedbackCreate(
                    user_id=request.user_id,
                    content=request.content,
                    source=request.source or "editor_activity_bar",
                    page=request.page,
                )
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _feedback_to_response(feedback)
    def UpdateFeedback(  # noqa: N802
        self, request: FeedbackUpdateRequest, context: grpc.ServicerContext,
    ) -> FeedbackEntryResponse:
        """Update one persisted feedback entry."""

        try:
            feedback = self._require_feedback_service(context).update_feedback(
                feedback_id=request.feedback_id,
                payload=FeedbackUpdate(content=request.content),
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        if feedback is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "feedback not found")
        return _feedback_to_response(feedback)
    def DeleteFeedback(  # noqa: N802
        self, request: FeedbackDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        """Delete one persisted feedback entry."""

        try:
            deleted = self._require_feedback_service(context).delete_feedback(
                feedback_id=request.feedback_id,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return DeleteResponse(ok=True, deleted_count=1 if deleted else 0)
