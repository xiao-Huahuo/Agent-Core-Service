"""
AgentService gRPC Servicer 实现。

功能说明:
本文件实现 agent_service.proto 定义的 AgentServiceServicer。
1. AgentCore 流式 / 非流式 RPC。
2. SessionService CRUD RPC。
3. 消息历史与 trace 事件 RPC。

由 main.py 注入 AgentCore + SessionService + MessageService:
    servicer = AgentServiceServicer(agent=agent, session_service=session_service, message_service=message_service)
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from typing import Any

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
from agent_service.schemas.feedback import FeedbackCreate, FeedbackUpdate
from agent_service.services.message_service import MessageService
from agent_service.services.session_service import SessionService
from agent_service.services.settings_service import SettingsService
from agent_service.services.knowledge_library_service import KnowledgeLibraryService, KnowledgeLibraryRebuildResult
from agent_service.services.git_service import GitService, GitServiceError
from agent_service.services.task_suggestion_service import TaskSuggestionService
from agent_service.services.token_usage_service import SUPPORTED_INTERVALS, TokenUsageService
from agent_service.services.favorite_service import FavoriteService
from agent_service.services.feedback_service import FeedbackService
from agent_service.services.vault_service import VaultService
from agent_service.services.agent_change_service import AgentChangeService
from agent_service.services.agent_queue_service import AgentQueueService
from agent_service.services.automation_service import AutomationService
from agent_service.services.activity_service import ActivityService
from agent_service.services.component_library_service import ComponentLibraryService
from agent_service.services.smart_form_service import SmartFormService

logger = logging.getLogger(__name__)


class AgentServiceServicer(BaseServicer):
    """AgentService gRPC Servicer。"""

    def __init__(
        self,
        *,
        agent: AgentCore,
        session_service: SessionService,
        message_service: MessageService | None = None,
        settings_service: SettingsService | None = None,
        knowledge_library_service: KnowledgeLibraryService | None = None,
        git_service: GitService | None = None,
        favorite_service: FavoriteService | None = None,
        feedback_service: FeedbackService | None = None,
        vault_service: VaultService | None = None,
        agent_change_service: AgentChangeService | None = None,
        agent_queue_service: AgentQueueService | None = None,
        automation_service: AutomationService | None = None,
        activity_service: ActivityService | None = None,
        component_library_service: ComponentLibraryService | None = None,
        smart_form_service: SmartFormService | None = None,
    ) -> None:
        self._agent = agent
        self._session_service = session_service
        self._message_service = message_service
        self._settings_service = settings_service
        self._knowledge_library_service = knowledge_library_service
        self._git_service = git_service
        self._favorite_service = favorite_service
        self._feedback_service = feedback_service
        self._vault_service = vault_service
        self._agent_change_service = agent_change_service
        self._agent_queue_service = agent_queue_service
        self._automation_service = automation_service
        self._activity_service = activity_service
        self._component_library_service = component_library_service
        self._smart_form_service = smart_form_service

    def shutdown(self) -> None:
        self._agent.close()

    # ------------------------------------------------------------------
    # Agent 流式 RPC
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Agent 非流式 RPC
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Session 管理 RPC
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 用户收藏 RPC
    # ------------------------------------------------------------------

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

    def VaultStatus(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """读取密码库设置状态。"""

        payload = MessageToDict(request)
        return self._vault_struct(context, self._require_vault_service(context).status, user_id=str(payload.get("user_id", "")))

    def VaultDebugMasterPassword(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """读取密码库调试主密码。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).debug_master_password,
            user_id=str(payload.get("user_id", "")),
        )

    def VaultSetup(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """设置密码库主密码并返回独立 token。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).setup,
            user_id=str(payload.get("user_id", "")),
            master_password=str(payload.get("master_password", "")),
        )

    def VaultUnlock(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """验证主密码并返回独立 token。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).unlock,
            user_id=str(payload.get("user_id", "")),
            master_password=str(payload.get("master_password", "")),
        )

    def VaultResetPassword(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """重设密码库主密码并重新加密条目。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).reset_master_password,
            user_id=str(payload.get("user_id", "")),
            new_password=str(payload.get("new_password", "")),
            old_password=str(payload.get("old_password", "")),
        )

    def VaultLock(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """主动锁定一个密码库 token。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).lock,
            token=str(payload.get("token", "")),
        )

    def VaultListItems(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """列出密码库条目。"""

        payload = MessageToDict(request)
        session = self._vault_session_from_payload(context, payload)
        return self._vault_struct(
            context,
            self._require_vault_service(context).list_items,
            session=session,
            query=str(payload.get("query", "")),
            tag=str(payload.get("tag", "")),
            item_type=str(payload.get("item_type", "")),
            trash=bool(payload.get("trash", False)),
        )

    def VaultGetItem(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """读取密码库条目。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).get_item,
            session=self._vault_session_from_payload(context, payload),
            item_id=str(payload.get("item_id", "")),
        )

    def VaultCreateItem(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """创建密码库条目。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).create_item,
            session=self._vault_session_from_payload(context, payload),
            item_type=str(payload.get("item_type", "")),
            fields=dict(payload.get("fields", {}) or {}),
            tags=[str(item) for item in payload.get("tags", [])],
            asset_ids=[str(item) for item in payload.get("asset_ids", [])],
        )

    def VaultUpdateItem(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """更新密码库条目。"""

        payload = MessageToDict(request)
        item_id = str(payload.pop("item_id", ""))
        token = str(payload.pop("token", ""))
        return self._vault_struct(
            context,
            self._require_vault_service(context).update_item,
            session=self._vault_session_from_payload(context, {"token": token}),
            item_id=item_id,
            payload=payload,
        )

    def VaultMoveToTrash(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """密码库条目移入回收站。"""

        return self._vault_item_ids_call(request, context, self._require_vault_service(context).move_to_trash)

    def VaultRestoreItems(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """恢复密码库回收站条目。"""

        return self._vault_item_ids_call(request, context, self._require_vault_service(context).restore_items)

    def VaultPurgeItems(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """永久删除密码库条目。"""

        return self._vault_item_ids_call(request, context, self._require_vault_service(context).purge_items)

    def VaultExportItems(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """导出密码库条目。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).export_items,
            session=self._vault_session_from_payload(context, payload),
            item_ids=[str(item) for item in payload.get("item_ids", [])] or None,
        )

    def VaultImportItems(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """导入密码库条目。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).import_items,
            session=self._vault_session_from_payload(context, payload),
            raw_items=list(payload.get("items", []) or []),
        )

    def VaultListTags(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """列出密码库标签。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            self._require_vault_service(context).list_tags,
            session=self._vault_session_from_payload(context, payload),
        )

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

    # ------------------------------------------------------------------
    # 取消执行 RPC
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 消息历史 RPC
    # ------------------------------------------------------------------

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
                limit=request.limit or 50,
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

    # ------------------------------------------------------------------
    # 观测 / trace 事件 RPC
    # ------------------------------------------------------------------

    def GetEvents(  # noqa: N802
        self, request: EventsRequest, context: grpc.ServicerContext
    ) -> EventsResponse:
        logger.info("GetEvents user=%s session=%s", request.user_id, request.session_id)
        ms = self._require_message_service(context)
        messages = ms.list_session_messages(
            user_id=request.user_id,
            session_id=request.session_id,
            limit=200,
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
                    content=m.content[:500] if m.role in ("assistant", "tool", "system") else "",
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
            limit=request.limit or 120,
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
            days=request.days or 371,
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

    # ------------------------------------------------------------------
    # 用户设置 — 系统提示词条目
    # ------------------------------------------------------------------

    def EnsureUserProfile(  # noqa: N802
        self, request: UserProfileRequest, context: grpc.ServicerContext,
    ) -> UserProfileResponse:
        logger.info("EnsureUserProfile user=%s", request.user_id)
        svc = self._require_settings_service(context)
        try:
            profile = svc.ensure_user_profile(user_id=request.user_id)
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

    def GetLLMConfig(  # noqa: N802
        self, request: LLMConfigRequest, context: grpc.ServicerContext,
    ) -> LLMConfigResponse:
        logger.info("GetLLMConfig user=%s", request.user_id)
        svc = self._require_settings_service(context)
        try:
            return _llm_config_to_response(svc.get_llm_config(user_id=request.user_id))
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    def SaveLLMConfig(  # noqa: N802
        self, request: LLMConfigSaveRequest, context: grpc.ServicerContext,
    ) -> LLMConfigResponse:
        logger.info("SaveLLMConfig user=%s", request.user_id)
        svc = self._require_settings_service(context)
        try:
            payload = svc.save_llm_config(
                user_id=request.user_id,
                api_key=request.api_key,
                base_url=request.base_url,
                model_name=request.model_name,
                small_api_key=request.small_api_key,
                small_base_url=request.small_base_url,
                small_model_name=request.small_model_name,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _llm_config_to_response(payload)

    def GetWebSearchConfig(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Return web-search and embedded-browser networking settings."""

        payload = MessageToDict(request)
        try:
            result = self._require_settings_service(context).get_web_search_config(
                user_id=str(payload.get("user_id") or ""),
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(result, Struct())

    def SaveWebSearchConfig(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Persist the REST-equivalent web-search and browser settings payload."""

        payload = MessageToDict(request)
        try:
            result = self._require_settings_service(context).save_web_search_config(
                user_id=str(payload.get("user_id") or ""),
                proxy_url=str(payload["proxy_url"]).strip() if "proxy_url" in payload else None,
                browser_proxy_url=(
                    str(payload["browser_proxy_url"]).strip()
                    if "browser_proxy_url" in payload
                    else None
                ),
                browser_home_url=(
                    str(payload["browser_home_url"]).strip()
                    if "browser_home_url" in payload
                    else None
                ),
                web_search_enabled=(
                    bool(payload["web_search_enabled"])
                    if "web_search_enabled" in payload
                    else None
                ),
                web_search_max_results=(
                    int(payload["web_search_max_results"])
                    if "web_search_max_results" in payload
                    else None
                ),
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(result, Struct())

    def ListLLMConfigPresets(  # noqa: N802
        self, request: LLMConfigRequest, context: grpc.ServicerContext,
    ) -> LLMConfigPresetListResponse:
        logger.info("ListLLMConfigPresets user=%s", request.user_id)
        svc = self._require_settings_service(context)
        try:
            presets = svc.list_llm_config_presets(user_id=request.user_id)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return LLMConfigPresetListResponse(
            configs=[_llm_config_preset_to_response(item) for item in presets],
        )

    def SaveLLMConfigPreset(  # noqa: N802
        self, request: LLMConfigPresetSaveRequest, context: grpc.ServicerContext,
    ) -> LLMConfigPresetResponse:
        logger.info("SaveLLMConfigPreset user=%s label=%s", request.user_id, request.label)
        svc = self._require_settings_service(context)
        try:
            preset = svc.save_llm_config_preset(
                user_id=request.user_id,
                label=request.label,
                api_key=request.api_key,
                base_url=request.base_url,
                model_name=request.model_name,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return _llm_config_preset_to_response(preset)

    def DeleteLLMConfigPreset(  # noqa: N802
        self, request: LLMConfigPresetDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        logger.info("DeleteLLMConfigPreset config=%s", request.config_id)
        svc = self._require_settings_service(context)
        deleted = svc.delete_llm_config_preset(config_id=request.config_id)
        if not deleted:
            context.abort(grpc.StatusCode.NOT_FOUND, "LLM config preset not found")
        return DeleteResponse(ok=True, deleted_count=1)

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

    # ------------------------------------------------------------------
    # 知识库 Git 管理 RPC
    # ------------------------------------------------------------------

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
            limit=request.limit or 50,
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

    def ListSystemPromptEntries(  # noqa: N802
        self, request: SystemPromptRequest, context: grpc.ServicerContext,
    ) -> SystemPromptEntriesResponse:
        logger.info("ListSystemPromptEntries user=%s", request.user_id)
        svc = self._require_settings_service(context)
        entries = svc.list_system_prompt_entries(user_id=request.user_id)
        return SystemPromptEntriesResponse(
            entries=[SystemPromptEntryResponse(
                prompt_id=e["prompt_id"],
                content=e["content"],
                created_at=e["created_at"],
            ) for e in entries]
        )

    def AddSystemPromptEntry(  # noqa: N802
        self, request: SystemPromptAddRequest, context: grpc.ServicerContext,
    ) -> SystemPromptEntryResponse:
        logger.info("AddSystemPromptEntry user=%s", request.user_id)
        svc = self._require_settings_service(context)
        entry = svc.add_system_prompt_entry(user_id=request.user_id, content=request.content)
        return SystemPromptEntryResponse(
            prompt_id=entry["prompt_id"],
            content=entry["content"],
            created_at=entry["created_at"],
        )

    def DeleteSystemPromptEntry(  # noqa: N802
        self, request: SystemPromptDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        logger.info("DeleteSystemPromptEntry prompt=%s", request.prompt_id)
        svc = self._require_settings_service(context)
        success = svc.delete_system_prompt_entry(prompt_id=request.prompt_id)
        if not success:
            context.abort(grpc.StatusCode.NOT_FOUND, f"prompt entry {request.prompt_id} not found")
        return DeleteResponse(ok=True, deleted_count=1)

    # ------------------------------------------------------------------
    # 用户设置 — 自定义长期记忆
    # ------------------------------------------------------------------

    def ListCustomMemories(  # noqa: N802
        self, request: MemoryListRequest, context: grpc.ServicerContext,
    ) -> MemoryListResponse:
        logger.info("ListCustomMemories user=%s", request.user_id)
        svc = self._require_settings_service(context)
        entries = svc.list_memories(user_id=request.user_id)
        return MemoryListResponse(
            entries=[MemoryEntryResponse(
                memory_id=e["memory_id"],
                content=e["content"],
                importance=e.get("importance", 0.5),
                created_at=e["created_at"],
            ) for e in entries]
        )

    def AddCustomMemory(  # noqa: N802
        self, request: MemoryAddRequest, context: grpc.ServicerContext,
    ) -> MemoryEntryResponse:
        logger.info("AddCustomMemory user=%s", request.user_id)
        svc = self._require_settings_service(context)
        entry = svc.add_memory(
            user_id=request.user_id,
            content=request.content,
            importance=request.importance or 0.5,
        )
        return MemoryEntryResponse(
            memory_id=entry["memory_id"],
            content=entry["content"],
            importance=entry.get("importance", 0.5),
            created_at=entry["created_at"],
        )

    def DeleteCustomMemory(  # noqa: N802
        self, request: MemoryDeleteRequest, context: grpc.ServicerContext,
    ) -> DeleteResponse:
        logger.info("DeleteCustomMemory memory=%s", request.memory_id)
        svc = self._require_settings_service(context)
        success = svc.remove_memory(memory_id=request.memory_id)
        if not success:
            context.abort(grpc.StatusCode.NOT_FOUND, f"memory {request.memory_id} not found")
        return DeleteResponse(ok=True, deleted_count=1)

    # ------------------------------------------------------------------
    # 持久任务队列 RPC
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 定时自动化 RPC
    # ------------------------------------------------------------------

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
        raw_limit = payload.get("limit", 20)
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
        if not 1 <= limit <= 100:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "limit must be between 1 and 100")
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

    def DeleteSmartForm(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """删除当前用户的智能表格，与 REST 删除接口保持一致。"""

        payload = MessageToDict(request)
        user_id = str(payload.get("user_id") or "")
        form_id = str(payload.get("form_id") or "")
        if not user_id or not form_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "user_id and form_id are required")
        deleted = self._require_smart_form_service(context).delete_form(user_id=user_id, form_id=form_id)
        if not deleted:
            context.abort(grpc.StatusCode.NOT_FOUND, "Smart form not found")
        return ParseDict({"deleted": True}, Struct())

    def ListComponentLibraryComponents(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """List component cards with the same fields as the REST endpoint."""

        payload = MessageToDict(request)
        return self._component_library_struct(
            context,
            self._require_component_library_service(context).list_components,
            user_id=str(payload.get("user_id", "")),
            tag=str(payload.get("tag") or "any"),
        )

    def CreateComponentLibraryComponent(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Persist one component upload with the same fields as the REST endpoint."""

        payload = MessageToDict(request)
        return self._component_library_struct(
            context,
            self._require_component_library_service(context).create_component,
            user_id=str(payload.get("user_id", "")),
            source=str(payload.get("source", "")),
            tag=str(payload.get("tag", "")),
            filename=str(payload.get("filename", "")),
        )

    def RenameComponentLibraryComponent(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Persist one inline component title edit through the shared file service."""

        payload = MessageToDict(request)
        return self._component_library_struct(
            context,
            self._require_component_library_service(context).rename_component,
            user_id=str(payload.get("user_id", "")),
            component_id=str(payload.get("component_id", "")),
            title=str(payload.get("title", "")),
        )

    def DeleteComponentLibraryComponent(self, request: Struct, context: grpc.ServicerContext) -> Struct:  # noqa: N802
        """Delete one component through the same file service as REST."""

        payload = MessageToDict(request)
        return self._component_library_struct(
            context,
            self._require_component_library_service(context).delete_component,
            user_id=str(payload.get("user_id", "")),
            component_id=str(payload.get("component_id", "")),
        )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

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

    def _require_smart_form_service(self, context: grpc.ServicerContext) -> SmartFormService:
        """返回注入的智能表格服务,未初始化时终止 RPC。"""

        if self._smart_form_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "SmartFormService not available")
        return self._smart_form_service  # type: ignore[return-value]

    @staticmethod
    def _component_library_struct(
        context: grpc.ServicerContext,
        function: Any,
        **kwargs: Any,
    ) -> Struct:
        """Run a component library operation and map validation to gRPC errors."""

        try:
            payload = function(**kwargs)
        except FileNotFoundError as exc:
            context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(payload, Struct())

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

    def _vault_session_from_payload(self, context: grpc.ServicerContext, payload: dict[str, Any]) -> Any:
        """从 Struct payload 中校验 vault token。"""

        try:
            return self._require_vault_service(context).verify_token(str(payload.get("token", "")))
        except ValueError as exc:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))

    def _vault_item_ids_call(self, request: Struct, context: grpc.ServicerContext, function: Any) -> Struct:
        """执行只需要 token 和 item_ids 的密码库方法。"""

        payload = MessageToDict(request)
        return self._vault_struct(
            context,
            function,
            session=self._vault_session_from_payload(context, payload),
            item_ids=[str(item) for item in payload.get("item_ids", [])],
        )

    @staticmethod
    def _vault_struct(context: grpc.ServicerContext, function: Any, **kwargs: Any) -> Struct:
        """执行密码库方法并转换为 protobuf Struct。"""

        try:
            payload = function(**kwargs)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(payload, Struct())

    @staticmethod
    def _git_struct(
        context: grpc.ServicerContext,
        function: Any,
        **kwargs: Any,
    ) -> Struct:
        """执行 Git 领域方法并转换为 protobuf Struct。"""

        try:
            payload = function(**kwargs)
        except (GitServiceError, ValueError) as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ParseDict(payload, Struct())

    @staticmethod
    def _stream_from_dicts(events_iter: Any) -> Any:
        """将 dict 事件流转换为 ChunkMessage 流,客户端断开时传播取消信号。"""
        try:
            for payload in events_iter:
                tool_calls = []
                for tc in payload.get("tool_calls", []) or []:
                    tool_calls.append(
                        ToolCall(
                            name=tc.get("name", ""),
                            args=tc.get("args", {}),
                            id=tc.get("id", ""),
                        )
                    )

                trace_entries = []
                for te in payload.get("trace", []) or []:
                    trace_entries.append(
                        TraceEntry(
                            node=te.get("node", ""),
                            event=te.get("event", ""),
                            error_type=te.get("error_type", ""),
                            message=te.get("message", ""),
                        )
                    )

                yield ChunkMessage(
                    node=payload.get("node", ""),
                    content=payload.get("content", ""),
                    tool_calls=tool_calls,
                    trace=trace_entries,
                    done=False,
                    model_name=payload.get("model_name", ""),
                    type=payload.get("type", ""),
                    context_messages=payload.get("context_messages", []),
                    metadata=payload.get("metadata", {}),
                    error=payload.get("error", ""),
                )

            yield ChunkMessage(done=True)
        except GeneratorExit:
            try:
                events_iter.close()
            except GeneratorExit:
                pass
            raise

    @staticmethod
    def _build_run_result(result: dict[str, Any]) -> RunResult:
        return RunResult(
            graph_diagram=result.get("graph_diagram", ""),
            final_output=result.get("final_output", ""),
            events=result.get("events", []),
            graph_diagram_path=result.get("graph_diagram_path", ""),
        )

    @staticmethod
    def _session_to_response(session: Any) -> SessionResponse:
        return SessionResponse(
            session_id=session.session_id,
            user_id=session.user_id,
            session_name=session.session_name or "",
            created_at=_to_iso(session.created_at),
            updated_at=_to_iso(session.updated_at),
        )


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _knowledge_rebuild_to_response(result: KnowledgeLibraryRebuildResult) -> KnowledgeRebuildResponse:
    """将知识库重建结果转换为 gRPC 响应。"""

    return KnowledgeRebuildResponse(
        user_id=result.user_id,
        knowledge_dir=result.knowledge_dir,
        frontmatter_dir=result.frontmatter_dir,
        frontmatter_files_seen=result.frontmatter_files_seen,
        frontmatter_files_written=result.frontmatter_files_written,
        frontmatter_files_skipped=result.frontmatter_files_skipped,
        files_seen=result.files_seen,
        files_ingested=result.files_ingested,
        files_skipped=result.files_skipped,
        chunks_created=result.chunks_created,
        chunks_deleted=result.chunks_deleted,
        uploaded_path=result.uploaded_path,
        library_id=result.library_id,
    )


def _favorite_to_response(favorite: Any) -> FavoriteEntryResponse:
    """将收藏 DTO 转换为 gRPC 响应。"""

    return FavoriteEntryResponse(
        favorite_id=str(favorite.favorite_id),
        user_id=str(favorite.user_id),
        library_id=str(favorite.library_id),
        target_type=str(favorite.target_type),
        target_id=str(favorite.target_id),
        created_at=_to_iso(favorite.created_at),
    )


def _feedback_to_response(feedback: Any) -> FeedbackEntryResponse:
    """将反馈 DTO 转换为 gRPC 响应。"""

    return FeedbackEntryResponse(
        feedback_id=str(feedback.feedback_id),
        user_id=str(feedback.user_id),
        content=str(feedback.content),
        source=str(feedback.source),
        page=str(feedback.page),
        created_at=_to_iso(feedback.created_at),
    )


def _llm_config_to_response(payload: dict[str, Any]) -> LLMConfigResponse:
    """将 LLM 配置字典转换为 gRPC 响应。"""

    return LLMConfigResponse(
        user_id=str(payload.get("user_id", "")),
        api_key=str(payload.get("api_key", "")),
        base_url=str(payload.get("base_url", "")),
        model_name=str(payload.get("model_name", "")),
        small_api_key=str(payload.get("small_api_key", "")),
        small_base_url=str(payload.get("small_base_url", "")),
        small_model_name=str(payload.get("small_model_name", "")),
        effective_small_api_key=str(payload.get("effective_small_api_key", "")),
        effective_small_base_url=str(payload.get("effective_small_base_url", "")),
        effective_small_model_name=str(payload.get("effective_small_model_name", "")),
        updated_at=str(payload.get("updated_at", "")),
    )


def _llm_config_preset_to_response(payload: dict[str, Any]) -> LLMConfigPresetResponse:
    """将已保存 LLM 配置字典转换为 gRPC 响应。"""

    return LLMConfigPresetResponse(
        config_id=str(payload.get("config_id", "")),
        user_id=str(payload.get("user_id", "")),
        label=str(payload.get("label", "")),
        api_key=str(payload.get("api_key", "")),
        base_url=str(payload.get("base_url", "")),
        model_name=str(payload.get("model_name", "")),
        created_at=str(payload.get("created_at", "")),
        updated_at=str(payload.get("updated_at", "")),
    )


def _knowledge_library_to_response(payload: dict[str, Any]) -> KnowledgeLibraryEntry:
    """将知识库配置字典转换为 gRPC 响应。"""

    return KnowledgeLibraryEntry(
        library_id=str(payload.get("library_id", "")),
        user_id=str(payload.get("user_id", "")),
        name=str(payload.get("name", "")),
        knowledge_dir=str(payload.get("knowledge_dir", "")),
        is_active=bool(payload.get("is_active", False)),
        created_at=str(payload.get("created_at", "")),
        updated_at=str(payload.get("updated_at", "")),
    )


def _knowledge_file_node_to_response(payload: dict[str, Any]) -> KnowledgeFileNode:
    """将文件树节点字典转换为 gRPC 响应。"""

    return KnowledgeFileNode(
        name=str(payload.get("name", "")),
        path=str(payload.get("path", "")),
        is_dir=bool(payload.get("isDir", False)),
        mtime=str(payload.get("mtime", "")),
        index_status=str(payload.get("indexStatus", "")),
        size=int(payload.get("size", 0)),
        children=[
            _knowledge_file_node_to_response(child)
            for child in payload.get("children", [])
        ],
        graph_status=str(payload.get("graphStatus", "")),
    )


def _build_tool_call_list(tool_calls: list | None) -> list:
    """将数据库中的 tool_calls JSON 列表转换为 proto ToolCall 消息列表。"""
    result = []
    for tc in (tool_calls or []):
        if isinstance(tc, dict):
            result.append(
                ToolCall(
                    name=tc.get("name", ""),
                    args=tc.get("args", {}),
                    id=tc.get("id", ""),
                )
            )
    return result
