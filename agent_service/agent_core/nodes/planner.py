"""
推理规划节点。

功能说明:
本文件只实现 `PlannerNode` 一个节点。该节点在 Agent 做出决策前,先用小模型分析
用户需求是否需要多步操作。如果需要,则生成结构化分步计划并存入 AgentState.plan。
后续 ModelDecisionNode 会读取该计划并注入到系统提示词中,指导模型按计划推进。

使用说明:
`graph.py` 会把本节点注册为 `planner` 节点,放在 `compress` 与 `agent` 之间。
节点只执行一次(计划已存在时直接跳过)。
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK, LLMTaskScheduler, get_llm_task_scheduler
from agent_service.tools.runtime_context import get_planner_content_callback


PLANNER_SYSTEM_PROMPT = (
    "你是一个任务规划助手。分析用户的最新需求,判断是否需要分步完成。\n"
    "如果任务需要多步操作才能完成(例如查询多个信息、执行多个计算、依次处理数据),"
    "请输出 JSON 格式的分步计划。\n"
    "如果任务很简单,只需回答即可,无需计划。\n"
    "输出格式(只输出 JSON,不要其他文字):\n"
    '{"need_plan": true, "steps": ["第一步: ...", "第二步: ..."]}\n'
    '或\n'
    '{"need_plan": false}'
)


class PlannerNode:
    """
    推理规划节点。

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
        检查是否需要规划,需要时用小模型生成计划。

        state: 当前 LangGraph 状态。
        """

        if state.get("plan") is not None:
            return {
                "messages": [AIMessage(content="已有执行计划，继续按计划推进。")],
                "trace": [{
                    "node": "planner",
                    "event": "plan_already_exists",
                    "human_readable": "已有执行计划，继续按计划推进。",
                }],
            }

        original_prompt = self._extract_latest_user_message(state)
        if not original_prompt:
            return {
                "messages": [AIMessage(content="未找到用户消息，跳过规划。")],
                "trace": [{
                    "node": "planner",
                    "event": "no_user_message",
                    "human_readable": "未找到用户消息，跳过规划。",
                }],
            }

        if self._is_simple_query(original_prompt):
            return {
                "messages": [AIMessage(content="这是一个简单问题，无需分步规划，直接回答。")],
                "plan": {"need_plan": False},
                "trace": [{
                    "node": "planner",
                    "event": "fast_path_simple_query",
                    "human_readable": "这是一个简单问题，无需分步规划，直接回答。",
                }],
            }

        system_message = SystemMessage(content=PLANNER_SYSTEM_PROMPT)
        user_message = SystemMessage(
            content=f"用户需求:\n{original_prompt}\n\n请输出 JSON 计划。"
        )
        response = self._call_llm(system_message, user_message)
        plan = self._parse_plan(response.content)
        if plan is not None:
            need_plan = plan.get("need_plan", False)
            steps = plan.get("steps", [])
            if need_plan and steps:
                readable = "我需要分 {} 步来完成这个任务：\n{}".format(
                    len(steps),
                    "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps)),
                )
            else:
                readable = "分析后判断：不需要分步计划，可以直接处理。"
            trace = {
                "node": "planner",
                "event": "plan_generated",
                "need_plan": need_plan,
                "steps": steps,
                "human_readable": readable,
            }
            return {"messages": [AIMessage(content=readable)], "plan": plan, "trace": [trace]}

        return {
            "messages": [AIMessage(content="模型未生成有效计划，直接进入决策。")],
            "plan": {"need_plan": False},
            "trace": [{
                "node": "planner",
                "event": "no_plan_needed",
                "human_readable": "模型未生成有效计划，直接进入决策。",
            }],
        }

    def _call_llm(self, system_message: Any, user_message: Any) -> Any:
        """调用 LLM,流式场景下通过 callback 逐 token 推送。"""

        callback = get_planner_content_callback()
        if callback is not None:
            cumulative = ""
            final_message: Any = None
            for chunk in self.task_scheduler.stream_chat(
                task_type=FOREGROUND_AGENT_TASK,
                messages=[system_message, user_message],
                model_tier="small",
            ):
                delta = chunk.get("content_delta", "")
                if delta:
                    cumulative += delta
                    callback(cumulative)
                if chunk.get("status") == "complete":
                    final_message = chunk.get("message")
            if final_message is None:
                from langchain_core.messages import AIMessage
                final_message = AIMessage(content=cumulative)
            return final_message

        return self.task_scheduler.invoke_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, user_message],
            model_tier="small",
        )

    @staticmethod
    def _extract_latest_user_message(state: AgentState) -> str:
        """从消息列表中提取最后一条用户消息。"""

        for message in reversed(state["messages"]):
            content = getattr(message, "content", None)
            if content and getattr(message, "type", None) == "human":
                return content if isinstance(content, str) else str(content)
        return ""

    @staticmethod
    def _is_simple_query(prompt: str) -> bool:
        """
        启发式判断是否为简单查询,跳过 LLM 规划调用。

        规则:
        - 纯中文/英文问候语(≤10 字)
        - 单句短问题(≤20 字且无逗号/分号)
        - 不含"步骤"、"规划"、"然后"等复杂意图关键词
        """
        text = prompt.strip()
        if len(text) <= 10:
            return True
        if len(text) <= 20:
            separators = ("，", ",", "；", ";", "。", "、", "\n")
            if not any(sep in text for sep in separators):
                return True
        return False

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
