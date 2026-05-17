"""
AgentCore 对外入口模块。

功能说明:
本文件提供 `AgentCore` 类,作为 Agent 微服务核心能力的对外门面。它负责接收
`AgentConfig`、加载默认内置工具、构建 LangGraph 图、输出图结构 Mermaid 文件,
启动时检查并下载 Embedding/ReRank 本地模型,并对外提供 Agent 执行入口。具体节点逻辑不写在本文件中,而是由
`AgentGraphBuilder` 装配 `compress`、`planner`、`model_decision`、`tool_call`、`reflection` 和 `summary` 等节点。

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
import threading
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.graph import AgentGraphBuilder
from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.message import MessageCreate
from agent_service.scripts.draw_agent_graph import draw_agent_graph
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.message_service import MessageService
from agent_service.services.safety import SafetyService
from agent_service.services.scheduler import (
    BACKGROUND_SUMMARY_TASK,
    SMALL_MODEL_TIER,
    LLMTaskScheduler,
    get_llm_task_scheduler,
)
from agent_service.tools import (
    ToolExecutor,
    ToolRegistry,
    clear_agent_token_callback,
    clear_tool_runtime,
    clear_tool_trace_callback,
    set_agent_token_callback,
    set_tool_runtime,
    set_tool_trace_callback,
    set_planner_content_callback,
    clear_planner_content_callback,
    set_reflection_content_callback,
    clear_reflection_content_callback,
)

logger = logging.getLogger(__name__)


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
    if "rate_limit" in lower or "rate limit" in lower:
        return "请求过于频繁,请稍后重试"
    if "timeout" in lower:
        return "请求超时,请稍后重试"
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
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        tools: Sequence[Any] | None = None,
        graph: CompiledStateGraph | None = None,
        message_service: MessageService | None = None,
        context_builder: ContextBuilder | None = None,
        task_scheduler: LLMTaskScheduler | None = None,
    ) -> None:
        """保存配置、检查本地模型、构建或接收 LangGraph 图,并输出当前节点流程图。"""

        self.config = config
        logger.debug("AgentCore 初始化开始 | model=%s", config.model.model_name)
        self.config.ensure_local_models()
        logger.debug("本地模型检查完成")
        self.message_service = message_service
        self.context_builder = context_builder
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
        builder = AgentGraphBuilder(
            config=config,
            tools=self.tools,
            tool_executor=self.tool_executor,
            task_scheduler=self.task_scheduler,
            safety_service=safety_service,
        )
        self.graph: CompiledStateGraph = graph or builder.build()
        self.graph_diagram_path = draw_agent_graph(
            compiled_graph=self.graph,
            output_path=config.storage.project_root / "agent_graph.mmd",
            branch_labels=builder.branch_labels,
        )

    def stream_run(self, *, prompt: str, user_id: str, session_id: str) -> Iterator[dict[str, Any]]:
        """
        运行一轮无状态 Agent 并逐节点产出 dict 事件。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        messages = [HumanMessage(content=prompt)]
        logger.info("开始无状态流式运行 | user=%s session=%s", user_id, session_id)
        yield from self._stream_events(messages=messages, user_id=user_id, session_id=session_id)
        logger.debug("无状态流式运行完成 | user=%s session=%s", user_id, session_id)

    def run_once(self, *, prompt: str, user_id: str, session_id: str) -> dict[str, Any]:
        """
        运行一轮无状态 Agent 并返回结构化结果。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        chunks = list(self.stream_run(prompt=prompt, user_id=user_id, session_id=session_id))
        graph_diagram = self.graph_diagram_path.read_text(encoding="utf-8")
        return {
            "graph_diagram_path": str(self.graph_diagram_path),
            "graph_diagram": graph_diagram,
            "final_output": self.extract_final_output(chunks),
            "events": chunks,
        }

    def run_session_prompt(self, *, prompt: str, user_id: str, session_id: str) -> dict[str, Any]:
        """
        运行带 session 上下文和消息持久化的一轮 Agent,返回结构化结果。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        chunks = list(self.stream_session_prompt(prompt=prompt, user_id=user_id, session_id=session_id))
        graph_diagram = self.graph_diagram_path.read_text(encoding="utf-8")
        return {
            "graph_diagram_path": str(self.graph_diagram_path),
            "graph_diagram": graph_diagram,
            "final_output": self.extract_final_output(chunks),
            "events": chunks,
        }

    def stream_session_prompt(self, *, prompt: str, user_id: str, session_id: str) -> Iterator[dict[str, Any]]:
        """
        运行带 session 上下文和消息持久化的一轮 Agent,逐节点产出 dict 事件。

        prompt: 用户本轮输入。
        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        message_service = self._get_message_service()
        context_builder = self._get_context_builder(message_service=message_service)
        logger.info(
            "开始 session 流式运行 | user=%s session=%s prompt_len=%d",
            user_id,
            session_id,
            len(prompt),
        )
        messages = context_builder.build_messages(user_id=user_id, session_id=session_id, current_prompt=prompt)
        logger.debug("上下文构建完成 | message_count=%d", len(messages))

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
                metadata_json={"source": "stream_session_prompt"},
            )
        )
        yield from self._stream_events(
            messages=messages,
            user_id=user_id,
            session_id=session_id,
            message_service=message_service,
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
        """

        inputs = {
            "messages": messages,
            "user_id": user_id,
            "session_id": session_id,
            "trace": [],
        }
        runtime_config = {"configurable": {"thread_id": session_id}}
        retrieval_service = None
        if self.context_builder is not None:
            retrieval_service = self.context_builder.retrieval_service

        cancel_event = threading.Event()
        with self._cancel_events_lock:
            self._cancel_events[session_id] = cancel_event

        token_queue: queue_module.Queue[dict[str, Any]] = queue_module.Queue()
        _streamed_content: list[str] = [""]
        _turn_traces: list[dict[str, Any]] = []
        _token_blocked: list[bool] = [False]


        def on_token(cumulative_text: str) -> None:
            if _token_blocked[0]:
                return
            content = AgentCore._sanitize_streaming_content(
                cumulative_text,
                min_chars=self.config.model.streaming_sanitize_min_chars,
            )
            _streamed_content[0] = content
            if content != cumulative_text:
                _token_blocked[0] = True
                token_queue.put({
                    "type": "token",
                    "node": "agent",
                    "content": content,
                    "tool_calls": [],
                    "trace": [],
                })
                return
            token_queue.put({
                "type": "token",
                "node": "agent",
                "content": content,
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

        def on_reflection_content(cumulative_text: str) -> None:
            token_queue.put({
                "type": "reflection_content",
                "node": "reflection",
                "content": cumulative_text,
                "tool_calls": [],
                "trace": [],
            })

        def run_graph() -> None:
            nonlocal graph_error
            set_tool_runtime(
                config=self.config,
                user_id=user_id,
                session_id=session_id,
                retrieval_service=retrieval_service,
            )
            set_agent_token_callback(on_token)
            set_tool_trace_callback(on_tool_trace)
            set_planner_content_callback(on_planner_content)
            set_reflection_content_callback(on_reflection_content)
            try:
                for event in self.graph.stream(inputs, config=runtime_config, stream_mode="updates"):
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
                clear_reflection_content_callback()
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
                        "node": item.get("node", "agent"),
                        "content": item.get("content", ""),
                        "tool_calls": item.get("tool_calls", []),
                        "trace": item.get("trace", []),
                        "model_name": self._model_name_for_node(item.get("node", "agent")),
                    }

                elif item_type == "tool_trace":
                    trace = item.get("trace", {})
                    if trace:
                        trace["model_name"] = self._model_name_for_node(trace.get("node", "action"))
                        _turn_traces.append(trace)
                    yield {
                        "node": trace.get("node", "action"),
                        "content": "",
                        "tool_calls": [],
                        "trace": [trace] if trace else [],
                        "model_name": self._model_name_for_node(trace.get("node", "action")),
                    }

                elif item_type == "planner_content":
                    yield {
                        "node": "planner",
                        "content": item.get("content", ""),
                        "tool_calls": [],
                        "trace": [],
                        "model_name": self._model_name_for_node("planner"),
                    }

                elif item_type == "reflection_content":
                    yield {
                        "node": "reflection",
                        "content": item.get("content", ""),
                        "tool_calls": [],
                        "trace": [],
                        "model_name": self._model_name_for_node("reflection"),
                    }

                elif item_type == "node":
                    event = item["event"]
                    for node_name, state_update in event.items():
                        logger.debug("图节点执行 | node=%s user=%s session=%s", node_name, user_id, session_id)
                        node_traces = state_update.get("trace", []) if state_update else []
                        if node_traces:
                            for t in node_traces:
                                t["model_name"] = self._model_name_for_node(node_name)
                            _turn_traces.extend(node_traces)
                        if message_service is not None:
                            self._save_state_update_messages(
                                message_service=message_service,
                                user_id=user_id,
                                session_id=session_id,
                                node_name=node_name,
                                state_update=state_update,
                                turn_traces=state_update.get("trace", []),
                            )
                        payload = self._build_stream_payload(node_name=node_name, state_update=state_update)
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
            clear_reflection_content_callback()
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
            self.context_builder = ContextBuilder(config=self.config, message_service=message_service)
        return self.context_builder

    def _save_state_update_messages(
        self,
        *,
        message_service: MessageService,
        user_id: str,
        session_id: str,
        node_name: str,
        state_update: dict[str, Any] | None,
        turn_traces: list[dict[str, Any]] | None = None,
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
        for message in state_update.get("messages", []):
            message_create = self._message_to_create(
                message=message,
                user_id=user_id,
                session_id=session_id,
                node_name=node_name,
                turn_traces=turn_traces,
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
            return MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=AgentCore._stringify_content(message.content),
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
        small_nodes = {"planner"}
        if node_name in small_nodes and self.config.model.small_model_name:
            return self.config.model.small_model_name
        return self.config.model.model_name

    @staticmethod
    def _build_stream_payload(*, node_name: str, state_update: dict[str, Any] | None) -> dict[str, Any]:
        """把 LangGraph 节点更新转换为稳定的流式输出结构。"""

        if not state_update:
            return {"node": node_name, "content": "", "tool_calls": [], "trace": []}

        messages = state_update.get("messages", [])
        last_message = messages[-1] if messages else None
        content = getattr(last_message, "content", "") if last_message is not None else ""
        tool_calls = getattr(last_message, "tool_calls", []) if last_message is not None else []
        content = AgentCore._sanitize_agent_output(content or "")
        return {
            "node": node_name,
            "content": content,
            "tool_calls": tool_calls or [],
            "trace": state_update.get("trace", []),
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


def _launch_auto_rename(agent: AgentCore, *, user_id: str, session_id: str) -> None:
    """Fire-and-forget: 用小模型根据对话内容生成并更新会话标题。"""

    def _rename_worker() -> None:
        try:
            message_service = agent._get_message_service()
            recent = message_service.list_recent_messages(
                user_id=user_id, session_id=session_id, limit=6
            )
            if len(recent) < 2:
                return
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
                return
            conversation = "\n".join(lines)
            rename_prompt = (
                "根据以下对话内容,为这个会话生成一个简洁的标题(15字以内,中文):\n\n"
                f"{conversation}\n\n标题:"
            )
            response = agent.task_scheduler.invoke_chat(
                task_type=BACKGROUND_SUMMARY_TASK,
                messages=[HumanMessage(content=rename_prompt)],
                tool_names=[],
                model_tier=SMALL_MODEL_TIER,
                temperature=0.3,
            )
            title = (getattr(response, "content", "") or "").strip()
            if not title:
                return
            title = title[:30]
            from agent_service.services.session_service import SessionService
            from agent_service.schemas.session import SessionUpdate
            session_service = SessionService(config=agent.config)
            session_service.update_session_name(
                session_id, SessionUpdate(session_name=title)
            )
        except Exception:
            logger.debug("会话自动重命名失败 | session=%s", session_id, exc_info=True)

    thread = threading.Thread(
        target=_rename_worker,
        daemon=True,
        name=f"rename-{session_id[:12]}",
    )
    thread.start()
