"""
工具运行时上下文模块。

功能说明:
本文件负责在 Agent 一轮执行期间为 builtin 工具暴露当前 `config`、`user_id`、
`session_id`、统一检索服务、记忆写入服务和 Embedding 服务。这样工具在执行时
可以访问当前会话上下文,而不需要把这些内部参数显式暴露给模型。
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import local
from typing import TYPE_CHECKING

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.retrieval_service import MemoryRetrievalService

if TYPE_CHECKING:
    from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
    from agent_service.services.memory.rag.embedding import EmbeddingService


@dataclass(slots=True)
class ToolRuntimeState:
    """
    工具运行时状态。

    config: 当前 Agent 配置对象。
    user_id: 当前用户 ID。
    session_id: 当前会话 ID。
    retrieval_service: 可复用的统一检索服务。
    memory_service: 可复用的长期记忆写入服务。
    embedding_service: 可复用的 Embedding 向量生成服务。
    """

    config: AgentConfig
    user_id: str
    session_id: str
    retrieval_service: MemoryRetrievalService
    memory_service: LongTermMemoryService | None = None
    embedding_service: EmbeddingService | None = None


_TOOL_RUNTIME = local()


def set_tool_runtime(
    *,
    config: AgentConfig,
    user_id: str,
    session_id: str,
    retrieval_service: MemoryRetrievalService | None = None,
    memory_service: LongTermMemoryService | None = None,
    embedding_service: EmbeddingService | None = None,
) -> None:
    """
    设置当前线程的工具运行时状态。

    config: 当前 Agent 配置。
    user_id: 当前用户 ID。
    session_id: 当前会话 ID。
    retrieval_service: 可选统一检索服务,用于测试或复用外部实例。
    memory_service: 可选长期记忆写入服务。
    embedding_service: 可选 Embedding 向量生成服务。
    """

    from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
    from agent_service.services.memory.rag.embedding import EmbeddingService

    _TOOL_RUNTIME.state = ToolRuntimeState(
        config=config,
        user_id=user_id,
        session_id=session_id,
        retrieval_service=retrieval_service or MemoryRetrievalService(config=config),
        memory_service=memory_service or LongTermMemoryService(config=config),
        embedding_service=embedding_service or EmbeddingService(config=config),
    )


def clear_tool_runtime() -> None:
    """清理当前线程的工具运行时状态。"""

    if hasattr(_TOOL_RUNTIME, "state"):
        delattr(_TOOL_RUNTIME, "state")


# ------------------------------------------------------------------
# 流式 Token 回调 (用于 ModelDecisionNode → AgentCore 实时推送)
# ------------------------------------------------------------------

from collections.abc import Callable

_AGENT_TOKEN_CALLBACK: local = local()


def set_agent_token_callback(callback: Callable[[str], None]) -> None:
    """
    设置当前线程的 Agent token 回调,供 ModelDecisionNode 在流式生成时逐 token 调用。

    callback: 接收累积文本内容的回调函数。
    """

    _AGENT_TOKEN_CALLBACK.callback = callback


def get_agent_token_callback() -> Callable[[str], None] | None:
    """
    获取当前线程的 Agent token 回调。

    返回值: 已设置的回调函数,未设置时返回 None。
    """

    return getattr(_AGENT_TOKEN_CALLBACK, "callback", None)


def clear_agent_token_callback() -> None:
    """清理当前线程的 Agent token 回调。"""

    if hasattr(_AGENT_TOKEN_CALLBACK, "callback"):
        delattr(_AGENT_TOKEN_CALLBACK, "callback")


# ------------------------------------------------------------------
# 工具调用 Trace 回调 (用于 ToolCallNode → AgentCore 实时推送)
# ------------------------------------------------------------------

from typing import Any

_TOOL_TRACE_CALLBACK: local = local()


def set_tool_trace_callback(callback: Callable[[dict[str, Any]], None]) -> None:
    """
    设置当前线程的工具 trace 回调,供 ToolCallNode 在每步工具调用前后调用。

    callback: 接收 trace dict 的回调函数。
    """

    _TOOL_TRACE_CALLBACK.callback = callback


def get_tool_trace_callback() -> Callable[[dict[str, Any]], None] | None:
    """
    获取当前线程的工具 trace 回调。

    返回值: 已设置的回调函数,未设置时返回 None。
    """

    return getattr(_TOOL_TRACE_CALLBACK, "callback", None)


def clear_tool_trace_callback() -> None:
    """清理当前线程的工具 trace 回调。"""

    if hasattr(_TOOL_TRACE_CALLBACK, "callback"):
        delattr(_TOOL_TRACE_CALLBACK, "callback")


# ------------------------------------------------------------------
# Planner 内容回调 (用于 PlannerNode → AgentCore 流式推送)
# ------------------------------------------------------------------

_PLANNER_CONTENT_CALLBACK: local = local()


def set_planner_content_callback(callback: Callable[[str], None]) -> None:
    """设置当前线程的 planner 内容回调,供 PlannerNode 在流式生成时逐 token 调用。"""
    _PLANNER_CONTENT_CALLBACK.callback = callback


def get_planner_content_callback() -> Callable[[str], None] | None:
    """获取当前线程的 planner 内容回调。"""
    return getattr(_PLANNER_CONTENT_CALLBACK, "callback", None)


def clear_planner_content_callback() -> None:
    """清理当前线程的 planner 内容回调。"""
    if hasattr(_PLANNER_CONTENT_CALLBACK, "callback"):
        delattr(_PLANNER_CONTENT_CALLBACK, "callback")


# ------------------------------------------------------------------
# Reflection 内容回调 (用于 ReflectionNode → AgentCore 流式推送)
# ------------------------------------------------------------------

_REFLECTION_CONTENT_CALLBACK: local = local()


def set_reflection_content_callback(callback: Callable[[str], None]) -> None:
    """设置当前线程的 reflection 内容回调,供 ReflectionNode 在流式生成时逐 token 调用。"""
    _REFLECTION_CONTENT_CALLBACK.callback = callback


def get_reflection_content_callback() -> Callable[[str], None] | None:
    """获取当前线程的 reflection 内容回调。"""
    return getattr(_REFLECTION_CONTENT_CALLBACK, "callback", None)


def clear_reflection_content_callback() -> None:
    """清理当前线程的 reflection 内容回调。"""
    if hasattr(_REFLECTION_CONTENT_CALLBACK, "callback"):
        delattr(_REFLECTION_CONTENT_CALLBACK, "callback")


# ------------------------------------------------------------------
# 上下文镜像回调 (用于 ModelDecisionNode → AgentCore 发送模型所见完整消息列表)
# ------------------------------------------------------------------

_CONTEXT_MIRROR_CALLBACK: local = local()


def set_context_mirror_callback(callback: Callable[[list[dict[str, Any]]], None]) -> None:
    """
    设置当前线程的上下文镜像回调, 供 ModelDecisionNode 在调用 LLM 前
    将完整消息列表镜像给 AgentCore, 再由 SSE 下发给前端 Obs 面板。

    callback: 接收序列化后的消息列表 (list[dict]) 的回调函数。
    """
    _CONTEXT_MIRROR_CALLBACK.callback = callback


def get_context_mirror_callback() -> Callable[[list[dict[str, Any]]], None] | None:
    """获取当前线程的上下文镜像回调。"""
    return getattr(_CONTEXT_MIRROR_CALLBACK, "callback", None)


def clear_context_mirror_callback() -> None:
    """清理当前线程的上下文镜像回调。"""
    if hasattr(_CONTEXT_MIRROR_CALLBACK, "callback"):
        delattr(_CONTEXT_MIRROR_CALLBACK, "callback")


def get_tool_runtime() -> ToolRuntimeState:
    """
    获取当前线程的工具运行时状态。

    如果工具在 AgentCore 之外被直接调用,会抛出错误。
    """

    state = getattr(_TOOL_RUNTIME, "state", None)
    if state is None:
        raise RuntimeError("当前工具调用缺少 Agent 运行时上下文。")
    return state


# ------------------------------------------------------------------
# Agent 探索状态 (供 update_exploration_state 工具修改)
# ------------------------------------------------------------------

_PLAN_STATE: local = local()


def set_plan_state(plan: dict[str, Any] | None) -> None:
    """设置当前线程的探索状态,供工具读取和修改。"""
    import copy
    _PLAN_STATE.state = copy.deepcopy(plan) if plan is not None else None


def get_plan_state() -> dict[str, Any] | None:
    """获取当前线程的探索状态。"""
    return getattr(_PLAN_STATE, "state", None)


def clear_plan_state() -> None:
    """清理当前线程的探索状态。"""
    if hasattr(_PLAN_STATE, "state"):
        delattr(_PLAN_STATE, "state")
