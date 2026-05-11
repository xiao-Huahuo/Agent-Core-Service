"""
摘要节点。

功能说明:
本文件只实现 `SummaryNode` 一个节点。该节点代表 Agent 一轮回答结束后的摘要阶段。
当前项目的长期记忆、PostgreSQL 和 pgvector 模块尚未实现,所以第一版只记录轨迹,
不做真实摘要入库。

使用说明:
`graph.py` 会把本节点注册为 `summary` 节点。后续接入记忆模块后,可以在本节点内
调用上下文压缩、事实提取和长期记忆写入逻辑。
"""

from __future__ import annotations

from typing import Any

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig


class SummaryNode:
    """
    处理一轮 Agent 循环结束后摘要阶段的 LangGraph 节点。

    config: 全局配置对象,后续用于读取摘要触发阈值、记忆标签和存储配置。
    """

    def __init__(self, *, config: AgentConfig) -> None:
        """保存配置对象,为后续接入真实记忆逻辑做准备。"""

        self.config = config

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """记录摘要阶段已执行;第一版不修改消息列表。"""

        return {
            "trace": [
                {
                    "node": "summary",
                    "event": "summary_skipped",
                    "reason": "memory_module_not_implemented",
                    "message_count": len(state["messages"]),
                }
            ]
        }
