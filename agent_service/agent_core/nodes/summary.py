"""
摘要节点。

功能说明:
本文件只实现 `SummaryNode` 一个节点。该节点代表 Agent 一轮回答结束后的摘要阶段,
会在后台线程中调用会话摘要服务,把当前 session 的未摘要消息提炼为长期记忆并写入
ChromaDB 向量库。

使用说明:
`graph.py` 会把本节点注册为 `summary` 节点。后续接入记忆模块后,可以在本节点内
调用上下文压缩、事实提取和长期记忆写入逻辑。
"""

from __future__ import annotations

import sys
from typing import Any

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.summary_service import SessionSummaryService
from agent_service.services.scheduler import BACKGROUND_SUMMARY_TASK, LLMTaskHandle, LLMTaskScheduler, get_llm_task_scheduler


class SummaryNode:
    """
    处理一轮 Agent 循环结束后摘要阶段的 LangGraph 节点。

    config: 全局配置对象,用于读取模型、数据库和记忆配置。
    summary_service: 可选摘要服务,测试时可注入假服务。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        summary_service: SessionSummaryService | None = None,
        task_scheduler: LLMTaskScheduler | None = None,
    ) -> None:
        """保存配置对象并初始化后台摘要执行器。"""

        self.config = config
        self.summary_service = summary_service
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.pending_tasks: list[LLMTaskHandle] = []

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """异步触发当前 session 的摘要提取和向量入库。"""

        if self.task_scheduler.supports_persistent_summary_jobs():
            task = self.task_scheduler.submit_summary_job(
                user_id=state["user_id"],
                session_id=state["session_id"],
                dedup_key=state["session_id"],
            )
            mode = "persistent_summary_queue"
        else:
            task = self.task_scheduler.submit(
                task_type=BACKGROUND_SUMMARY_TASK,
                operation=lambda: self._safe_summarize_session(
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                ),
                dedup_key=state["session_id"],
            )
            mode = "scheduler_queue"
        self.pending_tasks.append(task)

        return {
            "trace": [
                {
                    "node": "summary",
                    "event": "summary_scheduled",
                    "mode": mode,
                    "message_count": len(state["messages"]),
                }
            ]
        }

    def _get_summary_service(self) -> SessionSummaryService:
        """获取或懒加载会话摘要服务。"""

        if self.summary_service is None:
            self.summary_service = SessionSummaryService(config=self.config)
        return self.summary_service

    def _safe_summarize_session(self, *, user_id: str, session_id: str) -> str | None:
        """
        安全执行后台摘要任务。

        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        try:
            return self._get_summary_service().summarize_session(user_id=user_id, session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            if sys.is_finalizing() or "interpreter shutdown" in str(exc).lower():
                return None
            print(
                "Summary background task failed: "
                f"{exc.__class__.__name__}: {exc}"
            )
            raise
