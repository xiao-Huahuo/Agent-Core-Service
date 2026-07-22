"""
推理规划节点（策略顾问模式）。

功能说明:
本文件只实现 `PlannerNode` 一个节点。该节点在 Agent 做出决策前,用大模型分析
当前探索进度和已获取的信息,给出下一步策略建议,而不是生成固定步骤清单。
后续 ModelDecisionNode 会将建议注入到系统提示词中供 agent 参考,
但 agent 保留完全自主的决策权。

使用说明:
`graph.py` 会把本节点注册为 `planner` 节点,放在 `compress` 与 `agent` 之间。
节点支持重入:首次调用给出初步探索方向,后续调用根据执行历史更新策略建议。
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent_service.agent_core.nodes.base import AgentState
from agent_service.agent_core.nodes.model_decision import extract_token_usage, get_user_llm_overrides
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import (
    FOREGROUND_AGENT_TASK,
    SMALL_MODEL_TIER,
    LLMTaskScheduler,
    get_llm_task_scheduler,
)
from agent_service.tools import ToolExecutor
from agent_service.tools.runtime_context import get_tool_trace_callback




PLANNER_SYSTEM_PROMPT = (
    "你是一个多步骤任务规划器。根据用户问题、已有计划、工具结果和 observation 决策历史更新探索状态。\n"
    "输出格式（只输出 JSON，不要其他文字）：\n"
    '{"covered":["已覆盖方向"],"suggested":["建议方向"],"sub_questions":["待解决子问题"],"current_index":0,"status":"planning|running|ready_to_answer","sufficient":false,"hint":"给 agent 的一两句策略建议"}\n'
    "字段说明:\n"
    "- covered: 目前已覆盖了哪些子话题/方向(可为空数组)\n"
    "- suggested: 建议 agent 下一步探索的方向(可为空数组)\n"
    "- sub_questions: 为用户问题拆出的有序子问题,最多5个,已完成的也保留在列表里\n"
    "- current_index: 当前最应该处理的子问题下标,从0开始\n"
    "- status: planning 初始规划,running 正在探索,ready_to_answer 信息足够可回答\n"
    "- sufficient: 当前信息是否已经足够回答用户问题\n"
    "- hint: 给 agent 的具体下一步建议,必须引用 current_index 对应子问题,不要超过80字"
)


class PlannerNode:
    """
    策略顾问节点。

    不生成固定步骤清单,而是分析当前探索进度并给出策略建议。
    Agent 读取建议后自主决定下一步操作。

    config: 全局配置对象。
    task_scheduler: 可选 LLM 任务调度器,为空时自动创建。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        task_scheduler: LLMTaskScheduler | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        """保存配置和调度器。"""

        self.config = config
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.tool_executor = tool_executor

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """
        分析当前探索进度，给出策略建议。

        首次调用：给出初步探索方向。
        重入调用：根据执行历史分析已覆盖的主题，建议下一步方向。

        state: 当前 LangGraph 状态。
        """

        original_prompt = self._extract_latest_user_message(state)
        if not original_prompt:
            return {
                "messages": [AIMessage(content="未找到用户消息，跳过策略分析。")],
                "trace": [{
                "node": "planner",
                "event": "no_user_message",
                "human_readable": "未找到用户消息，跳过策略分析。",
                "chat_visible": False,
            }],
            }

        existing_plan = state.get("plan")
        system_message = SystemMessage(content=PLANNER_SYSTEM_PROMPT)
        user_content = self._build_planning_prompt(original_prompt, existing_plan, state)
        user_message = SystemMessage(content=user_content)
        trace_callback = get_tool_trace_callback()
        if trace_callback is not None:
            trace_callback({
                "node": "planner",
                "event": "planner_request_start",
                "human_readable": "正在更新探索策略。",
                "chat_visible": False,
            })
        response = self._call_llm(system_message, user_message, state)
        token_usage = extract_token_usage(response)
        plan = self._parse_plan(response.content)
        if plan is not None:
            event = "strategy_updated" if existing_plan else "strategy_generated"
            hint = plan.get("hint", "")
            readable = hint or "策略分析完成。"
            trace = {
                "node": "planner",
                "event": event,
                "covered": plan.get("covered", []),
                "suggested": plan.get("suggested", []),
                "sub_questions": plan.get("sub_questions", []),
                "current_index": plan.get("current_index", 0),
                "status": plan.get("status", "running"),
                "sufficient": plan.get("sufficient", False),
                "token_usage": token_usage,
                "human_readable": readable,
                "chat_visible": False,
            }
            return {"messages": [AIMessage(content=readable)], "plan": plan, "trace": [trace]}

        return {
            "messages": [AIMessage(content="策略分析未产出有效结果，直接进入决策。")],
            "plan": {"covered": [], "suggested": [], "sufficient": False, "hint": ""},
            "trace": [{
                "node": "planner",
                "event": "no_plan_needed",
                "token_usage": token_usage,
                "human_readable": "策略分析未产出有效结果，直接进入决策。",
                "chat_visible": False,
            }],
        }

    def _call_llm(self, system_message: Any, user_message: Any, state: AgentState) -> Any:
        """调用 LLM 获取策略建议。

        Planner 输出是简短 JSON,不需要流式推送;始终使用 invoke_chat 避免
        前端看到逐 token 拼接的原始 JSON。
        """

        api_key, base_url, model_name, small_api_key, small_base_url, small_model_name = get_user_llm_overrides(state)
        return self.task_scheduler.invoke_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, user_message],
            model_tier=SMALL_MODEL_TIER,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            small_api_key=small_api_key,
            small_base_url=small_base_url,
            small_model_name=small_model_name,
        )

    def _build_planning_prompt(
        self, query: str, existing_plan: dict[str, Any] | None, state: AgentState
    ) -> str:
        """
        构建发给策略顾问 LLM 的 prompt。

        query: 原始用户问题。
        existing_plan: 当前探索状态,为 None 表示首次分析。
        state: 当前 AgentState,用于提取执行历史。
        """

        if existing_plan is None:
            return f"用户需求:\n{query}\n\n请拆解这个需求的关键子问题,给出当前最应该处理的一步。输出 JSON。"

        # 重入: 附带当前覆盖状态和执行历史
        parts: list[str] = [f"用户需求:\n{query}"]
        covered = existing_plan.get("covered", [])
        if covered:
            parts.append(f"\n当前已覆盖的主题: {', '.join(covered)}")
        history = self._build_execution_history(state, limit=6)
        if history:
            parts.append(f"\n最近探索结果:\n{history}")
        observation_history = self._build_observation_history(state, limit=6)
        if observation_history:
            parts.append(f"\nObservation 决策历史:\n{observation_history}")
        parts.append("\n请根据以上信息更新 sub_questions/current_index/status,判断是否已经足够回答用户问题。输出 JSON。")
        return "\n".join(parts)

    def _build_execution_history(self, state: AgentState, limit: int = 6) -> str:
        """
        从状态消息中提取最近的工具调用摘要。

        state: 当前 AgentState。
        limit: 最多提取的消息对数。
        """

        messages = state.get("messages", [])
        if not messages:
            return ""
        lines: list[str] = []
        count = 0
        for msg in reversed(messages):
            if count >= limit:
                break
            if isinstance(msg, ToolMessage):
                content = str(getattr(msg, "content", "") or "")
                name = getattr(msg, "name", "") or ""
                display = self._lookup_display_name(name) if name else ""
                label = f"{display}: " if display else ""
                lines.append(f"- {label}{content[:200]}{'...' if len(content) > 200 else ''}")
                count += 1
            elif isinstance(msg, AIMessage):
                tool_calls = getattr(msg, "tool_calls", []) or []
                if tool_calls:
                    names = ", ".join(
                        self._lookup_display_name(tc.get("name", ""))
                        for tc in tool_calls if tc.get("name")
                    )
                    if names:
                        lines.append(f"- [调用工具] {names}")
                        count += 1
        lines.reverse()
        return "\n".join(lines)

    @staticmethod
    def _build_observation_history(state: AgentState, limit: int = 6) -> str:
        """从 trace 中提取 observation 的选择历史。"""

        traces = state.get("trace", []) or []
        lines: list[str] = []
        for trace in traces:
            if trace.get("node") != "observation":
                continue
            decision = trace.get("decision", "")
            reason = trace.get("reason") or trace.get("human_readable") or ""
            next_action = trace.get("next_action", "")
            lines.append(f"- {decision}: {reason}；下一步: {next_action}")
        return "\n".join(lines[-limit:])

    @staticmethod
    def _extract_latest_user_message(state: AgentState) -> str:
        """从消息列表中提取最后一条用户消息。"""

        for message in reversed(state["messages"]):
            content = getattr(message, "content", None)
            if content and getattr(message, "type", None) == "human":
                return content if isinstance(content, str) else str(content)
        return ""

    def _lookup_display_name(self, tool_name: str) -> str:
        """从工具执行器的注册表中查找工具的 display_name，找不到则回退到 tool_name。"""
        if self.tool_executor is not None:
            definition = self.tool_executor.registry.get(tool_name)
            if definition is not None and definition.display_name:
                return definition.display_name
        return tool_name

    @staticmethod
    def _parse_plan(raw_content: str | None) -> dict[str, Any] | None:
        """从模型响应中解析 JSON 计划。"""

        if not raw_content:
            return None
        content = raw_content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        if content.startswith("{") and content.endswith("}"):
            try:
                data = json.loads(content)
                covered = data.get("covered", [])
                suggested = data.get("suggested", [])
                sub_questions = data.get("sub_questions", [])
                if not isinstance(covered, list):
                    covered = []
                if not isinstance(suggested, list):
                    suggested = []
                if not isinstance(sub_questions, list):
                    sub_questions = []
                current_index = data.get("current_index", 0)
                try:
                    current_index = int(current_index)
                except (TypeError, ValueError):
                    current_index = 0
                if sub_questions:
                    current_index = max(0, min(current_index, len(sub_questions) - 1))
                status = str(data.get("status", "running") or "running")
                if status not in {"planning", "running", "ready_to_answer"}:
                    status = "running"
                sufficient = bool(data.get("sufficient", status == "ready_to_answer"))
                if sufficient:
                    status = "ready_to_answer"
                return {
                    "covered": [str(item) for item in covered[:8]],
                    "suggested": [str(item) for item in suggested[:8]],
                    "sub_questions": [str(item) for item in sub_questions[:5]],
                    "current_index": current_index,
                    "status": status,
                    "sufficient": sufficient,
                    "hint": str(data.get("hint", "") or "")[:120],
                }
            except json.JSONDecodeError:
                return None
        return None
