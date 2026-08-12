"""
Session 管理端点。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import json

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session as DBSession, select

from agent_service.api.rest.deps import _require_message_service, _require_session_service
from agent_service.models.message import MessageRecord
from agent_service.models.session import SessionRecord
from agent_service.schemas.message import MessageCreate
from agent_service.schemas.session import SessionCreate, SessionUpdate

router = APIRouter()


@router.get("/sessions")
async def list_sessions(user_id: str = Query(..., min_length=1, description="用户 ID")) -> list[dict[str, Any]]:
    """列出指定用户的所有会话,按更新时间倒序。"""
    service = _require_session_service()
    sessions = service.list_user_sessions(user_id)
    return [
        {
            "session_id": s.session_id,
            "user_id": s.user_id,
            "session_name": s.session_name,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.post("/sessions")
async def create_session(body: dict[str, Any]) -> dict[str, Any]:
    """创建新会话。body: user_id (必填), session_name (可选)。"""
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    session_name = body.get("session_name")
    service = _require_session_service()
    session = service.create_session(SessionCreate(user_id=str(user_id), session_name=session_name))
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.post("/sessions/import")
async def import_session(body: dict[str, Any]) -> dict[str, Any]:
    """导入结构化 JSON 格式的会话。"""
    return _do_import(body)


@router.post("/sessions/import-file")
async def import_session_file(body: dict[str, Any]) -> dict[str, Any]:
    """导入 YAML/JSON 文件内容。

    body:
      user_id (必填): 目标用户
      content (必填): YAML 或 JSON 格式的原始文本
      session_name (可选): 导入后的会话名

    content 格式应与 /sessions/export 导出的 YAML 结构一致:
      session: { id, name, user_id, created_at, updated_at }
      messages: [{ role, content, created_at, node, tool_calls, trace_details, ... }]
    或者顶层直接包含 messages 数组:
      messages: [...]
    """
    import yaml

    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    content = body.get("content")
    if not content:
        raise HTTPException(status_code=422, detail="content is required")

    try:
        parsed = yaml.safe_load(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"无法解析 YAML/JSON 内容: {exc}")

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="content 必须解析为对象")

    # 兼容两种结构: 顶层 { session, messages } 或纯 { messages }
    if "messages" in parsed:
        data = parsed
    else:
        raise HTTPException(status_code=422, detail="缺少 messages 字段")

    # 构造导入 body
    import_body: dict[str, Any] = {
        "user_id": str(user_id),
        "session_name": body.get("session_name") or (parsed.get("session", {}).get("name") if isinstance(parsed.get("session"), dict) else None),
        "messages": data.get("messages", []),
    }
    task_list = parsed.get("task_list")
    if task_list and isinstance(task_list, dict):
        import_body["task_list"] = task_list
    session_state = parsed.get("session_state")
    if isinstance(session_state, dict):
        import_body["session_state"] = session_state
    child_agents = parsed.get("child_agents")
    if isinstance(child_agents, list):
        import_body["child_agents"] = child_agents

    return _do_import(import_body)


def _do_import(body: dict[str, Any]) -> dict[str, Any]:
    """导入外部 YAML/JSON 格式的会话。

    body 格式:
      user_id (必填): 导入到哪个用户下
      session_name (可选): 导入后显示的名称
      messages (必填): 消息列表,每项包含:
        - role (必填): user/assistant/tool/system
        - content (必填): 消息正文
        - created_at (可选): ISO 格式时间,默认当前时间
        - node (可选): 图节点名,写入 metadata.node
        - reference (可选): 用户引用,写入 metadata.reference
        - tool_calls (可选): 工具调用列表
        - trace_details (可选): trace 事件列表,写入 metadata.trace
        - child_agent_event (可选): 子 Agent 生命周期事件,写入 metadata.child_agent_event
    """
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(status_code=422, detail="messages is required and must be a list")

    # 1. 创建新会话
    session_service = _require_session_service()
    session_name = body.get("session_name")
    session = session_service.create_session(SessionCreate(user_id=str(user_id), session_name=session_name))
    session_id = session.session_id
    now = datetime.now(timezone.utc)

    # 2. 导入消息
    message_service = _require_message_service()
    engine = message_service.engine

    imported_count = 0
    with DBSession(engine) as db_session:
        for raw in messages:
            if not isinstance(raw, dict):
                continue
            role = raw.get("role", "")
            if not role:
                continue
            content = raw.get("content", "") or ""
            created_at_str = raw.get("created_at")
            msg_created_at = _parse_iso_time(created_at_str) if created_at_str else now

            metadata = dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), dict) else {}
            _rebind_imported_change_snapshots(metadata, session_id)
            node = raw.get("node")
            if node:
                metadata["node"] = node
            reference = raw.get("reference")
            if reference:
                metadata["reference"] = reference
            trace_details = raw.get("trace_details")
            if trace_details and isinstance(trace_details, list):
                metadata["trace"] = trace_details
            child_agent_event = raw.get("child_agent_event")
            if child_agent_event and isinstance(child_agent_event, dict):
                metadata["child_agent_event"] = child_agent_event

            tool_calls = raw.get("tool_calls")
            if not tool_calls or not isinstance(tool_calls, list):
                tool_calls = []

            tool_call_id = raw.get("tool_call_id")

            record = MessageRecord(
                message_id=message_service.generate_message_id(),
                session_id=session_id,
                user_id=str(user_id),
                role=role,
                content=content,
                tool_call_id=tool_call_id,
                tool_calls_json=tool_calls,
                metadata_json=metadata,
                created_at=msg_created_at,
            )
            db_session.add(record)
            imported_count += 1

        # 更新会话的 updated_at 为最新消息时间
        if imported_count > 0:
            db_session.commit()
            # 找到消息中的最晚时间
            latest = db_session.exec(
                select(MessageRecord.created_at)
                .where(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.created_at.desc())
                .limit(1)
            ).first()
            if latest:
                sess = db_session.get(SessionRecord, session_id)
                if sess:
                    sess.updated_at = latest
                    db_session.add(sess)
            db_session.commit()

    # 3. Restore execution/UI snapshots and bind imported records to the new session id.
    state = _restore_session_state(
        raw_state=body.get("session_state"),
        task_list=body.get("task_list"),
        child_agents=body.get("child_agents"),
        session_id=session_id,
    )
    if state:
        session_service.update_session_state(session_id, json.dumps(state, ensure_ascii=False))

    return {
        "session_id": session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "imported_count": imported_count,
    }


def _parse_iso_time(value: str) -> datetime:
    """尝试解析 ISO 格式时间字符串,失败时返回当前 UTC 时间。"""
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _restore_session_state(
    *, raw_state: Any, task_list: Any, child_agents: Any, session_id: str,
) -> dict[str, Any]:
    """Restore portable session state without retaining IDs from the source workspace."""

    state = dict(raw_state) if isinstance(raw_state, dict) else {}
    restored_task_list = task_list if isinstance(task_list, dict) else state.get("task_list")
    if isinstance(restored_task_list, dict):
        state["task_list"] = {**restored_task_list, "session_id": session_id}
    snapshot = state.get("change_snapshot")
    if isinstance(snapshot, dict):
        state["change_snapshot"] = {**snapshot, "session_id": session_id, "is_imported": True}
    children = child_agents if isinstance(child_agents, list) else state.get("child_agents")
    if isinstance(children, list):
        state["child_agents"] = [child for child in children if isinstance(child, dict)]
    return state


def _rebind_imported_change_snapshots(metadata: dict[str, Any], session_id: str) -> None:
    """Keep imported diffs viewable while preventing undo against the source workspace."""

    snapshot = metadata.get("change_snapshot")
    if isinstance(snapshot, dict):
        metadata["change_snapshot"] = {**snapshot, "session_id": session_id, "is_imported": True}
    trace = metadata.get("trace")
    if isinstance(trace, list):
        for item in trace:
            if not isinstance(item, dict) or not isinstance(item.get("change_snapshot"), dict):
                continue
            item["change_snapshot"] = {
                **item["change_snapshot"],
                "session_id": session_id,
                "is_imported": True,
            }


@router.get("/sessions/{session_id}/state")
async def get_session_state(session_id: str) -> dict[str, Any]:
    """Return portable session execution state for history and export consumers."""

    raw_state = _require_session_service().get_session_state(session_id)
    if not raw_state:
        return {"session_state": None}
    try:
        state = json.loads(raw_state)
    except (json.JSONDecodeError, TypeError):
        state = None
    return {"session_state": state if isinstance(state, dict) else None}


@router.put("/sessions/{session_id}/state")
async def update_session_environment(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Persist the Git environment snapshot shown with a session's changes."""

    environment = body.get("environment")
    if not isinstance(environment, dict):
        raise HTTPException(status_code=422, detail="environment is required")
    service = _require_session_service()
    raw_state = service.get_session_state(session_id)
    try:
        state = json.loads(raw_state) if raw_state else {}
    except (json.JSONDecodeError, TypeError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    state["environment"] = environment
    if not service.update_session_state(session_id, json.dumps(state, ensure_ascii=False)):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_state": state}


@router.get("/sessions/messages/history")
@router.get("/sessions/observability/history")
async def list_user_message_history(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=1000,
        description="最近用户 message 轮次数量;不传则返回全部历史",
    ),
) -> list[dict[str, Any]]:
    """获取用户跨全部 session 的观测消息历史,支持按最近轮次懒加载。"""

    message_service = _require_message_service()
    messages = message_service.list_user_observability_messages(
        user_id=user_id,
        turn_limit=limit,
    )
    return [
        {
            "message_id": message.message_id,
            "session_id": message.session_id,
            "user_id": message.user_id,
            "role": message.role,
            "content": message.content if message.role in {"user", "assistant"} else "",
            "tool_calls": message_service.compact_observability_tool_calls(message.tool_calls_json),
            "metadata": message_service.compact_observability_metadata(message.metadata_json),
            "created_at": message.created_at.isoformat(),
        }
        for message in messages
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取指定会话详情。"""
    service = _require_session_service()
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """删除指定会话。"""
    service = _require_session_service()
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "deleted_count": 1}


@router.delete("/sessions")
async def clear_all_sessions(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """清空指定用户的所有会话。"""
    service = _require_session_service()
    count = service.delete_all_user_sessions(user_id)
    return {"ok": True, "deleted_count": count}


@router.post("/sessions/prune")
async def delete_empty_sessions(body: dict[str, Any]) -> dict[str, Any]:
    """删除指定用户的所有空会话(无消息)。body: user_id。"""
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    service = _require_session_service()
    count = service.prune_empty_sessions(str(user_id))
    return {"ok": True, "pruned_count": count}


@router.put("/sessions/{session_id}/name")
async def update_session_name(session_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """更新会话显示名称。body: session_name 字段。"""
    session_name = body.get("session_name")
    if not session_name:
        raise HTTPException(status_code=422, detail="session_name is required")
    service = _require_session_service()
    session = service.update_session_name(session_id, SessionUpdate(session_name=str(session_name)))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "session_name": session.session_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    limit: int | None = Query(default=None, ge=1, description="可选消息数量上限，默认返回完整历史"),
) -> list[dict[str, Any]]:
    """获取指定会话的消息历史。"""
    ms = _require_message_service()
    messages = ms.list_session_messages(user_id=user_id, session_id=session_id, limit=limit)
    return [
        {
            "message_id": m.message_id,
            "session_id": m.session_id,
            "user_id": m.user_id,
            "role": m.role,
            "content": m.content,
            "tool_call_id": m.tool_call_id,
            "tool_calls": m.tool_calls_json,
            "metadata": m.metadata_json,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
