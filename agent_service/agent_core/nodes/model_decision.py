"""
模型决策节点。

功能说明:
本文件只实现 `ModelDecisionNode` 一个节点。该节点负责调用 OpenAI Compatible
聊天模型,根据当前 `AgentState.messages` 决定直接回复用户还是发起工具调用。

使用说明:
`graph.py` 会把本节点注册为 `agent` 节点。节点接收 `AgentConfig` 和工具列表,
使用 `config.model` 中的模型名称、API Key、Base URL、温度和超时时间初始化模型。
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agent_service.agent_core.nodes.base import AgentState
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK, LLMTaskScheduler, get_llm_task_scheduler
from agent_service.tools import ToolExecutor
from agent_service.tools.runtime_context import get_agent_token_callback, get_context_mirror_callback

logger = logging.getLogger(__name__)


def get_user_llm_overrides(state: AgentState) -> tuple[str | None, str | None, str | None, str | None]:
    """从 SettingsService 读取用户的 LLM 配置，返回 (api_key, base_url, small_api_key, small_base_url)。

    优先从 state.llm_config 读取（一次读取，图重入不重复查 DB），
    回退到直接查询 _settings_service。
    """
    user_id = state.get("user_id")
    if not user_id:
        logger.warning("get_user_llm_overrides: state has no user_id")
        return None, None, None, None

    # 优先使用 state 中预存的 llm_config
    llm_config = state.get("llm_config")
    if llm_config:
        api_key = _normalize_optional_str(llm_config.get("api_key"))
        base_url = _normalize_optional_str(llm_config.get("base_url"))
        small_api_key = _normalize_optional_str(llm_config.get("small_api_key")) or api_key
        small_base_url = _normalize_optional_str(llm_config.get("small_base_url")) or base_url
        logger.info("get_user_llm_overrides: user=%s from state has_api_key=True api_key_len=%d", user_id, len(api_key or ""))
        return (
            api_key,
            base_url,
            small_api_key,
            small_base_url,
        )

    try:
        from agent_service.api.rest.deps import _settings_service
        if _settings_service is None:
            logger.warning("get_user_llm_overrides: _settings_service is None")
            return None, None, None, None
        config = _settings_service.get_llm_config(user_id=user_id)
        api_key = _normalize_optional_str(config.get("api_key"))
        base_url = _normalize_optional_str(config.get("base_url"))
        small_api_key = _normalize_optional_str(config.get("small_api_key")) or api_key
        small_base_url = _normalize_optional_str(config.get("small_base_url")) or base_url
        logger.info("get_user_llm_overrides: user=%s from db has_api_key=%s api_key_len=%d", user_id, bool(api_key), len(api_key or ""))
        return (
            api_key,
            base_url,
            small_api_key,
            small_base_url,
        )
    except Exception as exc:
        logger.error("get_user_llm_overrides: exception user=%s err=%s", user_id, exc)
        return None, None, None, None


def _normalize_optional_str(value: Any) -> str | None:
    """把设置项中的空字符串归一为 None,避免空 small key 覆盖可用的大模型 key。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ModelDecisionNode:
    """
    调用大模型进行 Agent 决策的 LangGraph 节点。

    config: 全局配置对象,从 `AgentCore(config=...)` 显式传入。
    tools: 可供模型调用的 LangChain 工具列表;为空时模型只会进行普通对话。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        task_scheduler: LLMTaskScheduler | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        """初始化聊天模型,并在存在工具时绑定工具。"""

        self.config = config
        self.tools = list(tools or [])
        self.tool_names = [str(tool.name) for tool in self.tools if getattr(tool, "name", None)]
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.tool_executor = tool_executor
        # 模型不在 __init__ 时创建，由调用方按需通过 self.task_scheduler 获取。
        # 用户可自行在客户端设置中配置 API Key，启动时无需强制提供。

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """读取当前消息状态,调用模型,并把模型响应追加回 `messages`。"""

        system_content = self.config.model.system_prompt

        # 追加用户自定义系统提示词(数据库持久化,每次对话自动加载)
        user_id = state.get("user_id")
        if user_id:
            try:
                from agent_service.api.rest.deps import _settings_service
                if _settings_service is not None:
                    custom_prompt = _settings_service.get_system_prompt(user_id=user_id)
                    if custom_prompt:
                        system_content += f"\n\n【用户自定义指令】\n{custom_prompt}"
            except Exception:
                pass  # 获取用户设置失败时不阻断流程

        plan = state.get("plan")
        if plan and plan.get("hint"):
            covered = plan.get("covered", [])
            suggested = plan.get("suggested", [])
            sufficient = plan.get("sufficient", False)
            status = "信息已充足，可以结束探索" if sufficient else "信息尚不充分，需继续探索"
            system_content += (
                f"\n\n【探索状态 — 仅供参考，你自行决定下一步】\n"
                f"已覆盖: {', '.join(covered) if covered else '暂无'}\n"
                f"建议方向: {', '.join(suggested) if suggested else '暂无'}\n"
                f"当前判断: {status}\n"
                f"策略提示: {plan['hint']}"
            )

        system_message = SystemMessage(content=system_content)
        token_callback = get_agent_token_callback()

        if token_callback is not None:
            return self._streaming_call(
                system_message=system_message,
                state=state,
                token_callback=token_callback,
            )

        user_api_key, user_base_url, user_small_api_key, user_small_base_url = self._get_user_model_overrides(state)
        response = self.task_scheduler.invoke_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, *state["messages"]],
            tool_names=self.tool_names,
            api_key=user_api_key,
            base_url=user_base_url,
            small_api_key=user_small_api_key,
            small_base_url=user_small_base_url,
        )
        tool_calls = getattr(response, "tool_calls", []) or []
        return {
            "messages": [response],
            "trace": [
                {
                    "node": "agent",
                    "event": "model_response",
                    "tool_call_count": len(tool_calls),
                    "has_content": bool(response.content),
                    "human_readable": self._make_agent_readable(tool_calls, bool(response.content)),
                }
            ],
        }

    def _streaming_call(
        self,
        *,
        system_message: SystemMessage,
        state: AgentState,
        token_callback: Any,
    ) -> dict[str, Any]:
        """
        流式调用模型,逐 token 通过 callback 推送,最终返回完整消息。

        system_message: 系统提示消息。
        state: 当前 AgentState。
        token_callback: 接收累积文本内容的回调。
        """

        cumulative = ""
        final_message: Any = None

        context_callback = get_context_mirror_callback()
        if context_callback is not None:
            context_callback(self._serialize_messages([system_message, *state["messages"]]))

        user_api_key, user_base_url, user_small_api_key, user_small_base_url = self._get_user_model_overrides(state)
        for chunk in self.task_scheduler.stream_chat(
            task_type=FOREGROUND_AGENT_TASK,
            messages=[system_message, *state["messages"]],
            tool_names=self.tool_names,
            api_key=user_api_key,
            base_url=user_base_url,
            small_api_key=user_small_api_key,
            small_base_url=user_small_base_url,
        ):
            is_complete = chunk.get("status") == "complete"
            if not is_complete:
                delta = chunk.get("content_delta", "")
                if delta:
                    cumulative += delta
                    token_callback(cumulative)
            if is_complete:
                final_message = chunk.get("message")
        if final_message is None:
            from langchain_core.messages import AIMessage
            final_message = AIMessage(content=cumulative)
        tool_calls = getattr(final_message, "tool_calls", []) or []
        has_content = bool(getattr(final_message, "content", None))
        return {
            "messages": [final_message],
            "trace": [
                {
                    "node": "agent",
                    "event": "model_response",
                    "tool_call_count": len(tool_calls),
                    "has_content": has_content,
                    "human_readable": self._make_agent_readable(tool_calls, has_content),
                }
            ],
        }

    def _make_agent_readable(self, tool_calls: list, has_content: bool) -> str:
        """根据模型决策生成人类可读的思考描述。"""

        if tool_calls:
            names = ", ".join(
                self._lookup_display_name(tc.get("name", "")) for tc in tool_calls if tc.get("name")
            )
            return f"模型决定调用工具：{names}"
        if has_content:
            return "模型生成最终回复。"
        return "模型返回空响应。"

    def _lookup_display_name(self, tool_name: str) -> str:
        """从工具执行器的注册表中查找工具的 display_name，找不到则回退到 tool_name。"""
        if self.tool_executor is not None:
            definition = self.tool_executor.registry.get(tool_name)
            if definition is not None and definition.display_name:
                return definition.display_name
        return tool_name

    def _get_user_model_overrides(self, state: AgentState) -> tuple[str | None, str | None, str | None, str | None]:
        """从 SettingsService 读取用户的 LLM 配置，返回 (api_key, base_url, small_api_key, small_base_url)。"""
        return get_user_llm_overrides(state)

    @staticmethod
    def _serialize_messages(messages: list) -> list[dict[str, Any]]:
        """
        将 LangChain BaseMessage 列表序列化为 JSON 友好的 dict 列表。

        用于上下文镜像回调, 让前端 Obs 面板能看到模型收到的完整消息。
        """
        role_map = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}
        result: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {
                "role": role_map.get(msg.type, msg.type),
                "content": str(getattr(msg, "content", "") or ""),
            }
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                entry["tool_calls"] = tool_calls
            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                entry["tool_call_id"] = tool_call_id
            name = getattr(msg, "name", None)
            if name:
                entry["name"] = name
            result.append(entry)
        return result

    def _build_model(self) -> Any:
        """根据 `AgentConfig.ModelConfig` 创建 OpenAI Compatible 聊天模型。

        注意: 此方法创建的模型实例仅保留向后兼容，实际 LLM 调用由
        self.task_scheduler（LLMTaskScheduler）统一管理。用户可在客户端
        设置中配置 API Key，启动时无需强制提供。
        """

        if not self.config.model.model_name:
            raise ValueError("config.model.model_name 不能为空。")

        model_kwargs = AgentConfig.ModelConfig.get_model_kwargs(self.config.model.model_name)
        model = ChatOpenAI(
            model=self.config.model.model_name,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            temperature=self.config.model.resolve_primary_temperature(),
            timeout=self.config.model.timeout_seconds,
            **model_kwargs,
        )
        if self.tools:
            return model.bind_tools(self.tools)
        return model
