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
from agent_service.services.scheduler import LLMTaskScheduler, get_llm_task_scheduler
from agent_service.tools import (
    ToolExecutor,
    ToolRegistry,
    clear_agent_token_callback,
    clear_tool_runtime,
    set_agent_token_callback,
    set_tool_runtime,
)

logger = logging.getLogger(__name__)


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

    def stream_run(self, *, prompt: str, user_id: str, session_id: str) -> Iterator[str]:
        """
        运行一轮 Agent 循环并输出 SSE 风格字符串。

        prompt: 用户本轮输入。
        user_id: 用户 ID,用于后续记忆和会话隔离。
        session_id: 会话 ID,用于后续 checkpoint 和短期记忆恢复。
        """

        messages = [HumanMessage(content=prompt)]
        logger.info("开始无状态流式运行 | user=%s session=%s prompt_len=%d", user_id, session_id, len(prompt))
        yield from self._format_sse(self._stream_events(messages=messages, user_id=user_id, session_id=session_id))
        logger.debug("无状态流式运行完成 | user=%s session=%s", user_id, session_id)

    def stream_run_events(self, *, prompt: str, user_id: str, session_id: str) -> Iterator[dict[str, Any]]:
        """与 stream_run 相同的逻辑,但直接产出 dict 供 gRPC 使用。"""

        messages = [HumanMessage(content=prompt)]
        logger.info("开始无状态流式运行(gRPC) | user=%s session=%s", user_id, session_id)
        yield from self._stream_events(messages=messages, user_id=user_id, session_id=session_id)
        logger.debug("无状态流式运行完成(gRPC) | user=%s session=%s", user_id, session_id)

    def run_once(self, *, prompt: str, user_id: str, session_id: str) -> dict[str, Any]:
        """
        运行一轮 Agent 并返回结构化结果。

        prompt: 用户本轮输入。
        user_id: 用户 ID,用于隔离不同用户的上下文。
        session_id: 会话 ID,用于标识同一轮会话线程。
        """

        chunks = list(self.stream_run(prompt=prompt, user_id=user_id, session_id=session_id))
        events = self.parse_stream_chunks(chunks)
        graph_diagram = self.graph_diagram_path.read_text(encoding="utf-8")
        return {
            "graph_diagram_path": str(self.graph_diagram_path),
            "graph_diagram": graph_diagram,
            "final_output": self.extract_final_output(events),
            "events": events,
            "chunks": chunks,
        }

    def run_session_prompt(self, *, prompt: str, user_id: str, session_id: str) -> dict[str, Any]:
        """
        运行带 session 上下文和消息持久化的一轮 Agent。

        prompt: 用户本轮输入。
        user_id: 用户 ID,用于读取和保存该用户的消息。
        session_id: 会话 ID,由外部主服务控制连续对话或新对话。
        """

        chunks: list[str] = []
        for chunk in self.stream_session_prompt(prompt=prompt, user_id=user_id, session_id=session_id):
            chunks.append(chunk)
        events = self.parse_stream_chunks(chunks)
        graph_diagram = self.graph_diagram_path.read_text(encoding="utf-8")
        return {
            "graph_diagram_path": str(self.graph_diagram_path),
            "graph_diagram": graph_diagram,
            "final_output": self.extract_final_output(events),
            "events": events,
            "chunks": chunks,
        }

    def stream_session_prompt(self, *, prompt: str, user_id: str, session_id: str) -> Iterator[str]:
        """
        运行带 session 上下文和消息持久化的一轮 Agent,以 SSE 流式输出。

        与 `run_session_prompt` 共享相同的上下文构建和持久化逻辑,但不再缓冲全部
        chunk 再返回 dict,而是逐节点 yield SSE 字符串,适合 HTTP SSE 直推到前端。

        prompt: 用户本轮输入。
        user_id: 用户 ID,用于读取和保存该用户的消息。
        session_id: 会话 ID,由外部主服务控制连续对话或新对话。
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
        message_service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=prompt,
                metadata_json={"source": "stream_session_prompt"},
            )
        )
        yield from self._format_sse(
            self._stream_events(
                messages=messages,
                user_id=user_id,
                session_id=session_id,
                message_service=message_service,
            )
        )

    def stream_session_prompt_events(
        self, *, prompt: str, user_id: str, session_id: str
    ) -> Iterator[dict[str, Any]]:
        """与 stream_session_prompt 相同的逻辑,但直接产出 dict 供 gRPC 使用。"""

        message_service = self._get_message_service()
        context_builder = self._get_context_builder(message_service=message_service)
        logger.info(
            "开始 session 流式运行(gRPC) | user=%s session=%s prompt_len=%d",
            user_id,
            session_id,
            len(prompt),
        )
        messages = context_builder.build_messages(user_id=user_id, session_id=session_id, current_prompt=prompt)
        logger.debug("上下文构建完成(gRPC) | message_count=%d", len(messages))
        message_service.create_message(
            MessageCreate(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=prompt,
                metadata_json={"source": "stream_session_prompt_grpc"},
            )
        )
        yield from self._stream_events(
            messages=messages,
            user_id=user_id,
            session_id=session_id,
            message_service=message_service,
        )

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
        HTTP 侧再用 _format_sse() 包一层 SSE 格式;
        gRPC 侧直接将 dict 转换为 ChunkMessage。

        采用双线程 + 队列模式: 图在后台线程中执行,Agent 节点的 token 级
        流式输出通过 thread-local 回调实时推入队列,主线程从队列读取并 yield,
        实现真正的 token 级流式推送。

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
        set_tool_runtime(
            config=self.config,
            user_id=user_id,
            session_id=session_id,
            retrieval_service=retrieval_service,
        )

        token_queue: queue_module.Queue[dict[str, Any]] = queue_module.Queue()

        def on_token(cumulative_text: str) -> None:
            """Agent 节点逐 token 回调: 将增量文本包装为流式事件推入队列。"""
            token_queue.put({
                "type": "token",
                "node": "agent",
                "content": cumulative_text,
                "tool_calls": [],
                "trace": [],
            })

        set_agent_token_callback(on_token)

        graph_error: Exception | None = None

        def run_graph() -> None:
            """在后台线程中同步执行 LangGraph 图,捕获异常。"""
            nonlocal graph_error
            try:
                for event in self.graph.stream(inputs, config=runtime_config, stream_mode="updates"):
                    token_queue.put({"type": "node", "event": event})
                token_queue.put({"type": "done"})
            except Exception as exc:
                graph_error = exc
                token_queue.put({"type": "error", "error": exc})

        graph_thread = threading.Thread(target=run_graph, daemon=True, name=f"graph-{session_id[:12]}")
        graph_thread.start()

        try:
            while True:
                try:
                    item = token_queue.get(timeout=0.1)
                except queue_module.Empty:
                    if graph_error is not None:
                        raise graph_error from graph_error
                    if not graph_thread.is_alive() and token_queue.empty():
                        break
                    continue

                item_type = item.get("type")

                if item_type == "done":
                    break

                if item_type == "error":
                    raise item["error"]

                if item_type == "token":
                    yield {
                        "node": item.get("node", "agent"),
                        "content": item.get("content", ""),
                        "tool_calls": item.get("tool_calls", []),
                        "trace": item.get("trace", []),
                    }

                elif item_type == "node":
                    event = item["event"]
                    for node_name, state_update in event.items():
                        logger.debug("图节点执行 | node=%s user=%s session=%s", node_name, user_id, session_id)
                        if message_service is not None:
                            self._save_state_update_messages(
                                message_service=message_service,
                                user_id=user_id,
                                session_id=session_id,
                                node_name=node_name,
                                state_update=state_update,
                            )
                        yield self._build_stream_payload(node_name=node_name, state_update=state_update)
        finally:
            clear_agent_token_callback()
            clear_tool_runtime()
            graph_thread.join(timeout=5.0)

    @staticmethod
    def _format_sse(events_iter: Iterator[dict[str, Any]]) -> Iterator[str]:
        """将 dict 事件迭代器包装为 SSE (text/event-stream) 格式字符串。"""

        for payload in events_iter:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

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
    ) -> None:
        """
        将图节点返回的新增消息保存为 MessageRecord。

        message_service: 消息服务。
        user_id: 用户 ID。
        session_id: 会话 ID。
        node_name: 当前节点名称。
        state_update: LangGraph 节点返回的状态更新。
        """

        if not state_update:
            return
        for message in state_update.get("messages", []):
            message_create = self._message_to_create(
                message=message,
                user_id=user_id,
                session_id=session_id,
                node_name=node_name,
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
    ) -> MessageCreate | None:
        """
        将 LangChain message 转换为 MessageCreate。

        message: LangGraph 节点返回的新增消息。
        user_id: 用户 ID。
        session_id: 会话 ID。
        node_name: 产生该消息的节点名称。
        """

        metadata = {"node": node_name, "source": "agent_graph"}
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

    @staticmethod
    def _build_stream_payload(*, node_name: str, state_update: dict[str, Any] | None) -> dict[str, Any]:
        """把 LangGraph 节点更新转换为稳定的流式输出结构。"""

        if not state_update:
            return {"node": node_name, "content": "", "tool_calls": [], "trace": []}

        messages = state_update.get("messages", [])
        last_message = messages[-1] if messages else None
        content = getattr(last_message, "content", "") if last_message is not None else ""
        tool_calls = getattr(last_message, "tool_calls", []) if last_message is not None else []
        return {
            "node": node_name,
            "content": content or "",
            "tool_calls": tool_calls or [],
            "trace": state_update.get("trace", []),
        }
