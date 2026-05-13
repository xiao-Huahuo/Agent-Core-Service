"""
上下文压缩节点。

功能说明:
本文件只实现 `CompressNode` 一个节点。该节点会在每次进入模型决策前检查当前
工作消息是否已经接近上下文 token 配额上限。如果超过阈值,节点会:

1. 使用小模型生成“重要事实摘要”。
2. 把该摘要写入统一长期记忆表。
3. 将当前工作消息替换为“压缩摘要 + 最近少量消息”,然后把控制流交回 `agent` 节点。

使用说明:
`graph.py` 会把本节点放在 `agent` 前面,因此它既能覆盖对话入口,也能覆盖
`action -> agent` 的回路。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, RemoveMessage, SystemMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.memory.important_fact_summary_service import ImportantFactSummaryService
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK, LLMTaskScheduler, get_llm_task_scheduler


class CompressNode:
    """
    上下文压缩节点。

    config: 全局配置对象。
    task_scheduler: 统一调度器,用于将压缩摘要路由到小模型池。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        task_scheduler: LLMTaskScheduler | None = None,
        summary_service: ImportantFactSummaryService | None = None,
    ) -> None:
        """初始化压缩节点依赖。"""

        self.config = config
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.summary_service = summary_service or ImportantFactSummaryService(
            config=config,
            task_scheduler=self.task_scheduler,
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """
        在模型决策前检查是否需要压缩上下文。

        state: 当前 LangGraph 运行状态。
        """

        estimated_tokens = ContextBuilder.estimate_messages_tokens(state["messages"])
        if estimated_tokens <= self.config.memory.summary_trigger_tokens:
            return {
                "trace": [
                    {
                        "node": "compress",
                        "event": "compression_skipped",
                        "estimated_tokens": estimated_tokens,
                    }
                ]
            }
        transcript = self._build_transcript(state["messages"])
        summary_text = self.summary_service.summarize_text(
            transcript=transcript,
            task_type=FOREGROUND_AGENT_TASK,
            mode="compress",
        )
        if not summary_text:
            return {
                "trace": [
                    {
                        "node": "compress",
                        "event": "compression_empty",
                        "estimated_tokens": estimated_tokens,
                    }
                ]
            }
        source_hash = self.summary_service.build_hash(
            state["session_id"],
            state["user_id"],
            transcript,
        )
        self.summary_service.persist_summary_memory(
            user_id=state["user_id"],
            session_id=state["session_id"],
            summary_text=summary_text,
            memory_type=self.config.constants.important_fact_summary_memory_type,
            source_type="context_compression",
            source_id=state["session_id"],
            source_hash=source_hash,
            source_range_json={"mode": "compress"},
            metadata_json={"estimated_tokens": estimated_tokens},
            importance=0.95,
            authority=0.6,
        )
        compressed_messages = self._build_compressed_messages(
            original_messages=state["messages"],
            summary_text=summary_text,
        )
        return {
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *compressed_messages],
            "trace": [
                {
                    "node": "compress",
                    "event": "compression_applied",
                    "estimated_tokens": estimated_tokens,
                    "compressed_message_count": len(compressed_messages),
                }
            ],
        }

    @staticmethod
    def _build_transcript(messages: list[BaseMessage]) -> str:
        """
        将当前工作消息转换为适合摘要模型消费的文本。

        messages: 当前工作消息列表。
        """

        lines: list[str] = []
        for message in messages:
            content = str(getattr(message, "content", "") or "").strip()
            if not content:
                continue
            lines.append(f"{message.type}: {content}")
        return "\n".join(lines)

    def _build_compressed_messages(
        self,
        *,
        original_messages: list[BaseMessage],
        summary_text: str,
    ) -> list[BaseMessage]:
        """
        构建压缩后的工作消息列表。

        original_messages: 压缩前的完整消息列表。
        summary_text: 小模型生成的重要事实摘要。
        """

        tail_count = max(self.config.memory.context_compression_tail_messages, 1)
        recent_messages = original_messages[-tail_count:]
        summary_message = SystemMessage(
            content=(
                "以下是当前会话在上下文压缩后保留的重要事实摘要,继续回答时必须优先参考:\n"
                f"{summary_text}"
            )
        )
        return [summary_message, *recent_messages]
