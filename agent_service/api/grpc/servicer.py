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
from datetime import datetime, timezone
from typing import Any

import grpc

from agent_service.agent_core.agent_core import AgentCore
from agent_service.api.recall_details import build_recall_details_payload
from agent_service.api.grpc.agent_service_pb2 import (
    CancelRequest,
    CancelResponse,
    ChunkMessage,
    DeleteAllSessionsRequest,
    DeleteResponse,
    EventEntry,
    EventsRequest,
    EventsResponse,
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
    ToolCall,
    TraceEntry,
)
from agent_service.api.grpc.agent_service_pb2_grpc import AgentServiceServicer as BaseServicer
from agent_service.schemas.session import SessionCreate, SessionUpdate
from agent_service.services.message_service import MessageService
from agent_service.services.session_service import SessionService

logger = logging.getLogger(__name__)


class AgentServiceServicer(BaseServicer):
    """AgentService gRPC Servicer。"""

    def __init__(
        self,
        *,
        agent: AgentCore,
        session_service: SessionService,
        message_service: MessageService | None = None,
    ) -> None:
        self._agent = agent
        self._session_service = session_service
        self._message_service = message_service

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
        )
        return self._build_run_result(result)

    def RunSessionPrompt(self, request: RunRequest, context: grpc.ServicerContext) -> RunResult:  # noqa: N802
        """带 session 上下文的单次运行。"""
        logger.info("RunSessionPrompt user=%s session=%s", request.user_id, request.session_id)
        result = self._agent.run_session_prompt(
            prompt=request.prompt,
            user_id=request.user_id,
            session_id=request.session_id,
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
    # 取消执行 RPC
    # ------------------------------------------------------------------

    def CancelSession(self, request: CancelRequest, context: grpc.ServicerContext) -> CancelResponse:  # noqa: N802
        """取消指定 session 正在执行的图,中断后部分输出自动保存。"""
        logger.info("CancelSession session=%s", request.session_id)
        self._agent.cancel_session(request.session_id)
        return CancelResponse(ok=True)

    # ------------------------------------------------------------------
    # 消息历史 RPC
    # ------------------------------------------------------------------

    def ListMessages(  # noqa: N802
        self, request: ListMessagesRequest, context: grpc.ServicerContext
    ) -> ListMessagesResponse:
        logger.info("ListMessages user=%s session=%s", request.user_id, request.session_id)
        ms = self._require_message_service(context)
        messages = ms.list_session_messages(
            user_id=request.user_id,
            session_id=request.session_id,
            limit=request.limit or 50,
        )
        entries = []
        for m in messages:
            entries.append(
                MessageEntry(
                    message_id=m.message_id,
                    session_id=m.session_id,
                    user_id=m.user_id,
                    role=m.role,
                    content=m.content,
                    tool_calls=_build_tool_call_list(m.tool_calls_json),
                    metadata=m.metadata_json or {},
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

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _require_message_service(self, context: grpc.ServicerContext) -> MessageService:
        if self._message_service is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "MessageService not available")
        return self._message_service  # type: ignore[return-value]

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
