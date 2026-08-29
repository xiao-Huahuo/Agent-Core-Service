"""gRPC 依赖可用性与领域错误映射。

方法体由主 servicer 机械迁移。
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
from agent_service.services.unified_search import UnifiedSearchService
from agent_service.services.smart_form.service import SmartFormService
from agent_service.services.latex.service import LatexService
from agent_service.services.model_management.service import ModelManagementService
from agent_service.services.storage.service import StorageService

class GrpcErrorMapperMixin:
    def _require_message_service(self, context: grpc.ServicerContext) -> MessageService:
        if self._message_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "MessageService not available")
        return self._message_service  # type: ignore[return-value]
    def _require_settings_service(self, context: grpc.ServicerContext) -> SettingsService:
        if self._settings_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "SettingsService not available")
        return self._settings_service  # type: ignore[return-value]
    def _require_knowledge_library_service(self, context: grpc.ServicerContext) -> KnowledgeLibraryService:
        if self._knowledge_library_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "KnowledgeLibraryService not available")
        return self._knowledge_library_service  # type: ignore[return-value]
    def _require_knowledge_ingestion_job_service(
        self,
        context: grpc.ServicerContext,
    ) -> KnowledgeIngestionJobService:
        """返回单文件入库任务服务，未初始化时终止 RPC。"""

        if self._knowledge_ingestion_job_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "KnowledgeIngestionJobService not available")
        return self._knowledge_ingestion_job_service  # type: ignore[return-value]
    def _require_git_service(self, context: grpc.ServicerContext) -> GitService:
        """返回注入的 GitService,未就绪时终止 RPC。"""

        if self._git_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "GitService not available")
        return self._git_service  # type: ignore[return-value]
    def _require_favorite_service(self, context: grpc.ServicerContext) -> FavoriteService:
        """返回注入的 FavoriteService,未就绪时终止 RPC。"""

        if self._favorite_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "FavoriteService not available")
        return self._favorite_service  # type: ignore[return-value]
    def _require_privacy_service(self, context: grpc.ServicerContext) -> PrivacyService:
        """返回注入的 PrivacyService,未就绪时终止 RPC。"""

        if self._privacy_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "PrivacyService not available")
        return self._privacy_service  # type: ignore[return-value]
    def _require_feedback_service(self, context: grpc.ServicerContext) -> FeedbackService:
        """返回注入的 FeedbackService,未就绪时终止 RPC。"""

        if self._feedback_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "FeedbackService not available")
        return self._feedback_service  # type: ignore[return-value]
    def _require_vault_service(self, context: grpc.ServicerContext) -> VaultService:
        """返回注入的 VaultService,未就绪时终止 RPC。"""

        if self._vault_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "VaultService not available")
        return self._vault_service  # type: ignore[return-value]
    def _require_agent_change_service(self, context: grpc.ServicerContext) -> AgentChangeService:
        """Return the injected durable Agent change service."""

        if self._agent_change_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "AgentChangeService not available")
        return self._agent_change_service  # type: ignore[return-value]
    def _require_agent_queue_service(self, context: grpc.ServicerContext) -> AgentQueueService:
        """Return the durable queue service or report an unavailable application runtime."""
        if self._agent_queue_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "AgentQueueService not available")
        return self._agent_queue_service  # type: ignore[return-value]
    def _require_automation_service(self, context: grpc.ServicerContext) -> AutomationService:
        """返回注入的自动化服务，未初始化时使用标准 gRPC 状态终止调用。"""

        if self._automation_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "AutomationService not available")
        return self._automation_service  # type: ignore[return-value]
    def _require_component_library_service(self, context: grpc.ServicerContext) -> ComponentLibraryService:
        """Return the injected component library service or abort the RPC."""

        if self._component_library_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "ComponentLibraryService not available")
        return self._component_library_service  # type: ignore[return-value]
    def _require_unified_search_service(self, context: grpc.ServicerContext) -> UnifiedSearchService:
        """返回注入的四库联合搜索服务，未初始化时终止 RPC。"""

        if self._unified_search_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "UnifiedSearchService not available")
        return self._unified_search_service  # type: ignore[return-value]
    def _require_smart_form_service(self, context: grpc.ServicerContext) -> SmartFormService:
        """返回注入的智能表格服务,未初始化时终止 RPC。"""

        if self._smart_form_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "SmartFormService not available")
        return self._smart_form_service  # type: ignore[return-value]
    def _require_latex_service(self, context: grpc.ServicerContext) -> LatexService:
        """返回注入的 LaTeX 服务，未初始化时终止 RPC。"""

        if self._latex_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "LatexService not available")
        return self._latex_service  # type: ignore[return-value]
    def _require_model_management_service(self, context: grpc.ServicerContext) -> ModelManagementService:
        """返回注入的模型管理服务，未初始化时终止 RPC。"""

        if self._model_management_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "ModelManagementService not available")
        return self._model_management_service  # type: ignore[return-value]
    @staticmethod
    def _require_struct_user_id(*, request: Struct, context: grpc.ServicerContext) -> str:
        """从通用 Struct 请求中提取必需的用户标识。"""

        user_id = str(MessageToDict(request).get("user_id") or "")
        if not user_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id is required")
        return user_id
    @staticmethod
    def _queue_call(context: grpc.ServicerContext, function: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Call a queue operation and map domain validation to standard gRPC errors."""
        try:
            result = function(**payload)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        if result is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "queue task not found")
        return result
