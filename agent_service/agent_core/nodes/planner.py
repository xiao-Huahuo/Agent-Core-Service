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
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK, LLMTaskScheduler, get_llm_task_scheduler




PLANNER_SYSTEM_PROMPT = (
    "你是一个知识探索策略顾问。根据用户问题和当前已获取的信息，分析探索进度并给出建议。\n"
    "输出格式（只输出 JSON，不要其他文字）：\n"
    '{"covered": ["已覆盖的主题或方向"], "suggested": ["建议继续深挖的方向"], "sufficient": false, "hint": "给 agent 的一两句策略建议"}\n'
    "字段说明:\n"
    "- covered: 目前已覆盖了哪些子话题/方向(可为空数组)\n"
    "- suggested: 建议 agent 下一步探索的方向(可为空数组)\n"
    "- sufficient: 当前信息是否已经足够回答用户问题\n"
    "- hint: 给 agent 的简短策略建议,一两句话即可,不要超过80字"
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
    ) -> None:
        """保存配置和调度器。"""

        self.config = config
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)

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
                }],
            }

        existing_plan = state.get("plan")
        system_message = SystemMessage(content=PLANNER_SYSTEM_PROMPT)
        user_content = self._build_planning_prompt(original_prompt, existing_plan, state)
        user_message = SystemMessage(content=user_content)
        response = self._call_llm(system_message, user_message)
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
                "sufficient": plan.get("sufficient", False),
                "human_readable": readable,
            }
            return {"messages": [AIMessage(content=readable)], "plan": plan, "trace": [trace]}

        return {
            "messages": [AIMessage(content="策略分析未产出有效结果，直接进入决策。")],
            "plan": {"covered": [], "suggested": [], "sufficient": False, "hint": ""},
            "trace": [{
                "node": "planner",
                "event": "no_plan_needed",
                "human_readable": "策略分析未产出有效结果，直接进入决策。",
            }],
        }

    def _call_llm(self, system_message: Any, user_message: Any) -> Any:
        """调用 LLM 获取策略建议。

        Planner 输出是简短 JSON,不需要流式推送;始终使用 invoke_chat 避免
        前端看到逐 token 拼接的原始 JSON。
        """

        return self.task_scheduler.invoke_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, user_message],
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
            return f"用户需求:\n{query}\n\n请分析这个需求涉及哪些子话题，给出初步探索建议。输出 JSON。"

        # 重入: 附带当前覆盖状态和执行历史
        parts: list[str] = [f"用户需求:\n{query}"]
        covered = existing_plan.get("covered", [])
        if covered:
            parts.append(f"\n当前已覆盖的主题: {', '.join(covered)}")
        history = self._build_execution_history(state, limit=6)
        if history:
            parts.append(f"\n最近探索结果:\n{history}")
        parts.append("\n请根据以上信息更新探索状态，判断是否已经足够回答用户问题。输出 JSON。")
        return "\n".join(parts)

    @staticmethod
    def _build_execution_history(state: AgentState, limit: int = 6) -> str:
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
                label = f"{name}: " if name else ""
                lines.append(f"- {label}{content[:200]}{'...' if len(content) > 200 else ''}")
                count += 1
            elif isinstance(msg, AIMessage):
                tool_calls = getattr(msg, "tool_calls", []) or []
                if tool_calls:
                    names = ", ".join(tc.get("name", "") for tc in tool_calls if tc.get("name"))
                    if names:
                        lines.append(f"- [调用工具] {names}")
                        count += 1
        lines.reverse()
        return "\n".join(lines)

    @staticmethod
    def _extract_latest_user_message(state: AgentState) -> str:
        """从消息列表中提取最后一条用户消息。"""

        for message in reversed(state["messages"]):
            content = getattr(message, "content", None)
            if content and getattr(message, "type", None) == "human":
                return content if isinstance(content, str) else str(content)
        return ""

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
                return json.loads(content)
            except json.JSONDecodeError:
                return None
        return None
