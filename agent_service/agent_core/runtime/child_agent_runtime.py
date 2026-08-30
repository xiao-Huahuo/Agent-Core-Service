"""AgentCore child_agent_runtime 职责实现。

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
from agent_service.services.session.service import SessionService
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

def _resolve_child_agent_category_template(category: str, prompts: AgentConfig.PromptConfig) -> str:
    """把子 Agent 类别解析为注入 prompt 的角色设定模板。

    命中预置 key 用对应模板;空类别返回空串不注入;其他自定义字符串视为角色描述。
    """

    text = (category or "").strip()
    if not text:
        return ""
    return prompts.child_agent_category_prompts.get(
        text,
        prompts.child_agent_custom_role_template.format(category=text),
    )

class ChildAgentRuntimeMixin:
    def list_child_agents(self, parent_run_id: str) -> list[dict[str, Any]]:
        """返回指定父 Agent 的子 Agent 状态快照。"""

        return [self._child_record_to_dict(record) for record in self.child_agent_manager.list_children(parent_run_id)]
    def list_child_agents_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """返回指定会话内主 Agent 创建的全部子 Agent,供前端面板查询。"""

        records = self.child_agent_manager.list_children_for_session(session_id)
        active_children = [self._child_record_to_dict(record) for record in records]
        saved_children = self._load_session_state_list(session_id, "child_agents")
        # Live records win so the panel never renders a stale terminal status while a child is running.
        children_by_run_id = {
            str(child.get("run_id") or ""): self._with_child_conversation_session(session_id, child)
            for child in saved_children
        }
        children_by_run_id.update({child["run_id"]: child for child in active_children})
        return list(children_by_run_id.values())
    def stop_child_agent(self, run_id: str) -> bool:
        """向指定子 Agent 发送停止信号。"""

        return self.child_agent_manager.stop(run_id)
    def update_child_agent(self, run_id: str, update: dict[str, Any]) -> None:
        """向指定子 Agent 下一次安全检查点投递上下文更新。"""

        self.child_agent_manager.update_context(run_id, update)
    @staticmethod
    def _child_record_to_dict(record: Any) -> dict[str, Any]:
        """将子 Agent 记录转为 REST/gRPC/前端共用的普通字典。"""

        result = record.result
        return {
            "run_id": record.run_id,
            "conversation_session_id": SessionService.child_agent_session_id(
                record.contract.session_id,
                record.run_id,
            ),
            "parent_run_id": record.contract.parent_run_id,
            "goal": record.contract.goal,
            "category": record.contract.category,
            "name": record.contract.name,
            "mode": record.contract.mode,
            "status": record.status.value,
            "access_mode": record.effective_access_mode,
            "allowed_tools": sorted(record.effective_tools),
            "result": result.result if result is not None else None,
            "summary": result.summary if result is not None else "",
            "error": result.error if result is not None else None,
        }
    @staticmethod
    def _with_child_conversation_session(session_id: str, child: dict[str, Any]) -> dict[str, Any]:
        """补全旧快照缺失的正式子对话 Session ID。"""

        run_id = str(child.get("run_id") or "")
        if not run_id:
            return child
        return {
            **child,
            "conversation_session_id": SessionService.child_agent_session_id(session_id, run_id),
        }
    def _child_event_to_payload(self, event: ChildAgentEvent) -> dict[str, Any] | None:
        """将子 Agent 生命周期事件转换为前端可展示的 SSE payload。"""

        return {
            "type": "child_agent_event",
            "node": "child_agent",
            "content": self._child_event_content(event),
            "tool_calls": [],
            "trace": [],
            "model_name": "",
            "metadata": {
                "child_agent_event": {
                    "event_name": event.event_name,
                    "created_at": event.created_at,
                    "child": {
                        "run_id": event.run_id,
                        "parent_run_id": event.parent_run_id,
                        "goal": event.goal,
                        "category": event.category,
                        "name": event.name,
                        "mode": event.mode,
                        "status": event.status.value,
                        "access_mode": event.access_mode,
                        "allowed_tools": list(event.allowed_tools),
                        "result": event.result,
                        "summary": event.summary,
                        "error": event.error,
                    },
                },
            },
        }
    @staticmethod
    def _child_event_content(event: ChildAgentEvent) -> str:
        """生成子 Agent 事件的历史上下文正文。"""

        status_label = {
            "created": "已创建",
            "running": "开始任务",
            "completed": "完成任务",
            "failed": "任务失败",
            "stopped": "已停止",
        }.get(event.status.value, event.status.value)
        parts = [
            f"子 Agent {event.name or event.run_id} {status_label}: {event.goal}",
            f"类别={event.category or '通用'}",
            f"模式={event.mode}",
            f"权限={event.access_mode}",
            f"工具数={len(event.allowed_tools)}",
        ]
        if event.summary:
            parts.append(f"摘要={event.summary}")
        if event.error:
            parts.append(f"错误={event.error}")
        return " | ".join(parts)
    def _drain_child_agent_event_payloads(
        self,
        *,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """读取当前会话的子 Agent 事件队列,转为 SSE payload 列表。

        事件落库已由 `_on_child_agent_event` 回调负责,此处只负责主 Agent 流内推送,
        避免与回调重复入库。
        """

        payloads: list[dict[str, Any]] = []
        for event in self.child_agent_manager.drain_events_for_session(session_id):
            payload = self._child_event_to_payload(event)
            if payload is not None:
                payloads.append(payload)
        return payloads
    def _on_child_agent_event(self, event_name: str, record: Any) -> None:
        """ChildAgentManager 事件回调:子 Agent 每次状态变化立即落库。

        此回调在子 Agent 执行线程中同步调用,保证主 Agent SSE 流结束后后台子 Agent
        的完成事件也能持久化,前端刷新历史或轮询即可看到"已完成"提醒。
        """

        try:
            payload = self._record_to_payload(event_name, record)
            self._persist_child_agent_snapshot(record.contract.session_id, self._child_record_to_dict(record))
            self._save_child_agent_event_message(
                message_service=self._get_message_service(),
                user_id=record.contract.user_id,
                session_id=record.contract.session_id,
                payload=payload,
            )
        except Exception:
            logger.exception(
                "子 Agent 事件落库失败 | event=%s run=%s", event_name, getattr(record, "run_id", "?")
            )
    @staticmethod
    def _record_to_payload(event_name: str, record: Any) -> dict[str, Any]:
        """从子 Agent 运行记录构造与 SSE payload 一致的 dict,供事件回调落库使用。"""

        result = record.result
        status_value = record.status.value if hasattr(record.status, "value") else str(record.status)
        status_label = {
            "created": "已创建",
            "running": "开始任务",
            "completed": "完成任务",
            "failed": "任务失败",
            "stopped": "已停止",
        }.get(status_value, status_value)
        parts = [
            f"子 Agent {record.contract.name or record.run_id} {status_label}: {record.contract.goal}",
            f"类别={record.contract.category or '通用'}",
            f"模式={record.contract.mode}",
            f"权限={record.effective_access_mode}",
            f"工具数={len(record.effective_tools)}",
        ]
        if result is not None and result.summary:
            parts.append(f"摘要={result.summary}")
        if result is not None and result.error:
            parts.append(f"错误={result.error}")
        return {
            "type": "child_agent_event",
            "node": "child_agent",
            "content": " | ".join(parts),
            "tool_calls": [],
            "trace": [],
            "model_name": "",
            "metadata": {
                "child_agent_event": {
                    "event_name": event_name,
                    "created_at": time.time(),
                    "child": {
                        "run_id": record.run_id,
                        "parent_run_id": record.contract.parent_run_id,
                        "goal": record.contract.goal,
                        "category": record.contract.category,
                        "name": record.contract.name,
                        "mode": record.contract.mode,
                        "status": status_value,
                        "access_mode": record.effective_access_mode,
                        "allowed_tools": sorted(record.effective_tools),
                        "result": result.result if result is not None else None,
                        "summary": result.summary if result is not None else "",
                        "error": result.error if result is not None else None,
                    },
                },
            },
        }
    @staticmethod
    def _save_child_agent_event_message(
        *,
        message_service: MessageService | None,
        user_id: str,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        """把子 Agent SSE 事件保存为可历史加载和导入导出的会话消息。"""

        if message_service is None:
            return
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata = {
            **metadata,
            "node": "child_agent",
            "source": "child_agent_event",
        }
        message_service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=str(payload.get("content") or ""),
                metadata_json=metadata,
            )
        )
    def _spawn_child_from_runtime(
        self,
        *,
        parent_run_id: str,
        user_id: str,
        session_id: str,
        parent_access_mode: str,
        goal: str,
        mode: str = "background",
        allowed_tools: list[str] | None = None,
        access_mode: str = "sandbox",
        input_refs: list[str] | None = None,
        output_contract: dict[str, Any] | None = None,
        category: str | None = None,
        name: str | None = None,
    ) -> str:
        """由当前主 Agent 工具上下文创建真实子 Agent并返回 JSON 摘要。

        category: 子 Agent 能力模板 key(agent/explore/plan)或自定义角色描述,可留空。
        name: 子 Agent 名字;留空时按同类别的已有数量自动生成(plan1/agent1/...)。
        """

        effective_name = (name or "").strip() or self._auto_child_agent_name(parent_run_id, category)
        parent_tools = frozenset(
            definition.name
            for definition in (self.tool_registry.definitions.values() if self.tool_registry else [])
            if definition.name not in {"spawn_child_agent", "wait_for_child_agents"}
        )
        contract = ChildAgentContract(
            goal=goal,
            parent_run_id=parent_run_id,
            user_id=user_id,
            session_id=session_id,
            mode=mode,
            allowed_tools=frozenset(allowed_tools) if allowed_tools is not None else None,
            access_mode=access_mode,
            input_refs=tuple(input_refs or []),
            output_contract=output_contract or {},
            category=category or "",
            name=effective_name,
        )

        def execute_child(context: Any) -> str:
            """在独立线程中执行一轮无状态 Agent,禁止继续召唤子 Agent。

            类别模板作为角色设定注入 prompt 前,让子 Agent 一进入就知道自己是谁。
            """

            context.raise_if_stopped()
            template = _resolve_child_agent_category_template(context.category, self.config.prompts)
            prompt = f"{template}\n\n{context.goal}" if template else context.goal
            if self.session_service is None:
                result = self.run_once(
                    prompt=prompt,
                    user_id=context.user_id,
                    session_id=SessionService.child_agent_session_id(context.session_id, context.run_id),
                    agent_mode=context.agent_mode,
                    agent_access_mode=context.access_mode,
                    allow_child_spawn=False,
                )
                context.raise_if_stopped()
                return str(result.get("final_output") or "")
            child_session = self.session_service.create_child_agent_session(
                user_id=context.user_id,
                parent_session_id=context.session_id,
                run_id=context.run_id,
                session_name=context.name or context.goal,
            )
            result = self.run_session_prompt(
                prompt=prompt,
                user_id=context.user_id,
                session_id=child_session.session_id,
                agent_mode=context.agent_mode,
                agent_access_mode=context.access_mode,
                allow_child_spawn=False,
            )
            context.raise_if_stopped()
            return str(result.get("final_output") or "")

        record = self.child_agent_manager.spawn(
            contract=contract,
            executor=execute_child,
            parent_tools=parent_tools,
            parent_access_mode=parent_access_mode,
        )
        return json.dumps(self._child_record_to_dict(record), ensure_ascii=False)
    def _auto_child_agent_name(self, parent_run_id: str, category: str | None) -> str:
        """按同类别的已有子 Agent 数量生成递增默认名(plan1/agent1/...)。"""

        base = (category or "").strip() or "child"
        siblings = self.child_agent_manager.list_children(parent_run_id)
        same_category = sum(1 for record in siblings if record.contract.category == (category or ""))
        return f"{base}{same_category + 1}"
    def _wait_child_agents_from_runtime(
        self,
        *,
        parent_run_id: str,
        run_ids: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """由当前主 Agent 工具上下文等待一个后台子 Agent 结果并返回 JSON。"""

        result = self.child_agent_manager.wait_for_children(
            parent_run_id=parent_run_id,
            run_ids=run_ids or [],
            timeout_seconds=(
                self.config.limits.agent_child_wait_timeout_seconds
                if timeout_seconds is None
                else timeout_seconds
            ),
        )
        records = self.child_agent_manager.list_children(parent_run_id)
        if run_ids:
            target_run_ids = set(run_ids)
            records = [record for record in records if record.run_id in target_run_ids]
        return json.dumps(
            {
                "result": (
                    {
                        "run_id": result.run_id,
                        "parent_run_id": result.parent_run_id,
                        "status": result.status.value,
                        "summary": result.summary,
                        "result": result.result,
                        "error": result.error,
                    }
                    if result is not None
                    else None
                ),
                "children": [self._child_record_to_dict(record) for record in records],
            },
            ensure_ascii=False,
        )
