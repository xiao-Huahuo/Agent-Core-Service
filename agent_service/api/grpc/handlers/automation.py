"""automation 领域 gRPC RPC handlers。

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

class AutomationGrpcHandlerMixin:
    def ListAutomations(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """列出一个用户的自动化任务，字段语义与 REST /automation/list 一致。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id") or "")
        if not user_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id is required")
        tasks = self._require_automation_service(context).list_tasks(user_id=user_id)
        return ParseDict({"automations": tasks}, Struct())
    def CreateAutomation(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """使用与 REST /automation/add 相同的请求字段创建自动化任务。"""

        payload = MessageToDict(request)
        try:
            body = AutomationCreateRequest.model_validate(payload)
        except ValidationError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        try:
            task = self._require_automation_service(context).create_task(
                user_id=body.user_id,
                text=body.text,
                prompt=body.prompt,
                next_run_at=body.next_run_at,
                timezone_name=body.timezone,
                recurrence=body.recurrence.model_dump(),
                access_mode=body.access_mode,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(task, Struct())
    def ToggleAutomation(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """启用或停用自动化任务，与 REST /automation/toggle 保持一致。"""

        payload = MessageToDict(request)
        try:
            body = AutomationToggleRequest.model_validate(payload)
        except ValidationError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        task = self._require_automation_service(context).set_enabled(
            user_id=body.user_id,
            automation_id=body.automation_id,
            enabled=body.enabled,
        )
        if task is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Automation task not found")
        return ParseDict(task, Struct())
    def ListAutomationRuns(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """列出自动化最近运行记录，与 REST /automation/runs 保持一致。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id") or "")
        automation_id = str(payload.get("automation_id") or "")
        limits = self._limits
        raw_limit = payload.get("limit", limits.automation_run_default_limit)
        try:
            if isinstance(raw_limit, bool):
                raise ValueError
            limit = int(raw_limit)
            if isinstance(raw_limit, float) and not raw_limit.is_integer():
                raise ValueError
        except (TypeError, ValueError):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "limit must be an integer between 1 and 100")
        if not user_id or not automation_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id and automation_id are required")
        if not limits.nonempty_min_length <= limit <= limits.automation_run_max_limit:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"limit must be between {limits.nonempty_min_length} and {limits.automation_run_max_limit}",
            )
        runs = self._require_automation_service(context).list_runs(
            user_id=user_id,
            automation_id=automation_id,
            limit=limit,
        )
        return ParseDict({"runs": runs}, Struct())
    def DeleteAutomation(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """删除自动化及关联数据，与 REST /automation/delete 保持一致。"""

        payload = MessageToDict(request)
        try:
            body = AutomationDeleteRequest.model_validate(payload)
        except ValidationError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        deleted = self._require_automation_service(context).delete_task(
            user_id=body.user_id,
            automation_id=body.automation_id,
        )
        if not deleted:
            context.abort(grpc.StatusCode.NOT_FOUND, "Automation task not found")
        return ParseDict({"deleted": True}, Struct())
