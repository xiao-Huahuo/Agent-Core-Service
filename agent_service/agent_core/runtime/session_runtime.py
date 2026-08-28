"""AgentCore session_runtime 职责实现。

本模块由机械迁移生成，方法体保持原业务逻辑。
"""

from __future__ import annotations

import json
import logging
import queue as queue_module
import re
import threading
import time
from collections.abc import Iterator, Sequence
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.graph import AgentGraphBuilder
from agent_service.agent_core.nodes.model_decision import ModelDecisionNode
from agent_service.agent_core.runtime import AttachmentRuntime, CancellationRuntime
from agent_service.agent_core.runtime.error_recovery import extract_friendly_error
from agent_service.agent_core.runtime.shared import (
    AGENT_LOOP_AUTO,
    AGENT_LOOP_DEEP_ALIAS,
    AGENT_LOOP_MODES,
    AGENT_LOOP_PLAN,
    AGENT_LOOP_REACT,
    AGENT_LOOP_SIMPLE,
)
from agent_service.agent_core.runtime.token_usage import extract_token_usage
from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.schemas.message import MessageCreate
from agent_service.scripts.draw_agent_graph import draw_agent_graph
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.child_agent import ChildAgentContract, ChildAgentEvent, ChildAgentManager
from agent_service.services.message.service import MessageService
from agent_service.services.session_attachment.service import SessionAttachmentService
from agent_service.services.safety import SafetyService
from agent_service.services.scheduler import (
    BACKGROUND_SUMMARY_TASK,
    FOREGROUND_AGENT_TASK,
    LARGE_MODEL_TIER,
    SMALL_MODEL_TIER,
    LLMTaskScheduler,
    get_llm_task_scheduler,
)
from agent_service.tools import (
    ToolExecutor,
    ToolRegistry,
    clear_agent_token_callback,
    clear_context_mirror_callback,
    clear_context_compression_callback,
    clear_markdown_html_visualization_callback,
    clear_plan_state,
    clear_planner_content_callback,
    clear_observation_content_callback,
    clear_task_list_callback,
    clear_tool_runtime,
    clear_tool_trace_callback,
    get_plan_state,
    set_agent_token_callback,
    set_context_mirror_callback,
    set_context_compression_callback,
    set_markdown_html_visualization_callback,
    set_plan_state,
    set_planner_content_callback,
    set_observation_content_callback,
    set_task_list_callback,
    set_tool_runtime,
    set_tool_trace_callback,
    normalize_agent_access_mode,
)
from agent_service.services.task_list.service import extract_plan_state, merge_plan_state


logger = logging.getLogger(__name__)
CITATION_ANCHOR_PATTERN = re.compile(r"\[([A-Z]?\d+)\]")

class SessionRuntimeMixin:
    def _get_message_service(self) -> MessageService:
        """获取或懒加载消息服务。"""

        if self.message_service is None:
            self.message_service = MessageService(config=self.config)
        return self.message_service
    def _get_context_builder(self, *, message_service: MessageService) -> ContextBuilder:
        """获取或懒加载短期上下文构建器。"""

        if self.context_builder is None:
            self.context_builder = ContextBuilder(
                config=self.config,
                message_service=message_service,
                attachment_service=self.attachment_runtime.service,
            )
        return self.context_builder
    def _save_state_update_messages(
        self,
        *,
        message_service: MessageService,
        user_id: str,
        session_id: str,
        node_name: str,
        state_update: dict[str, Any] | None,
        turn_traces: list[dict[str, Any]] | None = None,
        citation_map: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        将图节点返回的新增消息保存为 MessageRecord。

        message_service: 消息服务。
        user_id: 用户 ID。
        session_id: 会话 ID。
        node_name: 当前节点名称。
        state_update: LangGraph 节点返回的状态更新。
        turn_traces: 本轮截至当前节点累积的所有 trace,用于附加到 assistant 消息 metadata 中。
        """

        if not state_update:
            return None
        messages = state_update.get("messages", [])
        if (not messages or node_name in {"planner", "observation", "compress"}) and turn_traces:
            message_service.create_message(
                MessageCreate(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content="",
                    metadata_json={
                        "node": node_name,
                        "source": "agent_graph_trace",
                        "trace": turn_traces,
                    },
                )
            )
            return None
        change_snapshot: dict[str, Any] | None = None
        for message in messages:
            message_create = self._message_to_create(
                message=message,
                user_id=user_id,
                session_id=session_id,
                node_name=node_name,
                turn_traces=turn_traces,
                citation_map=citation_map,
            )
            if message_create is not None:
                if (
                    self.change_service is not None
                    and node_name == "agent"
                    and message_create.role == "assistant"
                    and message_create.content.strip()
                    and not message_create.tool_calls_json
                ):
                    change_snapshot = self.change_service.finalize_run(run_id=run_id or session_id)
                    if change_snapshot is not None:
                        message_create.metadata_json["change_snapshot"] = change_snapshot
                        self._persist_session_state_value(session_id, "change_snapshot", change_snapshot)
                message_service.create_message(message_create)
        return change_snapshot
    def _load_session_plan(self, session_id: str) -> dict[str, Any] | None:
        """从 DB 加载会话的探索状态,跨轮恢复 planner 的上下文。"""

        if self.session_service is None:
            return None
        state_json = self.session_service.get_session_state(session_id)
        if not state_json:
            return None
        try:
            return extract_plan_state(json.loads(state_json))
        except (json.JSONDecodeError, TypeError):
            logger.warning("会话状态 JSON 解析失败 | session=%s", session_id)
            return None
    def _load_session_compression_state(self, session_id: str) -> dict[str, Any] | None:
        """从数据库会话状态恢复最近一次结构化上下文压缩结果。"""

        state = self._load_session_state_dict(session_id)
        value = state.get("compression_state") if state else None
        return value if isinstance(value, dict) else None
    def _load_session_state_dict(self, session_id: str) -> dict[str, Any]:
        """读取兼容旧版 plan-only JSON 的完整会话状态对象。"""

        if self.session_service is None:
            return {}
        state_json = self.session_service.get_session_state(session_id)
        if not state_json:
            return {}
        try:
            state = json.loads(state_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("会话状态 JSON 解析失败 | session=%s", session_id)
            return {}
        return state if isinstance(state, dict) else {}
    def _persist_session_state_value(self, session_id: str, key: str, value: Any) -> None:
        """原子合并一个正式会话状态字段，不覆盖 Planner、环境或子 Agent 状态。"""

        if self.session_service is None:
            return
        with self._session_state_lock:
            state = self._load_session_state_dict(session_id)
            state[key] = value
            self.session_service.update_session_state(session_id, json.dumps(state, ensure_ascii=False))
    def _persist_session_compression_state(self, session_id: str, compression_state: dict[str, Any]) -> None:
        """仅当版本不回退时持久化结构化压缩状态。"""

        current = self._load_session_compression_state(session_id) or {}
        if int(compression_state.get("version", 0) or 0) < int(current.get("version", 0) or 0):
            return
        self._persist_session_state_value(session_id, "compression_state", compression_state)
    def _persist_session_plan(self, session_id: str, plan: dict[str, Any] | None) -> None:
        """将探索状态持久化到 DB,供下一轮恢复。"""

        if self.session_service is None:
            return
        current_state = None
        state_json = self.session_service.get_session_state(session_id)
        if state_json:
            try:
                current_state = json.loads(state_json)
            except (json.JSONDecodeError, TypeError):
                current_state = None
        merged_state = merge_plan_state(current_state, plan)
        self.session_service.update_session_state(
            session_id,
            json.dumps(merged_state, ensure_ascii=False) if merged_state is not None else None,
        )
    def _load_session_state_list(self, session_id: str, key: str) -> list[dict[str, Any]]:
        """Read one serialized list from session state without breaking older plan-only sessions."""

        if self.session_service is None:
            return []
        state_json = self.session_service.get_session_state(session_id)
        if not state_json:
            return []
        try:
            state = json.loads(state_json)
        except (json.JSONDecodeError, TypeError):
            return []
        value = state.get(key) if isinstance(state, dict) else None
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    def _persist_child_agent_snapshot(self, session_id: str, child: dict[str, Any]) -> None:
        """Keep the last child-agent state available after history reloads and imports."""

        children = self._load_session_state_list(session_id, "child_agents")
        run_id = str(child.get("run_id") or "")
        children = [item for item in children if str(item.get("run_id") or "") != run_id]
        children.append(child)
        self._persist_session_state_value(session_id, "child_agents", children)
    def _persist_session_state_value(self, session_id: str, key: str, value: Any) -> None:
        """Merge an auxiliary UI snapshot while preserving planner and task-list state."""

        if self.session_service is None:
            return
        state: dict[str, Any] = {}
        state_json = self.session_service.get_session_state(session_id)
        if state_json:
            try:
                parsed = json.loads(state_json)
                if isinstance(parsed, dict):
                    state = parsed
            except (json.JSONDecodeError, TypeError):
                pass
        state[key] = value
        self.session_service.update_session_state(session_id, json.dumps(state, ensure_ascii=False))
