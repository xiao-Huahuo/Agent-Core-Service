"""
AgentCore 对外入口模块。

功能说明:
本文件提供 `AgentCore` 类,作为 Agent 微服务核心能力的对外门面。它负责接收
`AgentConfig`、加载默认内置工具、构建 LangGraph 图、输出图结构 Mermaid 文件,
启动时检查并下载 Embedding/ReRank 本地模型,并对外提供 Agent 执行入口。具体节点逻辑不写在本文件中,而是由
`AgentGraphBuilder` 装配 `compress`、`planner`、`model_decision`、`tool_call`、`observation` 和 `summary` 等节点。

执行能力:
`stream_run()` 提供 SSE 风格的原始流式输出,适合接口层直接转发给前端。
`run_once()` 在 `stream_run()` 之上整理结构化结果,包含图结构、原始 chunks、
节点事件、最终输出等字段,适合测试脚本、调试接口和后续前端观测面板使用。

可观测能力:
`parse_stream_chunks()` 负责把 SSE 字符串解析成节点事件列表。
`extract_final_output()` 负责从节点事件中提取最终智能体回复。
`build_human_readable_process()` 负责把节点事件格式化为给人阅读的可观测过程,
但不暴露模型内部不可观测的思维链。

Session 入口:
`run_session_prompt()` 是面向主服务和 gRPC 的正式 session 级入口。它通过
ContextBuilder 构建同一 session 的短期上下文,执行 Agent 图,并通过
MessageService 保存本轮 user、assistant 和 tool 消息。

使用说明:
调用方应显式传入配置对象:

config = AgentConfig.load_config()
agent = AgentCore(config=config)
for chunk in agent.stream_run(prompt="你好", user_id="u1", session_id="s1"):
    ...

result = agent.run_once(prompt="你好", user_id="u1", session_id="s1")
"""

from __future__ import annotations

import json
import logging
import queue as queue_module
import re
import threading
import time
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.graph import AgentGraphBuilder
from agent_service.agent_core.nodes.model_decision import extract_token_usage
from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.message import MessageCreate
from agent_service.scripts.draw_agent_graph import draw_agent_graph
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.message_service import MessageService
from agent_service.services.session_attachment_service import SessionAttachmentService
from agent_service.services.safety import SafetyService
from agent_service.services.scheduler import (
    BACKGROUND_SUMMARY_TASK,
    FOREGROUND_AGENT_TASK,
    LARGE_MODEL_TIER,
    SMALL_MODEL_TIER,
    LLMTaskScheduler,
    get_llm_task_scheduler,
)
from agent_service.tools import (
    ToolExecutor,
    ToolRegistry,
    clear_agent_token_callback,
    clear_context_mirror_callback,
    clear_plan_state,
    clear_planner_content_callback,
    clear_observation_content_callback,
    clear_tool_runtime,
    clear_tool_trace_callback,
    get_plan_state,
    set_agent_token_callback,
    set_context_mirror_callback,
    set_plan_state,
    set_planner_content_callback,
    set_observation_content_callback,
    set_tool_runtime,
    set_tool_trace_callback,
    normalize_agent_access_mode,
)

logger = logging.getLogger(__name__)

AGENT_LOOP_AUTO = "auto"
AGENT_LOOP_SIMPLE = "simple"
AGENT_LOOP_REACT = "react"
AGENT_LOOP_PLAN = "plan"
AGENT_LOOP_DEEP_ALIAS = "deep"
AGENT_LOOP_MODES = {AGENT_LOOP_AUTO, AGENT_LOOP_SIMPLE, AGENT_LOOP_REACT, AGENT_LOOP_PLAN, AGENT_LOOP_DEEP_ALIAS}
CITATION_ANCHOR_PATTERN = re.compile(r"\[([A-Z]?\d+)\]")


def _extract_friendly_error(error_message: str) -> str:
    """从 LLM 调度层抛出的原始错误中提取对用户友好的提示信息。

    根据错误来源分类处理：
    - content_filter: 内容安全策略拦截,提示用户修改输入。
    - rate_limit: 速率限制,提示稍后重试。
    - 其他: 保留简洁的概要信息,避免暴露内部调用栈。
    """
    lower = error_message.lower()
    if "content_filter" in lower:
        msg = error_message
        # 提取 API 返回的具体原因文本
        import re
        match = re.search(r"'message':\s*'([^']+)'", msg) or re.search(
            r'"message":\s*"([^"]+)"', msg
        )
        detail = match.group(1) if match else "请求因内容安全策略被拦截"
        return f"内容安全拦截: {detail}"
    if "429" in lower or "too many requests" in lower or "rate_limit" in lower or "rate limit" in lower:
        return "模型服务限流(429 Too Many Requests),请稍后重试;如果频繁出现,请切换模型或配置独立的小模型 API Key。"
    if "missing api key" in lower or (
        "api key" in lower and ("missing" in lower or "not found" in lower or "empty" in lower)
    ):
        return "模型 API Key 未配置或未传入,请在设置页检查主模型和小模型 API Key。"
    if "timeout" in lower:
        return "请求超时,请稍后重试"
    if "connection error" in lower or "connection reset" in lower or "connection aborted" in lower:
        return "模型服务连接失败,请检查网络、代理、Base URL 和 API Key;如果服务端刚返回过 429,通常是限流导致的连接中断。"
    # 默认返回精简后的第一行错误,避免泄漏堆栈
    first_line = error_message.split("\n")[0].strip()
    return first_line


class AgentCore:
    """
    Agent 微服务核心入口。

    config: 由 `core.agent_config.AgentConfig.load_config()` 创建的显式配置对象。
    tools: 可选 LangChain 工具列表;为空时默认加载工具注册表中的内置工具。
    graph: 可选已编译图对象,主要用于测试时注入假图以避免真实模型请求。
    message_service: 可选消息服务,用于 session 级正式入口的消息持久化。
    context_builder: 可选上下文构建器,用于 session 级正式入口的短期上下文构建。
    session_service: 可选会话服务,用于跨轮持久化和恢复 Agent 探索状态。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        graph: CompiledStateGraph | None = None,
        message_service: MessageService | None = None,
        context_builder: ContextBuilder | None = None,
        attachment_service: SessionAttachmentService | None = None,
        task_scheduler: LLMTaskScheduler | None = None,
        session_service: Any = None,
    ) -> None:
        """保存配置、检查本地模型、构建或接收 LangGraph 图,并输出当前节点流程图。"""

        self.config = config
        logger.debug("AgentCore 初始化开始 | model=%s", config.model.model_name)
        self.config.ensure_local_models()
        logger.debug("本地模型检查完成")
        self.message_service = message_service
        self.context_builder = context_builder
        self.attachment_service = attachment_service
        self.session_service = session_service
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.tool_registry = ToolRegistry.with_builtin_tools(config=config) if tools is None else None
        self.tool_executor = ToolExecutor(registry=self.tool_registry) if self.tool_registry is not None else None
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_events_lock = threading.Lock()
        self.tools = list(tools) if tools is not None else self.tool_registry.to_langchain_tools()
        if message_service is not None:
            self._get_context_builder(message_service=message_service)
            if self.context_builder is not None:
                logger.info("预加载 Embedding / ReRank 模型中...")
                self.context_builder.retrieval_service.warmup()
                logger.info("Embedding / ReRank 模型预加载完成")
        safety_service = SafetyService(config=config, task_scheduler=self.task_scheduler)
        self.safety_service = safety_service
        plan_builder = AgentGraphBuilder(
            config=config,
            tools=self.tools,
            tool_executor=self.tool_executor,
            task_scheduler=self.task_scheduler,
            safety_service=safety_service,
        )
        react_builder = AgentGraphBuilder(
            config=config,
            tools=self.tools,
            tool_executor=self.tool_executor,
            task_scheduler=self.task_scheduler,
            safety_service=safety_service,
        )
        self.graph: CompiledStateGraph = graph or plan_builder.build(mode=AGENT_LOOP_PLAN)
        self.graphs: dict[str, CompiledStateGraph] = {
            AGENT_LOOP_PLAN: self.graph,
            AGENT_LOOP_REACT: graph or react_builder.build(mode=AGENT_LOOP_REACT),
        }
        self.graph_diagram_paths = {
            AGENT_LOOP_PLAN: draw_agent_graph(
                compiled_graph=self.graphs[AGENT_LOOP_PLAN],
                output_path=config.storage.project_root / "agent_graph.mmd",
                branch_labels=plan_builder.branch_labels,
            ),
            AGENT_LOOP_REACT: draw_agent_graph(
                compiled_graph=self.graphs[AGENT_LOOP_REACT],
                output_path=config.storage.project_root / "agent_graph_react.mmd",
                branch_labels=react_builder.branch_labels,
            ),
        }
        self.graph_diagram_path = self.graph_diagram_paths[AGENT_LOOP_PLAN]

    def stream_run(
        self,
        *,
        prompt: str,
        user_id: str,
        session_id: str,
        agent_mode: str = AGENT_LOOP_PLAN,
        agent_access_mode: str = "sandbox",
    ) -> Iterator[dict[str, Any]]:
        """
        运行一轮无状态 Agent 并逐节点产出 dict 事件。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        agent_mode: Agent Loop 模式,支持 react / plan。无状态入口不使用 simple。
        """

        effective_mode = AGENT_LOOP_REACT if agent_mode == AGENT_LOOP_REACT else AGENT_LOOP_PLAN
        messages = [HumanMessage(content=prompt)]
        logger.info("开始无状态流式运行 | user=%s session=%s mode=%s", user_id, session_id, effective_mode)
        yield from self._stream_events(
            messages=messages,
            user_id=user_id,
            session_id=session_id,
            graph=self.graphs[effective_mode],
            agent_mode=effective_mode,
            agent_access_mode=agent_access_mode,
        )
        logger.debug("无状态流式运行完成 | user=%s session=%s mode=%s", user_id, session_id, effective_mode)

    def run_once(
        self,
        *,
        prompt: str,
        user_id: str,
        session_id: str,
        agent_mode: str = AGENT_LOOP_PLAN,
        agent_access_mode: str = "sandbox",
    ) -> dict[str, Any]:
        """
        运行一轮无状态 Agent 并返回结构化结果。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        agent_mode: Agent Loop 模式,支持 react / plan。
        """

        effective_mode = AGENT_LOOP_REACT if agent_mode == AGENT_LOOP_REACT else AGENT_LOOP_PLAN
        chunks = list(self.stream_run(
            prompt=prompt,
            user_id=user_id,
            session_id=session_id,
            agent_mode=effective_mode,
            agent_access_mode=agent_access_mode,
        ))
        graph_diagram_path = self.graph_diagram_paths[effective_mode]
        graph_diagram = graph_diagram_path.read_text(encoding="utf-8")
        return {
            "graph_diagram_path": str(graph_diagram_path),
            "graph_diagram": graph_diagram,
            "final_output": self.extract_final_output(chunks),
            "events": chunks,
        }

    def graph_diagram_for_mode(self, agent_mode: str) -> str:
        """返回指定 Agent Loop 模式对应的 Mermaid 图。"""

        effective_mode = AGENT_LOOP_REACT if agent_mode == AGENT_LOOP_REACT else AGENT_LOOP_PLAN
        return self.graph_diagram_paths[effective_mode].read_text(encoding="utf-8")

    def graph_diagram_path_for_mode(self, agent_mode: str) -> str:
        """返回指定 Agent Loop 模式对应的 Mermaid 文件路径。"""

        effective_mode = AGENT_LOOP_REACT if agent_mode == AGENT_LOOP_REACT else AGENT_LOOP_PLAN
        return str(self.graph_diagram_paths[effective_mode])

    def list_registered_tools(self) -> dict[str, Any]:
        """
        返回当前 Agent 最终可用工具注册表快照。

        结果包含内置工具和配置启用的 MCP 工具;测试或外部注入 tools 时回退读取
        LangChain tool 对象的基础信息。
        """

        if self.tool_registry is not None:
            tools = [
                {
                    "name": definition.name,
                    "display_name": definition.display_name or definition.name,
                    "description": definition.description,
                    "args_schema": definition.args_schema,
                    "argument_count": len(definition.args_schema.get("properties", {})),
                }
                for definition in self.tool_registry.definitions.values()
            ]
        else:
            tools = [
                {
                    "name": str(getattr(tool, "name", "")),
                    "display_name": str(getattr(tool, "name", "")),
                    "description": str(getattr(tool, "description", "")),
                    "args_schema": (
                        getattr(tool, "args_schema").model_json_schema()
                        if getattr(tool, "args_schema", None) is not None
                        else {}
                    ),
                    "argument_count": len(getattr(getattr(tool, "args_schema", None), "model_fields", {}) or {}),
                }
                for tool in self.tools
            ]
        return {
            "tool_count": len(tools),
            "tools": sorted(tools, key=lambda item: item["name"]),
        }

    def run_session_prompt(
        self,
        *,
        prompt: str,
        user_id: str,
        session_id: str,
        reference: str | None = None,
        agent_mode: str = AGENT_LOOP_AUTO,
        agent_access_mode: str = "sandbox",
    ) -> dict[str, Any]:
        """
        运行带 session 上下文和消息持久化的一轮 Agent,返回结构化结果。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        reference: 用户明确引用的文档片段。
        agent_mode: Agent Loop 模式,支持 auto / simple / react / plan。兼容 deep 旧别名。
        """

        chunks = list(
            self.stream_session_prompt(
                prompt=prompt,
                user_id=user_id,
                session_id=session_id,
                reference=reference,
                agent_mode=agent_mode,
                agent_access_mode=agent_access_mode,
            )
        )
        effective_access_mode = normalize_agent_access_mode(agent_access_mode)
        effective_mode = self._extract_agent_mode_from_events(chunks) or self._resolve_agent_loop_mode_fallback(
            agent_mode=agent_mode,
            prompt=prompt,
            reference=reference,
        )
        diagram_mode = AGENT_LOOP_REACT if effective_mode == AGENT_LOOP_REACT else AGENT_LOOP_PLAN
        graph_diagram_path = self.graph_diagram_paths[diagram_mode]
        graph_diagram = graph_diagram_path.read_text(encoding="utf-8")
        return {
            "graph_diagram_path": str(graph_diagram_path),
            "graph_diagram": graph_diagram,
            "final_output": self.extract_final_output(chunks),
            "events": chunks,
            "agent_mode": effective_mode,
            "agent_access_mode": effective_access_mode,
        }

    def stream_session_prompt(
        self,
        *,
        prompt: str,
        user_id: str,
        session_id: str,
        reference: str | None = None,
        agent_mode: str = AGENT_LOOP_AUTO,
        agent_access_mode: str = "sandbox",
        web_search_max_results: int = 10,
    ) -> Iterator[dict[str, Any]]:
        """
        运行带 session 上下文和消息持久化的一轮 Agent,逐节点产出 dict 事件。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        reference: 用户引用的文本,作为额外上下文注入。
        agent_mode: Agent Loop 模式,支持 auto / simple / react / plan。兼容 deep 旧别名。
        web_search_max_results: 联网搜索每次最大结果数,用于系统提示词引导 agent 行为。
        """

        reference = reference.strip() if reference and reference.strip() else None
        effective_mode = self._resolve_agent_loop_mode(
            agent_mode=agent_mode,
            prompt=prompt,
            reference=reference,
            user_id=user_id,
        )
        effective_access_mode = normalize_agent_access_mode(agent_access_mode)
        message_service = self._get_message_service()
        context_builder = self._get_context_builder(message_service=message_service)
        logger.info(
            "开始 session 流式运行 | user=%s session=%s prompt_len=%d mode=%s requested_mode=%s",
            user_id,
            session_id,
            len(prompt),
            effective_mode,
            agent_mode,
        )
        messages = context_builder.build_messages(
            user_id=user_id, session_id=session_id, current_prompt=prompt, reference=reference,
            web_search_max_results=web_search_max_results,
        )
        turn_citation_map: dict[str, Any] = {}
        logger.debug("上下文构建完成 | message_count=%d", len(messages))

        initial_plan = self._load_session_plan(session_id) if effective_mode == AGENT_LOOP_PLAN else None

        for msg in messages:
            if isinstance(msg, SystemMessage):
                msg_create = self._message_to_create(
                    message=msg,
                    user_id=user_id,
                    session_id=session_id,
                    node_name="context_builder",
                )
                if msg_create is not None:
                    message_service.create_message(msg_create)
        message_service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=prompt,
                metadata_json={
                    "source": "stream_session_prompt",
                    **({"reference": reference} if reference else {}),
                },
            )
        )

        # 将系统提示作为首个 SSE 事件下发, 供前端 Obs 面板的上下文拼装卡片使用。
        # 系统消息不在图节点输出中, 不走常规 node 事件, 需要单独 yield。
        for msg in messages:
            if isinstance(msg, SystemMessage):
                rag_metrics = (getattr(msg, "additional_kwargs", {}) or {}).get("rag_metrics")
                recall_details = (getattr(msg, "additional_kwargs", {}) or {}).get("recall_details")
                citation_map = (recall_details or {}).get("citation_map", {})
                if citation_map:
                    turn_citation_map.update(citation_map)
                system_meta = {}
                if rag_metrics:
                    system_meta["rag_metrics"] = rag_metrics
                if recall_details:
                    system_meta["recall_details"] = recall_details
                if citation_map:
                    system_meta["citation_map"] = citation_map
                system_meta["agent_mode"] = effective_mode
                system_meta["requested_agent_mode"] = agent_mode
                system_meta["agent_access_mode"] = effective_access_mode
                yield {
                    "node": "context_builder",
                    "type": "system_prompt",
                    "content": AgentCore._stringify_content(msg.content),
                    "tool_calls": [],
                    "trace": [],
                    "model_name": "",
                    "metadata": system_meta,
                }
                break

        if effective_mode == AGENT_LOOP_SIMPLE:
            yield from self._stream_simple_answer(
                messages=messages,
                user_id=user_id,
                session_id=session_id,
                message_service=message_service,
                citation_map=turn_citation_map,
            )
            _launch_auto_rename(self, user_id=user_id, session_id=session_id)
            return

        yield from self._stream_events(
            messages=messages,
            user_id=user_id,
            session_id=session_id,
            message_service=message_service,
            initial_plan=initial_plan,
            graph=self.graphs[effective_mode],
            agent_mode=effective_mode,
            agent_access_mode=effective_access_mode,
            citation_map=turn_citation_map,
        )
        _launch_auto_rename(self, user_id=user_id, session_id=session_id)

    def cancel_session(self, session_id: str) -> None:
        """取消指定 session 正在执行的图,保存部分输出。"""

        with self._cancel_events_lock:
            event = self._cancel_events.get(session_id)
        if event is not None:
            logger.info("收到取消请求 | session=%s", session_id)
            event.set()

    def close(self) -> None:
        """释放 AgentCore 持有的调度器等资源。"""

        logger.info("AgentCore 正在释放调度器资源...")
        self.task_scheduler.shutdown()
        logger.info("AgentCore 资源释放完成")

    def _stream_events(
        self,
        *,
        messages: list[BaseMessage],
        user_id: str,
        session_id: str,
        message_service: MessageService | None = None,
        initial_plan: dict[str, Any] | None = None,
        graph: CompiledStateGraph | None = None,
        agent_mode: str = AGENT_LOOP_PLAN,
        agent_access_mode: str = "sandbox",
        citation_map: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        使用给定 LangChain messages 执行图并逐节点产出 dict 事件。

        统一的流式核心,HTTP 和 gRPC 共用此方法。
        支持通过 GeneratorExit (客户端断开 SSE) 或 cancel_session() 中断执行,
        中断时会保存当前已流式输出的部分内容到 agent_messages。

        messages: 已构建好的本轮初始上下文。
        user_id: 用户 ID。
        session_id: 会话 ID。
        message_service: 可选消息服务;传入时会持久化图节点新增消息。
        initial_plan: 可选上一轮的探索状态,跨轮注入。
        graph: 本轮使用的 LangGraph 图。
        agent_mode: 本轮 Agent Loop 模式。
        """

        # 在图启动前一次性读取用户 LLM 配置,存入 state 避免重入时重复查 DB
        llm_config = self._get_user_llm_config(user_id)
        inputs: dict[str, Any] = {
            "messages": messages,
            "user_id": user_id,
            "session_id": session_id,
            "trace": [],
            "llm_config": llm_config,
        }
        if initial_plan is not None:
            inputs["plan"] = initial_plan
        runtime_config = {"configurable": {"thread_id": session_id}}
        active_graph = graph or self.graphs.get(agent_mode) or self.graph
        effective_access_mode = normalize_agent_access_mode(agent_access_mode)
        retrieval_service = None
        if self.context_builder is not None:
            retrieval_service = self.context_builder.retrieval_service

        cancel_event = threading.Event()
        with self._cancel_events_lock:
            self._cancel_events[session_id] = cancel_event

        token_queue: queue_module.Queue[dict[str, Any]] = queue_module.Queue()
        _streamed_content: list[str] = [""]
        _turn_traces: list[dict[str, Any]] = []
        _citation_map: dict[str, Any] = dict(citation_map or {})
        _token_blocked: list[bool] = [False]
        _latest_plan: dict[str, Any] | None = initial_plan
        _last_sent_content: list[str] = [""]
        _last_node_completed_at: list[float] = [time.perf_counter()]


        def on_token(cumulative_text: str) -> None:
            if _token_blocked[0]:
                return
            content = AgentCore._sanitize_streaming_content(
                cumulative_text,
                min_chars=self.config.model.streaming_sanitize_min_chars,
            )
            content = AgentCore._strip_html_tags(content)
            _streamed_content[0] = content
            if content != cumulative_text:
                _token_blocked[0] = True
                delta = content
            else:
                prev = _last_sent_content[0]
                delta = content[len(prev):] if len(content) > len(prev) else content

            _last_sent_content[0] = content
            token_queue.put({
                "type": "token",
                "node": "agent",
                "content": delta,
                "tool_calls": [],
                "trace": [],
            })

        graph_error: Exception | None = None

        def on_tool_trace(trace: dict[str, Any]) -> None:
            token_queue.put({"type": "tool_trace", "trace": trace})

        def on_planner_content(cumulative_text: str) -> None:
            token_queue.put({
                "type": "planner_content",
                "node": "planner",
                "content": cumulative_text,
                "tool_calls": [],
                "trace": [],
            })

        def on_observation_content(cumulative_text: str) -> None:
            token_queue.put({
                "type": "observation_content",
                "node": "observation",
                "content": cumulative_text,
                "tool_calls": [],
                "trace": [],
            })

        def on_context_mirror(messages: list[dict[str, Any]]) -> None:
            token_queue.put({"type": "context_mirror", "messages": messages})

        def run_graph() -> None:
            nonlocal graph_error
            set_tool_runtime(
                config=self.config,
                user_id=user_id,
                session_id=session_id,
                retrieval_service=retrieval_service,
                citation_map=_citation_map,
                agent_access_mode=effective_access_mode,
            )
            set_agent_token_callback(on_token)
            set_tool_trace_callback(on_tool_trace)
            set_planner_content_callback(on_planner_content)
            set_observation_content_callback(on_observation_content)
            set_context_mirror_callback(on_context_mirror)
            set_plan_state(initial_plan)
            try:
                for event in active_graph.stream(inputs, config=runtime_config, stream_mode="updates"):
                    if cancel_event.is_set():
                        break
                    token_queue.put({"type": "node", "event": event})
            except Exception as exc:
                graph_error = exc
                token_queue.put({"type": "error", "error": exc})
            finally:
                clear_agent_token_callback()
                clear_tool_trace_callback()
                clear_planner_content_callback()
                clear_observation_content_callback()
                clear_context_mirror_callback()
                clear_plan_state()
                clear_tool_runtime()
                token_queue.put({"type": "done"})

        graph_thread = threading.Thread(target=run_graph, daemon=True, name=f"graph-{session_id[:12]}")
        graph_thread.start()

        try:
            while True:
                try:
                    item = token_queue.get(timeout=0.3)
                except queue_module.Empty:
                    if cancel_event.is_set():
                        partial = _streamed_content[0]
                        if message_service is not None and partial:
                            try:
                                message_service.create_message(
                                    MessageCreate(
                                        session_id=session_id,
                                        user_id=user_id,
                                        role="assistant",
                                        content=partial,
                                        metadata_json={"node": "agent", "source": "interrupted"},
                                    )
                                )
                                logger.info("已保存中断时的部分输出 | session=%s len=%d", session_id, len(partial))
                            except Exception:
                                logger.exception("保存中断输出失败 | session=%s", session_id)
                        break
                    continue

                item_type = item.get("type")

                if item_type == "done":
                    final_plan = get_plan_state()
                    self._persist_session_plan(session_id, final_plan)
                    break

                if item_type == "error":
                    error_msg = str(item["error"])
                    # 提取对用户友好的错误信息,去除冗余的技术细节
                    friendly_msg = _extract_friendly_error(error_msg)
                    logger.warning("图执行出错 | user=%s session=%s error=%s", user_id, session_id, friendly_msg)
                    if message_service is not None:
                        try:
                            message_service.create_message(
                                MessageCreate(
                                    session_id=session_id,
                                    user_id=user_id,
                                    role="assistant",
                                    content=friendly_msg,
                                    metadata_json={"node": "error", "source": "api_content_filter"},
                                )
                            )
                            logger.info("已保存错误消息到数据库 | session=%s", session_id)
                        except Exception:
                            logger.exception("保存错误消息失败 | session=%s", session_id)
                    yield {
                        "node": "error",
                        "content": friendly_msg,
                        "error": friendly_msg,
                        "tool_calls": [],
                        "trace": [],
                        "model_name": "",
                    }
                    break

                if item_type == "token":
                    yield {
                        "type": "delta",
                        "node": item.get("node", "agent"),
                        "content": item.get("content", ""),
                        "tool_calls": item.get("tool_calls", []),
                        "trace": item.get("trace", []),
                        "model_name": self._model_name_for_node(item.get("node", "agent")),
                    }

                elif item_type == "tool_trace":
                    trace = item.get("trace", {})
                    if trace:
                        trace_citation_map = trace.get("citation_map")
                        if isinstance(trace_citation_map, dict):
                            _citation_map.update(trace_citation_map)
                        if "model_name" not in trace:
                            trace["model_name"] = self._model_name_for_node(trace.get("node", "action"))
                        trace["ts"] = time.time()
                        trace["_streamed_trace"] = True
                        _turn_traces.append(trace)
                    public_trace = (
                        {key: value for key, value in trace.items() if not key.startswith("_")}
                        if trace
                        else {}
                    )
                    yield {
                        "node": trace.get("node", "action"),
                        "content": "",
                        "tool_calls": [],
                        "trace": [public_trace] if public_trace else [],
                        "model_name": self._model_name_for_node(trace.get("node", "action")),
                        "metadata": {"citation_map": dict(_citation_map)} if _citation_map else {},
                    }

                elif item_type == "planner_content":
                    yield {
                        "node": "planner",
                        "content": "",
                        "tool_calls": [],
                        "trace": [],
                        "model_name": self._model_name_for_node("planner"),
                    }

                elif item_type == "observation_content":
                    yield {
                        "node": "observation",
                        "content": "",
                        "tool_calls": [],
                        "trace": [],
                        "model_name": self._model_name_for_node("observation"),
                    }

                elif item_type == "context_mirror":
                    yield {
                        "node": "agent",
                        "type": "context_mirror",
                        "content": "",
                        "tool_calls": [],
                        "trace": [],
                        "model_name": self._model_name_for_node("agent"),
                        "context_messages": item.get("messages", []),
                    }

                elif item_type == "node":
                    event = item["event"]
                    for node_name, state_update in event.items():
                        completed_at = time.perf_counter()
                        duration_ms = max(0.01, round(max(0.0, completed_at - _last_node_completed_at[0]) * 1000, 2))
                        _last_node_completed_at[0] = completed_at
                        logger.debug("图节点执行 | node=%s user=%s session=%s", node_name, user_id, session_id)
                        node_traces = state_update.get("trace", []) if state_update else []
                        fresh_traces: list[dict[str, Any]] = []
                        if node_traces:
                            _now = time.time()
                            for t in node_traces:
                                if t.get("node") != node_name:
                                    continue
                                already_streamed = bool(t.get("_streamed_trace"))
                                if "ts" in t and not (already_streamed and not t.get("_persisted_trace")):
                                    continue
                                trace_citation_map = t.get("citation_map")
                                if isinstance(trace_citation_map, dict):
                                    _citation_map.update(trace_citation_map)
                                if "model_name" not in t:
                                    t["model_name"] = self._model_name_for_node(node_name)
                                if "ts" not in t:
                                    t["ts"] = _now
                                if not already_streamed:
                                    if t.get("event") == "tool_call_start":
                                        t["duration_ms"] = 0
                                    elif "duration_ms" not in t:
                                        t["duration_ms"] = duration_ms
                                t["_persisted_trace"] = True
                                fresh_traces.append(t)
                            _turn_traces.extend(fresh_traces)
                        if isinstance(state_update, dict) and "plan" in state_update:
                            _latest_plan = state_update["plan"]
                        public_fresh_traces = [
                            {key: value for key, value in trace.items() if not key.startswith("_")}
                            for trace in fresh_traces
                        ]
                        output_state_update = (
                            {**state_update, "trace": public_fresh_traces}
                            if isinstance(state_update, dict)
                            else state_update
                        )
                        if message_service is not None:
                            self._save_state_update_messages(
                                message_service=message_service,
                                user_id=user_id,
                                session_id=session_id,
                                node_name=node_name,
                                state_update=output_state_update,
                                turn_traces=public_fresh_traces,
                                citation_map=_citation_map,
                            )
                        payload = self._build_stream_payload(
                            node_name=node_name,
                            state_update=output_state_update,
                            citation_map=_citation_map,
                        )
                        payload["model_name"] = self._model_name_for_node(node_name)
                        yield payload
        except GeneratorExit:
            cancel_event.set()
            partial = _streamed_content[0]
            if message_service is not None and partial:
                try:
                    message_service.create_message(
                        MessageCreate(
                            session_id=session_id,
                            user_id=user_id,
                            role="assistant",
                            content=partial,
                            metadata_json={"node": "agent", "source": "interrupted"},
                        )
                    )
                    logger.info("已保存中断时的部分输出 | session=%s len=%d", session_id, len(partial))
                except Exception:
                    logger.exception("保存中断输出失败 | session=%s", session_id)
            raise
        finally:
            cancel_event.set()
            with self._cancel_events_lock:
                self._cancel_events.pop(session_id, None)
            clear_agent_token_callback()
            clear_tool_trace_callback()
            clear_planner_content_callback()
            clear_observation_content_callback()
            clear_plan_state()
            clear_tool_runtime()
            graph_thread.join(timeout=5.0)

    def _get_message_service(self) -> MessageService:
        """获取或懒加载消息服务。"""

        if self.message_service is None:
            self.message_service = MessageService(config=self.config)
        return self.message_service

    def _get_context_builder(self, *, message_service: MessageService) -> ContextBuilder:
        """获取或懒加载短期上下文构建器。"""

        if self.context_builder is None:
            self.context_builder = ContextBuilder(
                config=self.config,
                message_service=message_service,
                attachment_service=self.attachment_service,
            )
        return self.context_builder

    def _stream_simple_answer(
        self,
        *,
        messages: list[BaseMessage],
        user_id: str,
        session_id: str,
        message_service: MessageService,
        citation_map: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        对明显不需要工具的短输入走轻量直答路径。

        这条路径仍然使用 ContextBuilder 的消息、用户自定义系统提示词和消息持久化,
        但绕过 planner/action/observation graph loop,避免一次简单问候触发多次 LLM 请求。
        """

        system_content = self._build_runtime_system_prompt(user_id=user_id)
        llm_config = self._get_user_llm_config(user_id) or {}
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")
        model_name = llm_config.get("model_name")
        small_api_key = llm_config.get("small_api_key") or api_key
        small_base_url = llm_config.get("small_base_url") or base_url
        small_model_name = llm_config.get("small_model_name") or model_name
        runtime_messages = [SystemMessage(content=system_content), *messages]
        cumulative = ""
        last_sent_content = ""
        final_message: BaseMessage | None = None
        user_prompt = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_prompt = AgentCore._stringify_content(msg.content)
                break

        try:
            logger.info("启用短问直答路径 | user=%s session=%s msg_count=%d", user_id, session_id, len(runtime_messages))
            safety_started_at = time.perf_counter()
            input_audit = self.safety_service.audit_input(user_prompt, llm_config=llm_config)
            safety_input_trace = {
                "node": "safety_input",
                "event": "blocked" if input_audit.blocked else "passed",
                "model_tier": "runtime",
                "category": "political" if input_audit.is_political else "general",
                "message": input_audit.block_reason if input_audit.blocked else "输入安全审核通过",
                "human_readable": input_audit.block_reason if input_audit.blocked else "输入安全审核通过。",
                "duration_ms": max(0.01, round((time.perf_counter() - safety_started_at) * 1000, 2)),
                "chat_visible": False,
            }
            message_service.create_message(
                MessageCreate(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content="",
                    metadata_json={
                        "node": "safety_input",
                        "source": "simple_answer_safety",
                        "trace": [safety_input_trace],
                    },
                )
            )
            yield {
                "node": "safety_input",
                "content": "",
                "tool_calls": [],
                "trace": [safety_input_trace],
                "model_name": "",
            }
            if input_audit.blocked:
                block_message = self.safety_service.generate_block_message(
                    input_audit,
                    user_prompt,
                    llm_config=llm_config,
                )
                message_service.create_message(
                    MessageCreate(
                        session_id=session_id,
                        user_id=user_id,
                        role="assistant",
                        content=block_message,
                        metadata_json={
                            "node": "safety_input",
                            "source": "simple_answer_safety_block",
                            "trace": [safety_input_trace],
                        },
                    )
                )
                yield {
                    "node": "safety_input",
                    "content": block_message,
                    "tool_calls": [],
                    "trace": [],
                    "model_name": "",
                }
                return
            started_at = time.perf_counter()
            yield {
                "node": "agent",
                "type": "context_mirror",
                "content": "",
                "tool_calls": [],
                "trace": [],
                "model_name": self._model_name_for_node("agent_simple"),
                "context_messages": self._serialize_runtime_messages(runtime_messages),
            }
            for chunk in self.task_scheduler.stream_chat(
                task_type=FOREGROUND_AGENT_TASK,
                messages=runtime_messages,
                tool_names=[],
                model_tier=SMALL_MODEL_TIER,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                small_api_key=small_api_key,
                small_base_url=small_base_url,
                small_model_name=small_model_name,
            ):
                if chunk.get("status") == "complete":
                    final_message = chunk.get("message")
                    continue
                delta = chunk.get("content_delta", "")
                if not delta:
                    continue
                cumulative += delta
                safe_content = AgentCore._sanitize_streaming_content(
                    cumulative,
                    min_chars=self.config.model.streaming_sanitize_min_chars,
                )
                safe_content = AgentCore._strip_html_tags(safe_content)
                output_delta = safe_content[len(last_sent_content):] if len(safe_content) > len(last_sent_content) else safe_content
                if not output_delta:
                    last_sent_content = safe_content
                    continue
                last_sent_content = safe_content
                yield {
                    "type": "delta",
                    "node": "agent",
                    "content": output_delta,
                    "tool_calls": [],
                    "trace": [],
                    "model_name": self._model_name_for_node("agent_simple"),
                }

            content = AgentCore._stringify_content(getattr(final_message, "content", "") if final_message is not None else cumulative)
            content = AgentCore._sanitize_agent_output(content)
            content = AgentCore._strip_html_tags(content)
            content = AgentCore._drop_unmapped_citation_anchors(content, citation_map)
            content = AgentCore._insert_missing_citation_anchors_inline(content, citation_map)
            citation_metadata = AgentCore._build_citation_metadata(content, citation_map)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            token_usage = extract_token_usage(final_message)
            simple_trace = {
                "node": "agent",
                "event": "simple_answer",
                "human_readable": "短输入直接生成回复，未进入工具循环。",
                "model_tier": SMALL_MODEL_TIER,
                "model_name": self._model_name_for_node("agent_simple"),
                "duration_ms": duration_ms,
                "token_usage": token_usage,
            }
            output_safety_started_at = time.perf_counter()
            output_audit = self.safety_service.audit_output(content, user_input=user_prompt)
            if output_audit.blocked or output_audit.sanitized:
                content = output_audit.safe_output
                citation_metadata = AgentCore._build_citation_metadata(content, citation_map)
            safety_output_trace = {
                "node": "safety_output",
                "event": output_audit.verdict if (output_audit.blocked or output_audit.sanitized) else "passed",
                "model_tier": "runtime",
                "message": output_audit.reason if (output_audit.blocked or output_audit.sanitized) else "输出安全审核通过",
                "human_readable": output_audit.reason if (output_audit.blocked or output_audit.sanitized) else "输出安全审核通过。",
                "duration_ms": max(0.01, round((time.perf_counter() - output_safety_started_at) * 1000, 2)),
                "chat_visible": False,
            }
            message_service.create_message(
                MessageCreate(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=content,
                    metadata_json={
                        "node": "agent",
                        "source": "simple_answer_mode",
                        "trace": [simple_trace, safety_output_trace],
                        **citation_metadata,
                    },
                )
            )
            yield {
                "node": "agent",
                "content": content,
                "tool_calls": [],
                "trace": [simple_trace, safety_output_trace],
                "model_name": self._model_name_for_node("agent_simple"),
                "metadata": citation_metadata,
            }
        except GeneratorExit:
            raise
        except Exception as exc:
            friendly_msg = _extract_friendly_error(str(exc))
            logger.warning("短问直答出错 | user=%s session=%s error=%s", user_id, session_id, friendly_msg)
            message_service.create_message(
                MessageCreate(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=friendly_msg,
                    metadata_json={"node": "error", "source": "simple_answer_mode"},
                )
            )
            yield {
                "node": "error",
                "content": friendly_msg,
                "error": friendly_msg,
                "tool_calls": [],
                "trace": [],
                "model_name": "",
            }

    @staticmethod
    def _should_use_simple_answer_mode(*, prompt: str, reference: str | None = None) -> bool:
        """判断本轮是否可以跳过 Agent Loop,直接轻量回复。"""

        if reference:
            return False
        text = (prompt or "").strip()
        if not text:
            return False
        normalized = text.lower()
        simple_exact = {
            "hi",
            "hello",
            "hey",
            "ok",
            "okay",
            "thanks",
            "thank you",
            "你好",
            "您好",
            "在吗",
            "谢谢",
            "好的",
            "好",
            "嗯",
            "？",
            "?",
        }
        if normalized in simple_exact:
            return True
        if len(text) > 16:
            return False
        toolish_keywords = (
            "搜索",
            "查找",
            "查询",
            "打开",
            "读取",
            "文件",
            "知识库",
            "图谱",
            "记住",
            "长期",
            "规则",
            "写入",
            "删除",
            "重命名",
            "复制",
            "剪切",
            "粘贴",
            "灌库",
            "入库",
            "总结文档",
            "pdf",
            "docx",
            "xlsx",
            "ppt",
            "csv",
            "代码",
            "运行",
            "工具",
        )
        return not any(keyword in normalized for keyword in toolish_keywords)

    @staticmethod
    def _should_use_plan_mode(*, prompt: str, reference: str | None = None) -> bool:
        """判断 auto 模式下是否需要进入带 planner/observation 的规划图。"""

        if reference:
            return True
        text = (prompt or "").strip()
        if not text:
            return False
        normalized = text.lower()
        if len(text) >= 80:
            return True
        plan_keywords = (
            "计划",
            "规划",
            "方案",
            "步骤",
            "拆解",
            "分析",
            "比较",
            "评估",
            "调研",
            "排查",
            "诊断",
            "设计",
            "实现",
            "重构",
            "优化",
            "修复",
            "完成",
            "整理",
            "总结",
            "写文档",
            "多步骤",
            "一步一步",
            "从头到尾",
            "先",
            "然后",
            "最后",
            "todo",
        )
        return any(keyword in normalized for keyword in plan_keywords)

    def _resolve_agent_loop_mode(
        self,
        *,
        agent_mode: str | None,
        prompt: str,
        reference: str | None = None,
        user_id: str = "",
    ) -> str:
        """把外部请求模式归一为本轮实际执行模式。auto 模式优先由小模型分类。"""

        requested = (agent_mode or AGENT_LOOP_AUTO).strip().lower()
        explicit_mode = AgentCore._normalize_explicit_agent_loop_mode(requested)
        if explicit_mode is not None:
            return explicit_mode
        classified_mode = self._classify_agent_loop_mode_with_small_model(
            prompt=prompt,
            reference=reference,
            user_id=user_id,
        )
        if classified_mode is not None:
            return classified_mode
        return AgentCore._resolve_agent_loop_mode_fallback(
            agent_mode=requested,
            prompt=prompt,
            reference=reference,
        )

    @staticmethod
    def _normalize_explicit_agent_loop_mode(requested: str) -> str | None:
        """返回用户显式指定的模式;auto 返回 None。"""

        if requested == AGENT_LOOP_SIMPLE:
            return AGENT_LOOP_SIMPLE
        if requested == AGENT_LOOP_REACT:
            return AGENT_LOOP_REACT
        if requested in {AGENT_LOOP_PLAN, AGENT_LOOP_DEEP_ALIAS}:
            return AGENT_LOOP_PLAN
        return None

    @staticmethod
    def _resolve_agent_loop_mode_fallback(
        *,
        agent_mode: str | None,
        prompt: str,
        reference: str | None = None,
    ) -> str:
        """小模型路由不可用时的保守回退规则。"""

        requested = (agent_mode or AGENT_LOOP_AUTO).strip().lower()
        explicit_mode = AgentCore._normalize_explicit_agent_loop_mode(requested)
        if explicit_mode is not None:
            return explicit_mode
        if AgentCore._should_use_plan_mode(prompt=prompt, reference=reference):
            return AGENT_LOOP_PLAN
        if AgentCore._should_use_simple_answer_mode(prompt=prompt, reference=reference):
            return AGENT_LOOP_SIMPLE
        return AGENT_LOOP_REACT

    def _classify_agent_loop_mode_with_small_model(
        self,
        *,
        prompt: str,
        reference: str | None = None,
        user_id: str = "",
    ) -> str | None:
        """使用小模型判断 auto 模式下应进入 simple/react/plan 哪张图。"""

        text = (prompt or "").strip()
        if not text:
            return None
        llm_config = self._get_user_llm_config(user_id) or {}
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")
        model_name = llm_config.get("model_name")
        small_api_key = llm_config.get("small_api_key") or api_key
        small_base_url = llm_config.get("small_base_url") or base_url
        small_model_name = llm_config.get("small_model_name") or model_name
        system_prompt = (
            "你是 Agent Loop 路由器。只输出 JSON,不要输出解释。\n"
            "根据用户请求选择一个模式:\n"
            "- simple: 只适合寒暄、确认、极短且你有把握直接回答的常识性闲聊。"
            "必须同时满足: 不需要工具、不需要最新信息、不需要读文件、不需要事实核验、你自己能力足够。\n"
            "- react: 需要调用工具、搜索、读取知识库/文件、获取最近/最新/当前信息,或一步到几步即可完成的任务。\n"
            "- plan: 需要多步骤规划、复杂分析、调研、比较、排查、设计、实现、重构、修复或整理。\n"
            "只要你不确定自己能否可靠回答,或可能需要外部信息/工具核验,就不要选择 simple,至少选择 react。\n"
            "如果用户问最近、最新、今天、现在、当前发生了什么,即使句子很短也必须选择 react。\n"
            "如果不确定,选择 react。输出格式: {\"mode\":\"simple|react|plan\",\"reason\":\"简短原因\"}"
        )
        user_prompt = (
            f"用户请求:\n{text}\n\n"
            f"是否带显式引用片段: {'是' if reference else '否'}\n"
            "请给出路由 JSON。"
        )
        try:
            response = self.task_scheduler.invoke_chat(
                task_type=FOREGROUND_AGENT_TASK,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ],
                tool_names=[],
                model_tier=SMALL_MODEL_TIER,
                temperature=0.0,
                timeout_seconds=12,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                small_api_key=small_api_key,
                small_base_url=small_base_url,
                small_model_name=small_model_name,
            )
        except Exception:
            logger.warning("小模型 Agent Loop 路由失败,回退到本地规则 | user=%s", user_id, exc_info=True)
            return None
        mode = AgentCore._parse_agent_loop_route_response(AgentCore._stringify_content(response.content))
        if mode is None:
            logger.warning("小模型 Agent Loop 路由输出无法解析,回退到本地规则 | output=%s", response.content)
        return mode

    @staticmethod
    def _parse_agent_loop_route_response(content: str) -> str | None:
        """解析小模型路由输出。"""

        text = (content or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        if "{" in text and "}" in text:
            text = text[text.find("{"):text.rfind("}") + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        mode = str(data.get("mode", "") or "").strip().lower()
        if mode in {AGENT_LOOP_SIMPLE, AGENT_LOOP_REACT, AGENT_LOOP_PLAN}:
            return mode
        if mode == AGENT_LOOP_DEEP_ALIAS:
            return AGENT_LOOP_PLAN
        return None

    @staticmethod
    def _extract_agent_mode_from_events(events: list[dict[str, Any]]) -> str | None:
        """从 stream_session_prompt 事件中读取本轮实际执行模式。"""

        for event in events:
            metadata = event.get("metadata")
            if not isinstance(metadata, dict):
                continue
            mode = str(metadata.get("agent_mode", "") or "").strip().lower()
            if mode in {AGENT_LOOP_SIMPLE, AGENT_LOOP_REACT, AGENT_LOOP_PLAN}:
                return mode
        return None

    def _build_runtime_system_prompt(self, *, user_id: str) -> str:
        """构造运行时系统提示词,与模型决策节点保持一致。"""

        system_content = self.config.model.system_prompt
        if not user_id:
            return system_content
        try:
            from agent_service.api.rest.deps import _settings_service
            if _settings_service is not None:
                custom_prompt = _settings_service.get_system_prompt(user_id=user_id)
                if custom_prompt:
                    system_content += f"\n\n【用户自定义指令】\n{custom_prompt}"
        except Exception:
            logger.debug("读取用户自定义系统提示词失败 | user=%s", user_id, exc_info=True)
        return system_content

    @staticmethod
    def _serialize_runtime_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
        """序列化直答路径实际发送给模型的上下文,供观测面板展示。"""

        role_map = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}
        result: list[dict[str, Any]] = []
        for msg in messages:
            result.append(
                {
                    "role": role_map.get(msg.type, msg.type),
                    "content": AgentCore._stringify_content(getattr(msg, "content", "")),
                }
            )
        return result

    def _save_state_update_messages(
        self,
        *,
        message_service: MessageService,
        user_id: str,
        session_id: str,
        node_name: str,
        state_update: dict[str, Any] | None,
        turn_traces: list[dict[str, Any]] | None = None,
        citation_map: dict[str, Any] | None = None,
    ) -> None:
        """
        将图节点返回的新增消息保存为 MessageRecord。

        message_service: 消息服务。
        user_id: 用户 ID。
        session_id: 会话 ID。
        node_name: 当前节点名称。
        state_update: LangGraph 节点返回的状态更新。
        turn_traces: 本轮截至当前节点累积的所有 trace,用于附加到 assistant 消息 metadata 中。
        """

        if not state_update:
            return
        messages = state_update.get("messages", [])
        if (not messages or node_name in {"planner", "observation", "compress"}) and turn_traces:
            message_service.create_message(
                MessageCreate(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content="",
                    metadata_json={
                        "node": node_name,
                        "source": "agent_graph_trace",
                        "trace": turn_traces,
                    },
                )
            )
            return
        for message in messages:
            message_create = self._message_to_create(
                message=message,
                user_id=user_id,
                session_id=session_id,
                node_name=node_name,
                turn_traces=turn_traces,
                citation_map=citation_map,
            )
            if message_create is not None:
                message_service.create_message(message_create)

    @staticmethod
    def _message_to_create(
        *,
        message: BaseMessage,
        user_id: str,
        session_id: str,
        node_name: str,
        turn_traces: list[dict[str, Any]] | None = None,
        citation_map: dict[str, Any] | None = None,
    ) -> MessageCreate | None:
        """
        将 LangChain message 转换为 MessageCreate。

        message: LangGraph 节点返回的新增消息。
        user_id: 用户 ID。
        session_id: 会话 ID。
        node_name: 产生该消息的节点名称。
        turn_traces: 本轮累积的 trace,附加到 assistant 消息 metadata 中。
        """

        metadata: dict[str, Any] = {"node": node_name, "source": "agent_graph"}
        if turn_traces:
            metadata["trace"] = turn_traces
        if isinstance(message, AIMessage):
            reasoning_content = (message.additional_kwargs or {}).get("reasoning_content")
            if reasoning_content:
                metadata["reasoning_content"] = reasoning_content
            content = AgentCore._sanitize_agent_output(AgentCore._stringify_content(message.content))
            content = AgentCore._drop_unmapped_citation_anchors(content, citation_map)
            content = AgentCore._insert_missing_citation_anchors_inline(content, citation_map)
            metadata.update(AgentCore._build_citation_metadata(content, citation_map))
            if not content.strip() and not list(message.tool_calls or []):
                return None
            return MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=content,
                tool_calls_json=list(message.tool_calls or []),
                metadata_json=metadata,
            )
        if isinstance(message, ToolMessage):
            return MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="tool",
                content=AgentCore._stringify_content(message.content),
                tool_call_id=message.tool_call_id,
                metadata_json=metadata,
            )
        if isinstance(message, HumanMessage):
            return MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=AgentCore._stringify_content(message.content),
                metadata_json=metadata,
            )
        if isinstance(message, SystemMessage):
            rag_metrics = (getattr(message, "additional_kwargs", {}) or {}).get("rag_metrics")
            if rag_metrics:
                metadata["rag_metrics"] = rag_metrics
            recall_details = (getattr(message, "additional_kwargs", {}) or {}).get("recall_details")
            if recall_details:
                metadata["recall_details"] = recall_details
            return MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="system",
                content=AgentCore._stringify_content(message.content),
                metadata_json=metadata,
            )
        return None

    @staticmethod
    def _extract_used_citation_ids(content: str) -> list[str]:
        """Extract citation anchors that appear in the final assistant text."""

        used: list[str] = []
        seen: set[str] = set()
        for match in CITATION_ANCHOR_PATTERN.finditer(content or ""):
            citation_id = match.group(1)
            if citation_id not in seen:
                used.append(citation_id)
                seen.add(citation_id)
        return used

    @staticmethod
    def _build_citation_metadata(
        content: str,
        citation_map: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build per-message citation metadata from anchors actually used."""

        if not citation_map:
            return {}
        used_citations = AgentCore._extract_used_citation_ids(content)
        if not used_citations:
            used_citations = [
                citation_id
                for citation_id, source in citation_map.items()
                if isinstance(source, dict) and source.get("adopted_by_default") is True
            ]
        if not used_citations:
            return {}
        filtered_map = {
            citation_id: citation_map[citation_id]
            for citation_id in used_citations
            if citation_id in citation_map
        }
        if not filtered_map:
            return {}
        return {
            "used_citations": [citation_id for citation_id in used_citations if citation_id in filtered_map],
            "citation_map": filtered_map,
        }

    @staticmethod
    def _drop_unmapped_citation_anchors(
        content: str,
        citation_map: dict[str, Any] | None,
    ) -> str:
        """Remove citation anchors that do not resolve to this turn's citation map."""

        if not content or citation_map is None:
            return content

        def replace_unmapped(match: re.Match[str]) -> str:
            citation_id = match.group(1)
            return match.group(0) if citation_id in citation_map else ""

        return CITATION_ANCHOR_PATTERN.sub(replace_unmapped, content)

    @staticmethod
    def _insert_missing_citation_anchors_inline(
        content: str,
        citation_map: dict[str, Any] | None,
    ) -> str:
        """Insert omitted adopted citation anchors beside matching document lines."""

        if not content or not citation_map:
            return content
        existing_ids = set(AgentCore._extract_used_citation_ids(content))
        adopted_sources = [
            (citation_id, source)
            for citation_id, source in citation_map.items()
            if isinstance(source, dict) and source.get("adopted_by_default") is True
            and citation_id not in existing_ids
        ]
        if not adopted_sources:
            return content
        lines = content.splitlines()
        changed = False
        for citation_id, source in adopted_sources:
            terms = AgentCore._citation_match_terms(source)
            if not terms:
                continue
            for index, line in enumerate(lines):
                if f"[{citation_id}]" in line:
                    break
                normalized_line = AgentCore._normalize_citation_match_text(line)
                if any(term in normalized_line for term in terms):
                    lines[index] = f"{line.rstrip()} [{citation_id}]"
                    changed = True
                    break
        return "\n".join(lines) if changed else content

    @staticmethod
    def _citation_match_terms(source: dict[str, Any]) -> list[str]:
        """Build conservative line-match terms for a citation source."""

        terms: list[str] = []
        source_uri = str(source.get("source_uri") or "")
        basename = re.split(r"[\\/]", source_uri)[-1]
        stem = re.sub(r"\.[^.]+$", "", basename)
        raw_terms = [basename, stem]
        if stem:
            raw_terms.append(re.sub(r"^\d+[_\-\s]*", "", stem).replace("_", " ").replace("-", " "))
            raw_terms.append(re.sub(r"^\d+[_\-\s]*", "", stem).replace("_", "").replace("-", ""))
        content = str(source.get("content") or "")
        for line in content.splitlines()[:12]:
            stripped = line.strip()
            if stripped.startswith("#"):
                raw_terms.append(stripped.lstrip("#").strip())
                break
        seen: set[str] = set()
        for term in raw_terms:
            normalized = AgentCore._normalize_citation_match_text(term)
            if len(normalized) < 3 or normalized in seen:
                continue
            terms.append(normalized)
            seen.add(normalized)
        return terms

    @staticmethod
    def _normalize_citation_match_text(value: str) -> str:
        """Normalize text for conservative source-line matching."""

        return value.replace("\\_", "_").replace("`", "").strip().casefold()

    @staticmethod
    def _stringify_content(content: Any) -> str:
        """
        将 LangChain message content 转成可持久化字符串。

        content: LangChain message 的 content 字段,可能是字符串或多模态列表。
        """

        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False)

    @staticmethod
    def parse_stream_chunks(chunks: list[str]) -> list[dict[str, Any]]:
        """
        将 AgentCore 的 SSE 风格字符串解析为事件字典列表。

        chunks: `AgentCore.stream_run()` 输出的原始字符串列表。
        """

        events: list[dict[str, Any]] = []
        for chunk in chunks:
            data = chunk.removeprefix("data: ").strip()
            if not data or data == "[DONE]":
                continue
            events.append(json.loads(data))
        return events

    @staticmethod
    def extract_final_output(events: list[dict[str, Any]]) -> str:
        """
        从事件列表中提取最终智能体回复。

        events: 由 `parse_stream_chunks()` 解析出的事件列表。
        """

        final_output = ""
        for event in events:
            is_agent_message = event.get("node") == "agent"
            has_tool_calls = bool(event.get("tool_calls"))
            content = event.get("content", "")
            if is_agent_message and content and not has_tool_calls:
                final_output = content
        return final_output

    @staticmethod
    def build_human_readable_process(events: list[dict[str, Any]]) -> list[str]:
        """
        构建给人阅读的可观测执行过程。

        events: 由 `parse_stream_chunks()` 解析出的事件列表。
        """

        process_lines: list[str] = []
        for index, event in enumerate(events, start=1):
            node_name = event.get("node", "")
            content = event.get("content", "")
            tool_calls = event.get("tool_calls", [])
            if node_name == "agent" and tool_calls:
                tool_names = ", ".join(tool_call.get("name", "") for tool_call in tool_calls)
                process_lines.append(f"{index}. 模型决定调用工具: {tool_names}")
            elif node_name == "action":
                process_lines.append(f"{index}. 工具执行完成,返回内容: {content}")
            elif node_name == "agent" and content:
                process_lines.append(f"{index}. 模型生成最终回复。")
            elif node_name == "compress":
                process_lines.append(f"{index}. 压缩节点执行: {event.get('trace', [])}")
            elif node_name == "summary":
                process_lines.append(f"{index}. 摘要节点执行: {event.get('trace', [])}")
        return process_lines

    def _model_name_for_node(self, node_name: str) -> str:
        """根据节点名返回对应的模型名称，供前端展示。"""
        small_nodes = {"planner", "observation", "agent_simple", "compress", "summary"}
        runtime_nodes = {"action", "context_builder", "safety_input", "safety_output", "error", "interrupted"}
        if node_name in runtime_nodes:
            return ""
        if node_name in small_nodes and self.config.model.small_model_name:
            return self.config.model.small_model_name
        return self.config.model.model_name

    @staticmethod
    def _get_user_llm_config(user_id: str) -> dict[str, Any] | None:
        """读取用户的 LLM 配置（api_key, base_url 等），在图启动前一次性获取，避免重入竞态。"""
        if not user_id:
            return None
        try:
            from agent_service.api.rest.deps import _settings_service
            if _settings_service is None:
                return None
            return _settings_service.get_llm_config(user_id=user_id)
        except Exception:
            return None

    @staticmethod
    def _build_stream_payload(
        *,
        node_name: str,
        state_update: dict[str, Any] | None,
        citation_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """把 LangGraph 节点更新转换为稳定的流式输出结构。"""

        if not state_update:
            return {"node": node_name, "content": "", "tool_calls": [], "trace": []}

        messages = state_update.get("messages", [])
        last_message = messages[-1] if messages else None
        content = getattr(last_message, "content", "") if last_message is not None else ""
        tool_calls = getattr(last_message, "tool_calls", []) if last_message is not None else []
        if node_name in {"planner", "observation", "action"}:
            content = ""
            tool_calls = []
        content = AgentCore._sanitize_agent_output(content or "")
        content = AgentCore._strip_html_tags(content)
        content = AgentCore._drop_unmapped_citation_anchors(content, citation_map)
        content = AgentCore._insert_missing_citation_anchors_inline(content, citation_map)
        metadata = AgentCore._build_citation_metadata(content, citation_map)
        return {
            "node": node_name,
            "content": content,
            "tool_calls": tool_calls or [],
            "trace": state_update.get("trace", []),
            "metadata": metadata,
        }

    @staticmethod
    def _sanitize_streaming_content(cumulative_text: str, min_chars: int = 20) -> str:
        """
        流式 token 级的 JSON 检测,仅在累积足够长度后才拦截。

        cumulative_text: 当前已累积的全部文本。
        min_chars: JSON 检测最低字符数,低于此值跳过 JSON 语法检查。
        """
        if not cumulative_text:
            return cumulative_text
        stripped = cumulative_text.strip()
        import re
        if re.match(r"^\[[A-Za-z一-鿿]+\]", stripped):
            logger.warning("流式输出中检测到内部标记格式,已拦截: %s", stripped[:60])
            return "（系统拦截了内部标记格式的输出，请用自然语言重新回答。）"
        if len(stripped) < min_chars:
            return cumulative_text
        if stripped.startswith("```json") or stripped.startswith("```JSON"):
            return "（系统拦截了原始 JSON 输出，请用自然语言重新回答。）"
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(stripped)
                logger.warning("流式输出中检测到完整 JSON,已拦截")
                return "（系统拦截了原始 JSON 输出，请用自然语言重新回答。）"
            except (json.JSONDecodeError, ValueError):
                pass
        return cumulative_text

    @staticmethod
    def _strip_html_tags(content: str) -> str:
        """
        统一剥离所有 HTML 标签和实体编码, 不分 fence 内外。
        DeepSeek 可能在 fence 内注入已高亮的 hljs span,
        本方法将其彻底还原为纯文本, 由前端 marked+highlight.js 重新高亮。
        """
        import html as _html
        import re as _re

        if not content or not isinstance(content, str):
            return content

        # 深度解码: 循环 unescape 直到稳定 (处理多层 &amp;amp;lt; 嵌套)
        prev = content
        for _ in range(10):
            decoded = _html.unescape(prev)
            if decoded == prev:
                break
            prev = decoded

        # 剥离所有 HTML 标签
        return _re.sub(r"<[^>]*>", "", prev)

    @staticmethod
    def _sanitize_agent_output(content: str) -> str:
        """
        检测并拦截 agent 输出中的原始 JSON,强制返回自然语言提示。

        content: agent 节点输出的文本内容。
        """
        if not content:
            return content
        stripped = content.strip()
        if stripped.startswith("```json") or stripped.startswith("```JSON"):
            logger.warning("Agent 输出包含 JSON 代码块,已拦截")
            return "（系统拦截了原始 JSON 输出，请用自然语言重新回答。）"
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(stripped)
                logger.warning("Agent 输出包含原始 JSON 字符串,已拦截")
                return "（系统拦截了原始 JSON 输出，请用自然语言重新回答。）"
            except (json.JSONDecodeError, ValueError):
                pass
        import re
        if re.match(r"^\[[A-Za-z一-鿿]+\]", stripped):
            logger.warning("Agent 输出包含内部标记格式,已拦截: %s", stripped[:60])
            return "（系统拦截了内部标记格式的输出，请用自然语言重新回答。）"
        return content

    def _load_session_plan(self, session_id: str) -> dict[str, Any] | None:
        """从 DB 加载会话的探索状态,跨轮恢复 planner 的上下文。"""

        if self.session_service is None:
            return None
        state_json = self.session_service.get_session_state(session_id)
        if not state_json:
            return None
        try:
            return json.loads(state_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("会话状态 JSON 解析失败 | session=%s", session_id)
            return None

    def _persist_session_plan(self, session_id: str, plan: dict[str, Any] | None) -> None:
        """将探索状态持久化到 DB,供下一轮恢复。"""

        if self.session_service is None:
            return
        if plan is None:
            self.session_service.update_session_state(session_id, None)
            return
        state_json = json.dumps(plan, ensure_ascii=False)
        self.session_service.update_session_state(session_id, state_json)


def _rename_session_worker(agent: AgentCore, *, user_id: str, session_id: str) -> str | None:
    """生成会话标题并持久化到 DB。优先用小模型,失败时自动降级大模型。"""
    try:
        message_service = agent._get_message_service()
        recent = message_service.list_recent_messages(
            user_id=user_id, session_id=session_id, limit=6,
            include_summarized=True,
        )
        if len(recent) < 2:
            return None
        for message in reversed(recent):
            if getattr(message, "role", "") != "assistant":
                continue
            content = (getattr(message, "content", "") or "").strip()
            metadata = getattr(message, "metadata_json", None) or {}
            if metadata.get("node") == "error" or "429 Too Many Requests" in content or "模型服务限流" in content:
                logger.info("跳过会话自动重命名 | session=%s reason=last_assistant_error", session_id)
                return None
            break
        lines: list[str] = []
        for m in recent[-6:]:
            role_label = ""
            if m.role == "user":
                role_label = "用户"
            elif m.role == "assistant":
                role_label = "助手"
            if not role_label:
                continue
            content_preview = (m.content or "")[:200].replace("\n", " ")
            lines.append(f"{role_label}: {content_preview}")
        if not lines:
            return None
        conversation = "\n".join(lines)
        rename_prompt = (
            "根据以下对话内容,为这个会话生成一个简洁的标题(15字以内,中文):\n\n"
            f"{conversation}\n\n标题:"
        )
        llm_config = agent._get_user_llm_config(user_id)
        api_key = llm_config.get("api_key") if llm_config else None
        base_url = llm_config.get("base_url") if llm_config else None
        model_name = llm_config.get("model_name") if llm_config else None
        small_api_key = (llm_config.get("small_api_key") or api_key) if llm_config else None
        small_base_url = (llm_config.get("small_base_url") or base_url) if llm_config else None
        small_model_name = (llm_config.get("small_model_name") or model_name) if llm_config else None

        title = _do_rename_llm_call(agent, rename_prompt, session_id,
            model_tier=SMALL_MODEL_TIER,
            api_key=api_key, base_url=base_url, model_name=model_name,
            small_api_key=small_api_key, small_base_url=small_base_url, small_model_name=small_model_name)
        if title is not None:
            return _persist_rename_title(agent, session_id, title)

        logger.info("小模型重命名失败,降级使用大模型 | session=%s", session_id)
        title = _do_rename_llm_call(agent, rename_prompt, session_id,
            model_tier=LARGE_MODEL_TIER,
            api_key=api_key, base_url=base_url, model_name=model_name)
        if title is not None:
            return _persist_rename_title(agent, session_id, title)
        return None
    except Exception:
        logger.info("会话自动重命名失败 | session=%s", session_id, exc_info=True)
        return None


def _do_rename_llm_call(
    agent: AgentCore, prompt: str, session_id: str, *,
    model_tier: str,
    api_key: str | None = None, base_url: str | None = None, model_name: str | None = None,
    small_api_key: str | None = None, small_base_url: str | None = None, small_model_name: str | None = None,
) -> str | None:
    """调用 LLM 生成会话标题,返回标题或 None。"""
    try:
        response = agent.task_scheduler.invoke_chat(
            task_type=BACKGROUND_SUMMARY_TASK,
            messages=[HumanMessage(content=prompt)],
            tool_names=[],
            model_tier=model_tier,
            temperature=0.3,
            api_key=api_key, base_url=base_url, model_name=model_name,
            small_api_key=small_api_key, small_base_url=small_base_url, small_model_name=small_model_name,
        )
        title = (getattr(response, "content", "") or "").strip()
        if not title:
            return None
        return title[:30]
    except Exception:
        logger.info("重命名 LLM 调用失败 | session=%s tier=%s", session_id, model_tier, exc_info=True)
        return None


def _persist_rename_title(agent: AgentCore, session_id: str, title: str) -> str:
    """将标题写入 DB 并返回。"""
    from agent_service.services.session_service import SessionService
    from agent_service.schemas.session import SessionUpdate
    session_service = SessionService(config=agent.config)
    session_service.update_session_name(session_id, SessionUpdate(session_name=title))
    return title


def _launch_auto_rename(agent: AgentCore, *, user_id: str, session_id: str) -> tuple[threading.Thread, queue_module.Queue]:
    """Fire rename worker in background thread. Caller can wait on the queue for the result."""
    q: queue_module.Queue = queue_module.Queue(maxsize=1)

    def _worker() -> None:
        try:
            title = _rename_session_worker(agent, user_id=user_id, session_id=session_id)
            q.put(title)
        except Exception:
            q.put(None)

    thread = threading.Thread(target=_worker, daemon=True, name=f"rename-{session_id[:12]}")
    thread.start()
    return thread, q


