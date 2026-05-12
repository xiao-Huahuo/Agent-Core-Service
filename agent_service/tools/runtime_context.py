"""
工具运行时上下文模块。

功能说明:
本文件负责在 Agent 一轮执行期间为 builtin 工具暴露当前 `config`、`user_id`、
`session_id` 和统一检索服务。这样工具在执行时可以访问当前会话上下文,而不需要
把这些内部参数显式暴露给模型。
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import local

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.retrieval_service import MemoryRetrievalService


@dataclass(slots=True)
class ToolRuntimeState:
    """
    工具运行时状态。

    config: 当前 Agent 配置对象。
    user_id: 当前用户 ID。
    session_id: 当前会话 ID。
    retrieval_service: 可复用的统一检索服务。
    """

    config: AgentConfig
    user_id: str
    session_id: str
    retrieval_service: MemoryRetrievalService


_TOOL_RUNTIME = local()


def set_tool_runtime(
    *,
    config: AgentConfig,
    user_id: str,
    session_id: str,
    retrieval_service: MemoryRetrievalService | None = None,
) -> None:
    """
    设置当前线程的工具运行时状态。

    config: 当前 Agent 配置。
    user_id: 当前用户 ID。
    session_id: 当前会话 ID。
    retrieval_service: 可选统一检索服务,用于测试或复用外部实例。
    """

    _TOOL_RUNTIME.state = ToolRuntimeState(
        config=config,
        user_id=user_id,
        session_id=session_id,
        retrieval_service=retrieval_service or MemoryRetrievalService(config=config),
    )


def clear_tool_runtime() -> None:
    """清理当前线程的工具运行时状态。"""

    if hasattr(_TOOL_RUNTIME, "state"):
        delattr(_TOOL_RUNTIME, "state")


def get_tool_runtime() -> ToolRuntimeState:
    """
    获取当前线程的工具运行时状态。

    如果工具在 AgentCore 之外被直接调用,会抛出错误。
    """

    state = getattr(_TOOL_RUNTIME, "state", None)
    if state is None:
        raise RuntimeError("当前工具调用缺少 Agent 运行时上下文。")
    return state
