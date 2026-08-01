"""
子 Agent 运行时服务包。

功能说明:
本包提供父 Agent 管理子 Agent 所需的最小运行时能力,包括子任务合同、
生命周期状态、独立线程执行、父级结果队列、权限继承和协作式停止。

使用说明:
第一版通过注入 `ChildAgentExecutor` 执行具体任务,因此可以先用假执行器测试
父子调度逻辑,再由 AgentCore 适配为真实的子 Agent 执行器。
"""

from agent_service.services.child_agent.manager import ChildAgentManager
from agent_service.services.child_agent.types import (
    ChildAgentContract,
    ChildAgentEvent,
    ChildAgentExecutionContext,
    ChildAgentRecord,
    ChildAgentResult,
    ChildAgentStatus,
    ChildAgentUpdate,
)

__all__ = [
    "ChildAgentContract",
    "ChildAgentEvent",
    "ChildAgentExecutionContext",
    "ChildAgentManager",
    "ChildAgentRecord",
    "ChildAgentResult",
    "ChildAgentStatus",
    "ChildAgentUpdate",
]
