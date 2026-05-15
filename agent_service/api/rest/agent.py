"""
Agent 流式对话与观测端点。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from fastapi import APIRouter, Body, Query
from fastapi.responses import StreamingResponse

from agent_service.api.rest.deps import _require_agent, _require_message_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_sse(events: Iterator[dict[str, Any]]) -> Iterator[str]:
    """将 dict 事件迭代器包装为 SSE 格式字符串,客户端断开时传播取消信号。"""
    try:
        for payload in events:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    except GeneratorExit:
        try:
            events.close()
        except GeneratorExit:
            pass
        raise


# ------------------------------------------------------------------
# 流式对话
# ------------------------------------------------------------------


@router.get("/agent/stream")
async def agent_stream(
    prompt: str = Query(..., min_length=1, description="用户输入"),
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    session_id: str = Query(..., min_length=1, description="会话 ID"),
) -> StreamingResponse:
    """
    SSE 流式对话接口(带 session 上下文)。

    事件流格式: data: <json>\\n\\n, 以 data: [DONE]\\n\\n 结束。
    """
    agent = _require_agent()

    def _event_generator():
        try:
            yield from _to_sse(
                agent.stream_session_prompt(
                    prompt=prompt,
                    user_id=user_id,
                    session_id=session_id,
                )
            )
        except Exception:
            logger.exception("SSE 流式对话异常 | user=%s session=%s", user_id, session_id)
            yield f"data: {json.dumps({'error': 'internal server error'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/agent/stream-run")
async def agent_stream_run(
    prompt: str = Query(..., min_length=1, description="用户输入"),
    user_id: str = Query(default="stream-run-user", description="用户 ID"),
    session_id: str = Query(default="stream-run-session", description="会话 ID"),
) -> StreamingResponse:
    """
    无状态 SSE 流式对话(无上下文,无持久化)。
    """
    agent = _require_agent()

    def _event_generator():
        try:
            yield from _to_sse(
                agent.stream_run(
                    prompt=prompt,
                    user_id=user_id,
                    session_id=session_id,
                )
            )
        except Exception:
            logger.exception("SSE 无状态流式异常 | user=%s session=%s", user_id, session_id)
            yield f"data: {json.dumps({'error': 'internal server error'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ------------------------------------------------------------------
# 非流式调用
# ------------------------------------------------------------------


@router.post("/agent/run")
async def agent_run_session(
    prompt: str = Body(..., embed=True),
    user_id: str = Body(..., embed=True),
    session_id: str = Body(..., embed=True),
) -> dict[str, Any]:
    """
    带 session 上下文的非流式调用,返回完整结构化结果。
    """
    agent = _require_agent()
    return agent.run_session_prompt(prompt=prompt, user_id=user_id, session_id=session_id)


# ------------------------------------------------------------------
# 观测 / trace 事件
# ------------------------------------------------------------------


@router.get("/agent/events")
async def agent_events(
    session_id: str = Query(..., min_length=1, description="会话 ID"),
    user_id: str = Query(..., min_length=1, description="用户 ID"),
) -> dict[str, Any]:
    """
    获取指定会话的最新执行 trace 事件,供前端观测面板使用。

    从消息表中提取带有 node 信息的 metadata_json,按时间序排列。
    """
    ms = _require_message_service()
    messages = ms.list_session_messages(user_id=user_id, session_id=session_id, limit=200)

    events: list[dict[str, Any]] = []
    for m in messages:
        meta = m.metadata_json or {}
        node_name = meta.get("node", "")
        if not node_name:
            continue
        event = {
            "message_id": m.message_id,
            "role": m.role,
            "node": node_name,
            "content": m.content[:500] if m.role in ("assistant", "tool", "system") else "",
            "tool_calls": m.tool_calls_json,
            "created_at": m.created_at.isoformat(),
            "metadata": meta,
        }
        events.append(event)

    return {
        "session_id": session_id,
        "user_id": user_id,
        "event_count": len(events),
        "events": events,
    }
