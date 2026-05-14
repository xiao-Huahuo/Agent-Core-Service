"""
AgentService gRPC Servicer 实现。

功能说明:
本文件实现 `agent_service.proto` 定义的 `AgentServiceServicer`,负责:
1. 将 AgentCore 的 4 个方法映射为 gRPC unary / server-streaming RPC。
2. 将 SessionService 的 5 个 CRUD 映射为 gRPC unary RPC。
3. 在流式 RPC 中解析 SSE chunk → ChunkMessage,并以 done=True 哨兵结束流。

使用说明:
由 `main.py` 在 FastAPI lifespan 中创建并注入 AgentCore + SessionService:
    servicer = AgentServiceServicer(agent=agent, session_service=session_service)
    add_AgentServiceServicer_to_server(servicer, grpc_server)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import grpc

from agent_service.agent_core.agent_core import AgentCore
from agent_service.api.grpc.agent_service_pb2 import (
    ChunkMessage,
    DeleteResponse,
    ListSessionsResponse,
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
from agent_service.services.session_service import SessionService

logger = logging.getLogger(__name__)


class AgentServiceServicer(BaseServicer):
    """
    AgentService gRPC Servicer。

    agent: AgentCore 实例,由 main.py 创建并注入。
    session_service: SessionService 实例,由 main.py 创建并注入。
    """

    def __init__(self, *, agent: AgentCore, session_service: SessionService) -> None:
        self._agent = agent
        self._session_service = session_service

    def shutdown(self) -> None:
        """关闭 servicer 持有的资源（委托给 AgentCore.close()）。"""

        self._agent.close()

    # ------------------------------------------------------------------
    # Agent 流式 RPC
    # ------------------------------------------------------------------

    def StreamRun(self, request: RunRequest, context: grpc.ServicerContext):  # noqa: N802
        """无状态流式运行。"""

        logger.info("StreamRun user=%s session=%s", request.user_id, request.session_id)
        yield from self._stream_from_dicts(
            self._agent.stream_run_events(
                prompt=request.prompt,
                user_id=request.user_id,
                session_id=request.session_id,
            )
        )

    def StreamSessionPrompt(self, request: RunRequest, context: grpc.ServicerContext):  # noqa: N802
        """带 session 上下文的流式运行。"""

        logger.info("StreamSessionPrompt user=%s session=%s", request.user_id, request.session_id)
        yield from self._stream_from_dicts(
            self._agent.stream_session_prompt_events(
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
        """创建新 session。"""

        logger.info("CreateSession user=%s", request.user_id)
        session = self._session_service.create_session(
            SessionCreate(user_id=request.user_id, session_name=request.session_name or None)
        )
        return self._session_to_response(session)

    def GetSession(self, request: SessionIdRequest, context: grpc.ServicerContext) -> SessionResponse:  # noqa: N802
        """获取指定 session。"""

        logger.info("GetSession session=%s", request.session_id)
        session = self._session_service.get_session(request.session_id)
        if session is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"session {request.session_id} not found")
        return self._session_to_response(session)

    def ListUserSessions(  # noqa: N802
        self, request: ListSessionsRequest, context: grpc.ServicerContext,  # noqa: ARG002
    ) -> ListSessionsResponse:
        """列出用户的所有 session。"""

        logger.info("ListUserSessions user=%s", request.user_id)
        sessions = self._session_service.list_user_sessions(request.user_id)
        return ListSessionsResponse(
            sessions=[self._session_to_response(s) for s in sessions]
        )

    def UpdateSessionName(  # noqa: N802
        self, request: SessionUpdateRequest, context: grpc.ServicerContext
    ) -> SessionResponse:
        """更新 session 名称。"""

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
        """删除 session。"""

        logger.info("DeleteSession session=%s", request.session_id)
        success = self._session_service.delete_session(request.session_id)
        return DeleteResponse(success=success)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _stream_from_dicts(events_iter: Any) -> Any:
        """将统一 dict 事件流直接转换为 ChunkMessage 流(gRPC server-streaming)。

        events_iter: `AgentCore.stream_*_events()` 返回的 Iterator[dict]。
        HTTP 侧用 _format_sse() 从同一 dict 流生成 SSE。
        """

        for payload in events_iter:
            tool_calls = []
            for tc in payload.get("tool_calls", []) or []:
                tool_calls.append(
                    ToolCall(
                        name=tc.get("name", ""),
                        args_json=json.dumps(tc.get("args", {}), ensure_ascii=False),
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
            )

        yield ChunkMessage(done=True)

    @staticmethod
    def _build_run_result(result: dict[str, Any]) -> RunResult:
        """将 AgentCore.run_*() 返回的 dict 映射为 RunResult。"""

        return RunResult(
            graph_diagram=result.get("graph_diagram", ""),
            final_output=result.get("final_output", ""),
            events_json=json.dumps(result.get("events", []), ensure_ascii=False),
            chunks_json=json.dumps(result.get("chunks", []), ensure_ascii=False),
        )

    @staticmethod
    def _session_to_response(session: Any) -> SessionResponse:
        """将 SessionOut DTO 转换为 proto SessionResponse。"""

        return SessionResponse(
            session_id=session.session_id,
            user_id=session.user_id,
            session_name=session.session_name or "",
            created_at=_to_iso(session.created_at),
            updated_at=_to_iso(session.updated_at),
        )


def _to_iso(value: datetime | None) -> str:
    """将 datetime 转为 ISO 8601 UTC 字符串。"""

    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
