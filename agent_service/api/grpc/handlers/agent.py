"""agent 领域 gRPC RPC handlers。

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

class AgentGrpcHandlerMixin:
    def StreamRun(self, request: RunRequest, context: grpc.ServicerContext):  # noqa: N802
        """无状态流式运行。"""
        logger.info("StreamRun user=%s session=%s", request.user_id, request.session_id)
        yield from self._stream_from_dicts(
            self._agent.stream_run(
                prompt=request.prompt,
                user_id=request.user_id,
                session_id=request.session_id,
                agent_mode=getattr(request, "agent_mode", "") or "plan",
                agent_access_mode=getattr(request, "agent_access_mode", "") or "sandbox",
            )
        )
    def StreamSessionPrompt(self, request: RunRequest, context: grpc.ServicerContext):  # noqa: N802
        """带 session 上下文的流式运行。"""
        logger.info("StreamSessionPrompt user=%s session=%s", request.user_id, request.session_id)
        yield from self._stream_from_dicts(
            self._agent.stream_session_prompt(
                prompt=request.prompt,
                user_id=request.user_id,
                session_id=request.session_id,
                reference=request.reference or None,
                agent_mode=getattr(request, "agent_mode", "") or "auto",
                agent_access_mode=getattr(request, "agent_access_mode", "") or "sandbox",
            )
        )
    def RunOnce(self, request: RunRequest, context: grpc.ServicerContext) -> RunResult:  # noqa: N802
        """无状态单次运行。"""
        logger.info("RunOnce user=%s session=%s", request.user_id, request.session_id)
        result = self._agent.run_once(
            prompt=request.prompt,
            user_id=request.user_id,
            session_id=request.session_id,
            agent_mode=getattr(request, "agent_mode", "") or "plan",
            agent_access_mode=getattr(request, "agent_access_mode", "") or "sandbox",
        )
        return self._build_run_result(result)
    def RunSessionPrompt(self, request: RunRequest, context: grpc.ServicerContext) -> RunResult:  # noqa: N802
        """带 session 上下文的单次运行。"""
        logger.info("RunSessionPrompt user=%s session=%s", request.user_id, request.session_id)
        result = self._agent.run_session_prompt(
            prompt=request.prompt,
            user_id=request.user_id,
            session_id=request.session_id,
            reference=request.reference or None,
            agent_mode=getattr(request, "agent_mode", "") or "auto",
            agent_access_mode=getattr(request, "agent_access_mode", "") or "sandbox",
        )
        return self._build_run_result(result)
    def CancelSession(self, request: CancelRequest, context: grpc.ServicerContext) -> CancelResponse:  # noqa: N802
        """取消指定 session 正在执行的图,中断后部分输出自动保存。"""
        logger.info("CancelSession session=%s", request.session_id)
        self._agent.cancel_session(request.session_id)
        return CancelResponse(ok=True)
    def ListChildAgents(  # noqa: N802
        self, request: ChildAgentListRequest, context: grpc.ServicerContext
    ) -> ChildAgentListResponse:
        """读取指定会话内子 Agent 的状态与结果。"""

        children = self._agent.list_child_agents_for_session(request.session_id)
        return ChildAgentListResponse(
            session_id=request.session_id,
            children=[
                ChildAgentRecord(
                    run_id=str(child.get("run_id", "")),
                    parent_run_id=str(child.get("parent_run_id", "")),
                    goal=str(child.get("goal", "")),
                    mode=str(child.get("mode", "")),
                    status=str(child.get("status", "")),
                    access_mode=str(child.get("access_mode", "")),
                    allowed_tools=list(child.get("allowed_tools", [])),
                    summary=str(child.get("summary", "")),
                    result_json=json.dumps(child.get("result"), ensure_ascii=False),
                    error=str(child.get("error") or ""),
                    category=str(child.get("category", "")),
                    name=str(child.get("name", "")),
                )
                for child in children
            ],
        )
    def StopChildAgent(  # noqa: N802
        self, request: ChildAgentControlRequest, context: grpc.ServicerContext
    ) -> ChildAgentControlResponse:
        """停止指定子 Agent。"""

        return ChildAgentControlResponse(
            run_id=request.run_id,
            ok=self._agent.stop_child_agent(request.run_id),
        )
    def UpdateChildAgent(  # noqa: N802
        self, request: ChildAgentUpdateRequest, context: grpc.ServicerContext
    ) -> ChildAgentControlResponse:
        """向指定子 Agent 投递上下文更新。"""

        update = MessageToDict(request.update) if request.HasField("update") else {}
        self._agent.update_child_agent(request.run_id, update)
        return ChildAgentControlResponse(run_id=request.run_id, ok=True)
    def GetEvents(  # noqa: N802
        self, request: EventsRequest, context: grpc.ServicerContext
    ) -> EventsResponse:
        logger.info("GetEvents user=%s session=%s", request.user_id, request.session_id)
        ms = self._require_message_service(context)
        messages = ms.list_session_messages(
            user_id=request.user_id,
            session_id=request.session_id,
            limit=self._limits.api_large_list_limit,
        )
        events = []
        for m in messages:
            meta = m.metadata_json or {}
            node_name = meta.get("node", "")
            if not node_name:
                continue
            events.append(
                EventEntry(
                    message_id=m.message_id,
                    role=m.role,
                    node=node_name,
                content=(
                    m.content[:self._limits.agent_event_content_preview_chars]
                    if m.role in ("assistant", "tool", "system")
                    else ""
                ),
                    tool_calls=_build_tool_call_list(m.tool_calls_json),
                    created_at=_to_iso(m.created_at),
                    metadata=meta,
                )
            )
        return EventsResponse(
            session_id=request.session_id,
            user_id=request.user_id,
            event_count=len(events),
            events=events,
        )
    def GetRecallDetails(  # noqa: N802
        self, request: RecallDetailsRequest, context: grpc.ServicerContext
    ) -> RecallDetailsResponse:
        """返回最近一次真实召回快照,供外部面板复现 ReRank 前后切换。"""

        logger.info("GetRecallDetails user=%s session=%s", request.user_id, request.session_id)
        ms = self._require_message_service(context)
        payload = build_recall_details_payload(
            agent=self._agent,
            message_service=ms,
            user_id=request.user_id,
            session_id=request.session_id,
        )
        return RecallDetailsResponse(
            session_id=payload["session_id"],
            user_id=payload["user_id"],
            created_at=payload["created_at"],
            query=payload["query"],
            rag_metrics=payload["rag_metrics"],
            memory_recall=payload["memory_recall"],
            knowledge_recall=payload["knowledge_recall"],
        )
    def GetTaskSuggestions(  # noqa: N802
        self, request: TaskSuggestionsRequest, context: grpc.ServicerContext
    ) -> TaskSuggestionsResponse:
        """Return likely next user tasks generated from the current session context."""

        logger.info("GetTaskSuggestions user=%s session=%s", request.user_id, request.session_id)
        service = TaskSuggestionService(
            agent=self._agent,
            message_service=self._require_message_service(context),
        )
        payload = service.generate_suggestions(user_id=request.user_id, session_id=request.session_id)
        return TaskSuggestionsResponse(suggestions=payload.get("suggestions", []))
    def GetTokenUsage(  # noqa: N802
        self, request: TokenUsageRequest, context: grpc.ServicerContext
    ) -> Struct:
        """Return persisted token usage dashboard statistics."""

        logger.info("GetTokenUsage user=%s session=%s", request.user_id, request.session_id)
        interval = request.interval if request.interval in SUPPORTED_INTERVALS else "5m"
        service = TokenUsageService(config=self._agent.config)
        payload = service.get_dashboard_stats(
            user_id=request.user_id,
            session_id=request.session_id or None,
            interval=interval,
            limit=request.limit or self._limits.token_usage_default_limit,
        )
        return ParseDict(payload, Struct())
    def GetActivityHeatmap(  # noqa: N802
        self, request: ActivityHeatmapRequest, context: grpc.ServicerContext
    ) -> Struct:
        """Return the same persisted daily activity heatmap exposed by REST."""

        service = self._activity_service
        if service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "ActivityService not initialized")
        service.sync_existing_records(user_id=request.user_id)
        payload = service.get_heatmap(
            user_id=request.user_id,
            days=request.days or self._limits.activity_heatmap_max_days,
            timezone_name=request.timezone or "Asia/Shanghai",
        )
        return ParseDict(payload, Struct())
    def GetRegisteredTools(  # noqa: N802
        self, request: ToolListRequest, context: grpc.ServicerContext,
    ) -> ToolListResponse:
        """返回当前 Agent 最终注册表中的所有工具基础信息。"""

        logger.info("GetRegisteredTools")
        payload = self._agent.list_registered_tools()
        return ToolListResponse(
            tool_count=int(payload.get("tool_count", 0)),
            tools=[
                ToolInfo(
                    name=str(tool.get("name", "")),
                    display_name=str(tool.get("display_name", "")),
                    description=str(tool.get("description", "")),
                    args_schema=ParseDict(tool.get("args_schema", {}) or {}, Struct()),
                    argument_count=int(tool.get("argument_count", 0)),
                )
                for tool in payload.get("tools", [])
            ],
        )
