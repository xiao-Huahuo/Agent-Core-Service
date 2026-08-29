"""knowledge 领域 gRPC RPC handlers。

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

class KnowledgeGrpcHandlerMixin:
    def SearchAllLibraries(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """执行与 REST 完全相同的四库联合搜索。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id") or "").strip()
        query = str(payload.get("query") or "").strip()
        raw_sources = payload.get("sources") or []
        sources = {str(source).strip() for source in raw_sources if str(source).strip()}
        if not user_id or not query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id and query are required")
        try:
            result = self._require_unified_search_service(context).search(
                user_id=user_id,
                query=query,
                sources=sources,
                fulltext=bool(payload.get("fulltext", True)),
                semantic=bool(payload.get("semantic", False)),
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except RuntimeError as exc:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        return ParseDict(result, Struct())

    def UpdateUserKnowledgeDir(  # noqa: N802
        self, request: UserKnowledgeDirUpdateRequest, context: grpc.ServicerContext,
    ) -> UserProfileResponse:
        """更新用户 active 知识库目录并持久化,不执行灌库。"""

        logger.info("UpdateUserKnowledgeDir user=%s dir=%s", request.user_id, request.knowledge_dir)
        svc = self._require_settings_service(context)
        try:
            profile = svc.update_knowledge_dir(
                user_id=request.user_id,
                knowledge_dir=request.knowledge_dir,
                name=request.name or None,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return UserProfileResponse(
            user_id=profile["user_id"],
            knowledge_dir=profile["knowledge_dir"],
            created_at=profile["created_at"],
            updated_at=profile["updated_at"],
            active_library_id=profile.get("active_library_id", ""),
            active_knowledge_library=_knowledge_library_to_response(
                profile.get("active_knowledge_library") or {}
            ),
            knowledge_libraries=[
                _knowledge_library_to_response(item)
                for item in profile.get("knowledge_libraries", [])
            ],
        )
    def RebuildKnowledge(  # noqa: N802
        self, request: KnowledgeRebuildRequest, context: grpc.ServicerContext,
    ) -> KnowledgeRebuildResponse:
        """重新扫描用户知识库并灌入向量库。"""

        logger.info("RebuildKnowledge user=%s", request.user_id)
        svc = self._require_knowledge_library_service(context)
        try:
            result = svc.rebuild_user_knowledge(
                user_id=request.user_id,
                knowledge_dir=request.knowledge_dir or None,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_rebuild_to_response(result)
    def CreateKnowledgeIngestionJobs(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """创建与 REST 相同的持久化单文件入库任务。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id", "")).strip()
        paths = [str(path) for path in payload.get("paths", [])]
        if not user_id or not paths:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id and non-empty paths are required")
        service = self._require_knowledge_ingestion_job_service(context)
        try:
            jobs = service.submit(
                user_id=user_id,
                paths=paths,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict({"jobs": jobs}, Struct())
    def ListKnowledgeIngestionJobs(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """列出持久化单文件入库任务。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id", "")).strip()
        if not user_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id is required")
        jobs = self._require_knowledge_ingestion_job_service(context).list_jobs(
            user_id=user_id,
            active_only=bool(payload.get("active_only", False)),
        )
        return ParseDict({"jobs": jobs}, Struct())
    def CancelKnowledgeIngestionJob(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """中止单文件入库任务并返回最终任务状态。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id", "")).strip()
        job_id = str(payload.get("job_id", "")).strip()
        if not user_id or not job_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id and job_id are required")
        job = self._require_knowledge_ingestion_job_service(context).cancel(
            job_id=job_id,
            user_id=user_id,
        )
        if job is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "ingestion job not found")
        return ParseDict(job, Struct())
    def UploadKnowledgeFile(  # noqa: N802
        self, request: KnowledgeFileUploadRequest, context: grpc.ServicerContext,
    ) -> KnowledgeRebuildResponse:
        """上传文件到用户知识库目录并重新灌库。"""

        logger.info("UploadKnowledgeFile user=%s filename=%s", request.user_id, request.filename)
        svc = self._require_knowledge_library_service(context)
        try:
            uploaded_path = svc.write_uploaded_file(
                user_id=request.user_id,
                filename=request.filename,
                content=request.content,
                relative_dir=request.relative_dir,
            )
            result = svc.rebuild_user_knowledge(
                user_id=request.user_id,
                uploaded_path=str(uploaded_path),
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_rebuild_to_response(result)
    def ListKnowledgeFiles(  # noqa: N802
        self, request: KnowledgeFileTreeRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileTreeResponse:
        """列出当前 active 知识库的递归文件树。"""

        logger.info("ListKnowledgeFiles user=%s", request.user_id)
        svc = self._require_knowledge_library_service(context)
        try:
            tree = svc.list_files(user_id=request.user_id)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return KnowledgeFileTreeResponse(tree=[_knowledge_file_node_to_response(node) for node in tree])
    def ReadKnowledgeFile(  # noqa: N802
        self, request: KnowledgeFileContentRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileContentResponse:
        """读取当前 active 知识库中的 UTF-8 文本文件。"""

        logger.info("ReadKnowledgeFile user=%s path=%s", request.user_id, request.path)
        svc = self._require_knowledge_library_service(context)
        try:
            payload = svc.read_file(user_id=request.user_id, path=request.path)
        except UnicodeDecodeError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "file is not valid UTF-8 text")
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return KnowledgeFileContentResponse(
            path=str(payload.get("path", "")),
            content=str(payload.get("content", "")),
            mtime=str(payload.get("mtime", "")),
            size=int(payload.get("size", 0)),
        )
    def PreviewKnowledgePdfPage(  # noqa: N802
        self, request: KnowledgePdfPageRequest, context: grpc.ServicerContext,
    ) -> KnowledgePdfPageResponse:
        """按需栅格化并返回一页 PDF PNG，与 REST Preview1 使用同一缓存。"""

        svc = self._require_knowledge_library_service(context)
        try:
            file_path, media_type = svc.render_pdf_page(
                user_id=request.user_id,
                path=request.path,
                page=request.page,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return KnowledgePdfPageResponse(content=file_path.read_bytes(), mime_type=media_type)
    def WriteKnowledgeFile(  # noqa: N802
        self, request: KnowledgeFileWriteRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileNode:
        """
        保存当前 active 知识库中的文本文件。

        保存只落盘并刷新文件树,不会触发向量灌库。
        """

        logger.info("WriteKnowledgeFile user=%s path=%s", request.user_id, request.path)
        svc = self._require_knowledge_library_service(context)
        try:
            node = svc.write_file(user_id=request.user_id, path=request.path, content=request.content)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_file_node_to_response(node)
    def CreateKnowledgeFile(  # noqa: N802
        self, request: KnowledgeFileCreateRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileNode:
        """在当前 active 知识库中新建文本文件。"""

        logger.info("CreateKnowledgeFile user=%s path=%s", request.user_id, request.path)
        svc = self._require_knowledge_library_service(context)
        try:
            node = svc.create_file(user_id=request.user_id, path=request.path, content=request.content)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_file_node_to_response(node)
    def CreateKnowledgeFolder(  # noqa: N802
        self, request: KnowledgeFolderCreateRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileNode:
        """在当前 active 知识库中新建文件夹。"""

        logger.info("CreateKnowledgeFolder user=%s path=%s", request.user_id, request.path)
        svc = self._require_knowledge_library_service(context)
        try:
            node = svc.create_folder(user_id=request.user_id, path=request.path)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_file_node_to_response(node)
    def CopyKnowledgePath(  # noqa: N802
        self, request: KnowledgePathCopyRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileNode:
        """复制当前 active 知识库中的文件/文件夹。"""

        logger.info(
            "CopyKnowledgePath user=%s source=%s target=%s",
            request.user_id,
            request.source_path,
            request.target_path,
        )
        svc = self._require_knowledge_library_service(context)
        try:
            node = svc.copy_path(
                user_id=request.user_id,
                source_path=request.source_path,
                target_path=request.target_path,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_file_node_to_response(node)
    def DeleteKnowledgePath(  # noqa: N802
        self, request: KnowledgePathDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        """删除当前 active 知识库中的文件或文件夹。"""

        logger.info("DeleteKnowledgePath user=%s path=%s", request.user_id, request.path)
        svc = self._require_knowledge_library_service(context)
        try:
            svc.delete_path(user_id=request.user_id, path=request.path)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return DeleteResponse(ok=True, deleted_count=1)
    def RenameKnowledgePath(  # noqa: N802
        self, request: KnowledgePathRenameRequest, context: grpc.ServicerContext,
    ) -> KnowledgeFileNode:
        """移动或重命名当前 active 知识库中的文件/文件夹。"""

        logger.info(
            "RenameKnowledgePath user=%s source=%s target=%s",
            request.user_id,
            request.source_path,
            request.target_path,
        )
        svc = self._require_knowledge_library_service(context)
        try:
            node = svc.rename_path(
                user_id=request.user_id,
                source_path=request.source_path,
                target_path=request.target_path,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _knowledge_file_node_to_response(node)
