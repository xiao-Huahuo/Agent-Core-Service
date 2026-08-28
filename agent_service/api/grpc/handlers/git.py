"""git 领域 gRPC RPC handlers。

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

class GitGrpcHandlerMixin:
    def GetGitStatus(  # noqa: N802
        self, request: GitUserRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """读取当前知识库 Git 状态。"""

        return self._git_struct(
            context,
            self._require_git_service(context).get_status,
            user_id=request.user_id,
        )
    def InitGitRepository(  # noqa: N802
        self, request: GitInitRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """初始化当前知识库 Git 仓库。"""

        return self._git_struct(
            context,
            self._require_git_service(context).initialize_repository,
            user_id=request.user_id,
            initial_branch=request.initial_branch or "main",
        )
    def GetGitHistory(  # noqa: N802
        self, request: GitHistoryRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """读取提交历史和未推送内容。"""

        return self._git_struct(
            context,
            self._require_git_service(context).get_history,
            user_id=request.user_id,
            limit=request.limit or self._limits.api_default_list_limit,
        )
    def GetGitDiff(  # noqa: N802
        self, request: GitDiffRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """读取工作区或暂存区 diff。"""

        return self._git_struct(
            context,
            self._require_git_service(context).get_diff,
            user_id=request.user_id,
            path=request.path,
            staged=request.staged,
        )
    def RestoreGitPaths(  # noqa: N802
        self, request: GitPathsRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """回滚文件并同步清理知识索引。"""

        return self._git_struct(
            context,
            self._require_git_service(context).restore_paths,
            user_id=request.user_id,
            paths=list(request.paths),
        )
    def CommitGitPaths(  # noqa: N802
        self, request: GitCommitRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """提交选中的知识库文件。"""

        return self._git_struct(
            context,
            self._require_git_service(context).commit,
            user_id=request.user_id,
            paths=list(request.paths),
            message=request.message,
        )
    def PushGitBranch(  # noqa: N802
        self, request: GitPushRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """推送本地分支到远程分支。"""

        return self._git_struct(
            context,
            self._require_git_service(context).push,
            user_id=request.user_id,
            local_branch=request.local_branch,
            remote=request.remote,
            remote_branch=request.remote_branch,
            force_with_lease=request.force_with_lease,
            # proto3 的 bool 缺省值为 false；单分支推送保持与 REST 的默认
            # `set_upstream=true` 一致，全部分支模式由 GitService 忽略该参数。
            set_upstream=request.set_upstream or not request.all_branches,
            all_branches=request.all_branches,
        )
    def CreateGitBranch(  # noqa: N802
        self, request: GitBranchRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """创建本地分支。"""

        return self._git_struct(
            context,
            self._require_git_service(context).create_branch,
            user_id=request.user_id,
            name=request.name,
            checkout=request.checkout,
        )
    def SwitchGitBranch(  # noqa: N802
        self, request: GitBranchRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """切换本地分支并清理受影响知识索引。"""

        return self._git_struct(
            context,
            self._require_git_service(context).switch_branch,
            user_id=request.user_id,
            name=request.name,
        )
    def AddGitRemote(  # noqa: N802
        self, request: GitRemoteRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """新增命名远程仓库。"""

        return self._git_struct(
            context,
            self._require_git_service(context).add_remote,
            user_id=request.user_id,
            name=request.name,
            url=request.url,
        )
    def PullGitBranch(  # noqa: N802
        self, request: GitPullRequest, context: grpc.ServicerContext,
    ) -> Struct:
        """快进拉取远程分支并清理受影响知识索引。"""

        return self._git_struct(
            context,
            self._require_git_service(context).pull_fast_forward,
            user_id=request.user_id,
            remote=request.remote,
            branch=request.branch,
        )
