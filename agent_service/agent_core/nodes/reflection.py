"""
反思节点。

功能说明:
本文件只实现 `ReflectionNode` 一个节点。该节点在工具调用执行完毕后,用大模型审视
工具执行结果,判断是否已经获得足够信息回答用户问题,或者还需要继续调用工具。

使用说明:
`graph.py` 会把本节点注册为 `reflection` 节点,放在 `action` 之后。
节点输出 `reflection_decision` 字段,"continue" 表示继续工具循环,"answer" 表示
可以输出最终答案,路由到摘要节点结束本轮执行。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK, LLMTaskScheduler, get_llm_task_scheduler
from agent_service.tools.runtime_context import get_reflection_content_callback


REFLECTION_SYSTEM_PROMPT = (
    "你是一个执行结果审视助手。分析最近一次工具调用的结果,"
    "判断是否已经获得足够信息来回答用户的原始问题。\n"
    "如果还需要继续调用工具获取更多信息,只输出: continue\n"
    "如果已经足够,可以给出最终答案了,只输出: answer\n"
    "只输出 continue 或 answer,不要其他文字。\n"
    "注意:如果工具执行返回了错误,你可以建议继续尝试其他方式。"
)


class ReflectionNode:
    """
    反思节点。

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
        审视最近一次工具执行结果,决定继续还是回答。

        当 LLM 决定继续时,额外检查上下文 token 是否溢出:
        - 未溢出 → "continue"(直接路由到 planner)
        - 已溢出 → "compress"(先经过 compress 再到 planner)

        state: 当前 LangGraph 状态。
        """

        summary = self._build_reflection_context(state)
        if not summary:
            decision = self._check_overflow_then_decide(state, "continue")
            return {
                "messages": [AIMessage(content="没有需要审视的工具执行结果，继续推进。")],
                "reflection_decision": decision,
                "trace": [{
                    "node": "reflection",
                    "event": "no_tool_results_to_review",
                    "human_readable": "没有需要审视的工具执行结果，继续推进。",
                }],
            }

        system_message = SystemMessage(content=REFLECTION_SYSTEM_PROMPT)
        context_message = SystemMessage(content=summary)
        response = self._call_llm(system_message, context_message)
        llm_decision = self._parse_decision(response.content)
        decision = self._check_overflow_then_decide(state, llm_decision)
        if decision == "answer":
            readable = "工具执行结果已足够回答用户问题，准备生成最终回复。"
        elif decision == "compress":
            readable = "上下文已接近 token 上限，需要先压缩历史对话再继续。"
        else:
            readable = "信息还不够充分，需要继续调用工具获取更多信息。"
        trace = {
            "node": "reflection",
            "event": "reflection_complete",
            "decision": decision,
            "human_readable": readable,
        }
        return {"messages": [AIMessage(content=readable)], "reflection_decision": decision, "trace": [trace]}

    def _call_llm(self, system_message: Any, context_message: Any) -> Any:
        """调用 LLM,流式场景下通过 callback 逐 token 推送。"""

        callback = get_reflection_content_callback()
        if callback is not None:
            cumulative = ""
            final_message: Any = None
            for chunk in self.task_scheduler.stream_chat(
                task_type=FOREGROUND_AGENT_TASK,
                messages=[system_message, context_message],
                model_tier="large",
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
            messages=[system_message, context_message],
            model_tier="large",
        )

    def _check_overflow_then_decide(self, state: AgentState, llm_decision: str) -> str:
        """当 LLM 决定 continue 时,检查上下文是否溢出;溢出则返回 compress 迫使进入压缩节点。"""

        if llm_decision != "continue":
            return llm_decision
        estimated_tokens = ContextBuilder.estimate_messages_tokens(state.get("messages", []))
        if estimated_tokens > self.config.memory.summary_trigger_tokens:
            return "compress"
        return "continue"

    @staticmethod
    def _build_reflection_context(state: AgentState) -> str:
        """
        从 state 中提取最近一次工具调用的上下文。
        只提取当前 cycle(最近一条人类消息之后)的工具调用和结果,
        避免跨 cycle 污染。
        """

        messages = state.get("messages", [])
        parts: list[str] = []

        # 找到最近一条人类消息的位置,作为当前 cycle 的起点
        human_idx = -1
        for i, message in enumerate(messages):
            if getattr(message, "type", None) == "human":
                human_idx = i

        if human_idx < 0:
            return ""

        parts.append(f"用户问题:\n{messages[human_idx].content}")

        # 只提取当前 cycle(人类消息之后)的工具调用和结果
        tool_calls = []
        tool_results = []
        for message in messages[human_idx + 1:]:
            msg_type = getattr(message, "type", None)
            content = getattr(message, "content", None)
            if msg_type == "ai":
                calls = getattr(message, "tool_calls", []) or []
                for tc in calls:
                    tool_calls.append(tc)
            elif msg_type == "tool" and content:
                tool_results.append(f"  结果: {content[:500]}")

        if tool_calls:
            tc = tool_calls[-1]
            args_str = str(tc.get("args", {}))
            parts.append(f"最近工具调用: {tc.get('name', '')} ({args_str})")
        if tool_results:
            parts.extend(tool_results)

        if len(parts) <= 1:
            return ""

        return "\n".join(parts)

    @staticmethod
    def _parse_decision(raw_content: str | None) -> str:
        """从模型响应中解析决策。"""

        if not raw_content:
            return "continue"
        cleaned = raw_content.strip().lower()
        if "answer" in cleaned:
            return "answer"
        return "continue"
