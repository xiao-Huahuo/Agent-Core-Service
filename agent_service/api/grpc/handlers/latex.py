"""latex 领域 gRPC RPC handlers。

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

class LatexGrpcHandlerMixin:
    def GetLatexStatus(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802, ARG002
        """返回与 REST `/settings/latex/status` 相同的运行时状态。"""

        return ParseDict(self._require_latex_service(context).get_status(), Struct())
    def GetLatexManagement(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """返回与 REST `/settings/latex/management` 相同的编译管理详情。"""

        self._require_struct_user_id(request=request, context=context)
        return ParseDict(self._require_latex_service(context).get_management_status(), Struct())
    def StartLatexInstall(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """在校验用户标识后启动托管 MiKTeX 安装。"""

        self._require_struct_user_id(request=request, context=context)
        try:
            payload = self._require_latex_service(context).start_install()
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(payload, Struct())
    def CancelLatexInstall(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """取消当前托管 MiKTeX 安装。"""

        self._require_struct_user_id(request=request, context=context)
        return ParseDict(self._require_latex_service(context).cancel_install(), Struct())
    def UninstallManagedLatex(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """只卸载 MetaWeave 托管的 MiKTeX。"""

        self._require_struct_user_id(request=request, context=context)
        try:
            payload = self._require_latex_service(context).uninstall_managed()
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(payload, Struct())
    def CompileLatex(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """编译知识库 LaTeX 并返回 REST 同形结果。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id") or "")
        path = str(payload.get("path") or "")
        if not user_id or not path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id and path are required")
        try:
            result = self._require_latex_service(context).compile_file(user_id=user_id, path=path)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except RuntimeError as exc:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        return ParseDict(result, Struct())
    def ClearLatexStorage(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """清理明确允许回收的 LaTeX 仓库、临时或编译缓存。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id") or "")
        path_key = str(payload.get("path_key") or "")
        allowed = {"latex_repository_dir", "latex_temp_dir", "latex_build_cache_dir"}
        if not user_id or path_key not in allowed:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "valid user_id and LaTeX cache path_key are required")
        service = StorageService(
            config=self._agent.config,
            settings_service=self._require_settings_service(context),
        )
        try:
            result = service.clear_path(path_key=path_key, user_id=user_id)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(result, Struct())
