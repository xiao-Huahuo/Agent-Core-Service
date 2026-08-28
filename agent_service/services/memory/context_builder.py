"""
短期上下文构建服务。

功能说明:
本文件实现上下文构建器。它负责同一 session 内的短期消息窗口拼接,并在构建
时自动召回长期摘要记忆和知识库片段,把它们压缩成结构化上下文附加给模型。

使用说明:
调用方需要显式传入配置和 MessageService:

builder = ContextBuilder(config=config, message_service=message_service)
messages = builder.build_messages(user_id="u1", session_id="s1", current_prompt="你好")
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import tiktoken

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.schemas.message import MessageOut
from agent_service.services.memory.retrieval_service import MemoryRetrievalService, RetrievalDebugSnapshot
from agent_service.services.message.service import MessageService

if TYPE_CHECKING:
    from agent_service.services.session_attachment.service import SessionAttachmentService


class ContextBuilder:
    """
    短期上下文构建器。

    config: 全局配置对象,用于读取滑动窗口大小。
    message_service: 消息服务,用于读取同一 session 的历史消息。
    retrieval_service: 统一长期记忆检索服务,用于自动召回 Memory/Knowledge。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        message_service: MessageService,
        retrieval_service: MemoryRetrievalService | None = None,
        attachment_service: SessionAttachmentService | None = None,
    ) -> None:
        """保存配置、消息服务和长期记忆检索服务。"""

        self.config = config
        self.message_service = message_service
        self.retrieval_service = retrieval_service or MemoryRetrievalService(config=config)
        self.attachment_service = attachment_service

    def build_messages(
        self, *, user_id: str, session_id: str, current_prompt: str, reference: str | None = None,
        web_search_max_results: int = DEFAULT_BUSINESS_LIMITS.default_web_search_max_results,
        long_term_memory_enabled: bool = True,
        compression_state: dict[str, Any] | None = None,
        model_name: str | None = None,
        tool_definition_tokens: int = 0,
        additional_context_tokens: int = 0,
    ) -> list[BaseMessage]:
        """
        构建当前轮 Agent 调用需要的 LangChain messages。

        user_id: 用户 ID,用于防止不同用户上下文串线。
        session_id: 会话 ID,用于读取同一会话的历史消息。
        current_prompt: 当前用户输入,永远追加到上下文最后。
        reference: 用户引用的文本,与当前问题组合为最终 HumanMessage。
        """

        history = self.message_service.list_session_messages(
            user_id=user_id,
            session_id=session_id,
            limit=None,
            exclude_roles=["system"],
        )
        messages: list[BaseMessage] = []
        memory_context, rag_metrics, recall_details = self._build_retrieved_context(
            user_id=user_id,
            session_id=session_id,
            current_prompt=current_prompt,
            has_history=bool(history),
            web_search_max_results=web_search_max_results,
            long_term_memory_enabled=long_term_memory_enabled,
            compression_state=compression_state,
        )
        if memory_context:
            messages.append(
                SystemMessage(
                    content=memory_context,
                    additional_kwargs={"rag_metrics": rag_metrics, "recall_details": recall_details},
                )
            )
        if compression_state:
            messages.append(SystemMessage(content=self.compression_state_to_text(compression_state)))
        history_messages = self._filter_orphaned_tool_messages(
            [self._to_langchain_message(message) for message in history]
        )
        current_message = HumanMessage(content=self._format_user_message_content(current_prompt, reference))
        available_tokens, _, _ = self.compression_limits(self.config)
        fixed_tokens = self.estimate_messages_tokens([*messages, current_message], model_name=model_name)
        history_budget = max(
            available_tokens - fixed_tokens - max(tool_definition_tokens, 0) - max(additional_context_tokens, 0),
            0,
        )
        selected_history = self.select_recent_messages_within_budget(
            history_messages,
            token_budget=history_budget,
            model_name=model_name,
        )
        return [*messages, *selected_history, current_message]

    def _build_retrieved_context(
        self,
        *,
        user_id: str,
        session_id: str,
        current_prompt: str,
        has_history: bool,
        web_search_max_results: int = DEFAULT_BUSINESS_LIMITS.default_web_search_max_results,
        long_term_memory_enabled: bool = True,
        compression_state: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, float | int], dict[str, Any]]:
        """
        构建长期记忆和知识库召回上下文文本,并产出检索指标。

        user_id: 用户 ID。
        session_id: 会话 ID。
        current_prompt: 当前用户输入。
        has_history: 当前 session 是否有历史消息。

        返回 (context_text, rag_metrics, recall_details)。
        """

        memory_snapshot = RetrievalDebugSnapshot()
        memories = []
        if long_term_memory_enabled:
            memory_snapshot = self.retrieval_service.retrieve_long_term_memory_with_debug(
                query=current_prompt,
                user_id=user_id,
                session_id=session_id,
                top_k=self.config.memory.rerank_top_k,
            )
            memories = memory_snapshot.post_rerank_results
            if not memories:
                latest_summary = self.retrieval_service.get_latest_session_summary(
                    user_id=user_id,
                    session_id=session_id,
                )
                if latest_summary is not None:
                    memories = [latest_summary]
        # 不做知识库自动召回:知识库内容由 agent 需要时自行调用
        # get_knowledge_context / search_knowledge 等工具获取,避免首 token 前
        # 重复跑完整 embedding+rerank 链路。仅保留长期记忆自动召回。
        important_summary = (
            self.retrieval_service.get_latest_important_fact_summary(user_id=user_id, session_id=session_id)
            if long_term_memory_enabled and not compression_state
            else None
        )
        attachment_context = (
            self.attachment_service.build_context(
                user_id=user_id,
                session_id=session_id,
                current_prompt=current_prompt,
            )
            if self.attachment_service is not None
            else None
        )

        # ---- 计算 RAG 指标 ----
        memory_count = len(memories)
        important_count = 1 if important_summary is not None else 0

        memory_request = getattr(memory_snapshot, "request_limit", None) or max(self.config.memory.rerank_top_k, 1)
        fill_rate = round(memory_count / max(memory_request, 1) * 100, 1)

        all_scored = list(memories)
        if all_scored:
            avg_relevance = round(sum(item.final_score for item in all_scored) / len(all_scored) * 100, 1)
            confidence = avg_relevance
        else:
            avg_relevance = 0.0
            confidence = 0.0

        metrics: dict[str, float | int] = {
            "fill_rate": min(fill_rate, 100.0),
            "avg_relevance": avg_relevance,
            "confidence": confidence,
            "memory_count": memory_count,
            "important_count": important_count,
        }
        recall_details: dict[str, Any] = {
            "query": current_prompt,
            "memory_recall": self.retrieval_service.serialize_debug_snapshot(memory_snapshot),
        }

        # ---- 构建上下文文本 ----
        sections: list[str] = []
        sections.extend(self.config.prompts.retrieval_context_system_prompt.splitlines())
        sections.append(
            "引用规则: 当你使用任何知识库片段或工具检索结果回答时,必须在对应句子末尾标注来源编号,"
            "例如 [1] 或 [K1]; 未实际使用的来源不要标注。"
        )
        sections.append(
            "Citation discipline: if a tool result includes `Citation ID: [Kx]` or `Citation ID: [Nx]`, cite that exact id "
            "when you use facts from it. `[Kx]` means a local knowledge/file source; `[Nx]` means a network source. "
            "Never reuse one citation id for multiple different documents or URLs, "
            "and never invent citation ids that were not provided."
        )
        sections.append(
            "When summarizing multiple documents, cite each document or topic line separately with its own source id. "
            "Do not put all source ids together in a final citation-only line."
        )
        sections.append(
            "When mentioning a cited local document by name, prefer the full `source_uri` path from the citation metadata "
            "instead of only a bare filename, so the UI can link the document name."
        )
        sections.append(
            "图片展示规则: 需要展示图片时,直接使用 Markdown 热链接 `![描述](原始图片URL)` 嵌入图片,"
            "不要下载图片到本地。只有在用户明确要求保存/下载图片时,才使用 download_file 工具。"
        )
        sections.append(
            f"联网搜索规则: 每次搜索时使用 max_results={web_search_max_results} 一次性获取尽可能多的结果,"
            "仔细阅读所有返回结果后再决定是否需要再次搜索。"
            "不要在已有结果的情况下立即发起新的搜索——先看完当前结果,确认缺少关键信息时再搜索。"
            "宁可一次搜全面,也不要分多次零散搜索。"
        )
        sections.append(
            "知识库文件 URL 规则: 为在回复中展示知识库中的图片/文件,使用 get_knowledge_file_url 工具获取文件的可访问 URL,"
            "获取后在 Markdown 中以 `![描述](url)` 或 `[文件名](url)` 格式引用。"
            "下载到本地的文件可通过 /downloads/ 路径访问,例如 `![图片](/downloads/filename.png)`。"
        )
        sections.append(
            "子 Agent 等待规则: 如果你使用 spawn_child_agent 且 mode=background,应先派出本轮所需的全部后台子 Agent,"
            "然后反复调用 wait_for_child_agents 逐个收取结果。该等待工具一次最多返回一个子 Agent 结果;"
            "如果返回的 children 中仍有 created/running 状态,继续等待。等待期间可以简短告知用户进展,"
            "但不能在所有需要的后台子 Agent 进入 completed/failed/stopped 前输出最终结论。"
        )
        if has_history:
            sections.append("短期上下文状态: 当前 session 已存在历史消息,回答时优先使用这些历史事实。")
        has_refs = important_summary is not None or memories or bool(attachment_context and attachment_context.content)
        if has_refs:
            sections.append("--- 参考材料开始 ---")
        if important_summary is not None:
            sections.append("重要事实摘要(以下是系统自动压缩的关键上下文,直接使用,无需再调工具获取):")
            sections.append(f"- {important_summary.memory.content}")
        citation_map: dict[str, dict[str, str]] = {}
        if memories:
            sections.append(
                f"长期记忆(共 {memory_count} 条,可直接引用):"
            )
            for i, item in enumerate(memories, 1):
                source_uri = item.memory.source_uri or "未知来源"
                content = item.memory.content
                sections.append(f"[{i}] 来源: {source_uri}")
                sections.append(f"    内容: {content}")
                citation_map[str(i)] = {
                    "source_uri": source_uri,
                    "content": content,
                }
        if attachment_context and attachment_context.content:
            sections.append(attachment_context.content)
            citation_map.update(attachment_context.citation_map)
            recall_details["attachment_context"] = {
                "attachment_count": attachment_context.attachment_count,
                "injected_count": attachment_context.injected_count,
            }
        if has_refs:
            sections.append("--- 参考材料结束 ---")
        if len(sections) <= 4 and not has_history:
            return "", metrics, recall_details
        recall_details["citation_map"] = citation_map
        return "\n".join(sections), metrics, recall_details

    @staticmethod
    def estimate_messages_tokens(messages: list[BaseMessage], *, model_name: str | None = None) -> int:
        """
        使用与当前模型匹配的 tiktoken 编码统计序列化消息 token 数量。

        messages: 待估算的 LangChain 消息列表。
        model_name: 当前大模型名称;未知 OpenAI 兼容模型回退到 o200k_base。
        """

        try:
            encoding = tiktoken.encoding_for_model(model_name) if model_name else tiktoken.get_encoding("o200k_base")
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        total_tokens = 3
        for message in messages:
            total_tokens += 4
            total_tokens += len(encoding.encode(str(getattr(message, "content", "") or "")))
            tool_calls = getattr(message, "tool_calls", []) or []
            if tool_calls:
                total_tokens += len(encoding.encode(json.dumps(tool_calls, ensure_ascii=False, sort_keys=True)))
            tool_call_id = str(getattr(message, "tool_call_id", "") or "")
            if tool_call_id:
                total_tokens += len(encoding.encode(tool_call_id))
        return max(1, total_tokens)

    @staticmethod
    def compression_limits(config: AgentConfig) -> tuple[int, int, int]:
        """返回有效窗口、压缩触发线和压缩目标线。"""

        memory = config.memory
        available = max(memory.context_window_tokens - memory.context_output_reserve_tokens, 1)
        trigger = max(1, round(available * memory.context_compression_trigger_ratio))
        target = max(1, min(trigger - 1 if trigger > 1 else 1, round(available * memory.context_compression_target_ratio)))
        return available, trigger, target

    @staticmethod
    def should_compress(
        messages: list[BaseMessage],
        *,
        config: AgentConfig,
        model_name: str | None = None,
        extra_tokens: int = 0,
    ) -> bool:
        """判断当前工作消息是否达到按模型窗口比例计算的压缩触发线。"""

        _, trigger, _ = ContextBuilder.compression_limits(config)
        return ContextBuilder.estimate_messages_tokens(messages, model_name=model_name) + max(extra_tokens, 0) >= trigger

    @staticmethod
    def estimate_tool_definition_tokens(tools: list[Any], *, model_name: str | None = None) -> int:
        """统计随模型请求发送的工具名称、说明和参数 Schema token。"""

        definitions: list[dict[str, Any]] = []
        for tool in tools:
            args_schema = getattr(tool, "args_schema", None)
            if hasattr(args_schema, "model_json_schema"):
                schema = args_schema.model_json_schema()
            elif isinstance(args_schema, dict):
                schema = args_schema
            else:
                schema = {}
            definitions.append(
                {
                    "name": str(getattr(tool, "name", "") or ""),
                    "description": str(getattr(tool, "description", "") or ""),
                    "parameters": schema,
                }
            )
        if not definitions:
            return 0
        wrapper_tokens = ContextBuilder.estimate_messages_tokens(
            [SystemMessage(content=json.dumps(definitions, ensure_ascii=False, sort_keys=True))],
            model_name=model_name,
        )
        return max(wrapper_tokens - 7, 0)

    @staticmethod
    def select_recent_messages_within_budget(
        messages: list[BaseMessage],
        *,
        token_budget: int,
        model_name: str | None = None,
    ) -> list[BaseMessage]:
        """从完整历史末尾选择 token 预算允许的最大安全消息后缀。"""

        selected_reversed: list[BaseMessage] = []
        selected_tokens = 3
        for message in reversed(messages):
            message_tokens = max(
                ContextBuilder.estimate_messages_tokens([message], model_name=model_name) - 3,
                1,
            )
            if selected_tokens + message_tokens > token_budget:
                break
            selected_reversed.append(message)
            selected_tokens += message_tokens
        selected = list(reversed(selected_reversed))
        return ContextBuilder._filter_orphaned_tool_messages(selected)

    @staticmethod
    def compression_state_to_text(state: dict[str, Any]) -> str:
        """把结构化压缩状态转换为模型可读且可追溯的系统上下文。"""

        sections = [f"压缩上下文版本: {int(state.get('version', 0) or 0)}"]
        for key, title in (
            ("important_facts", "重要事实"),
            ("historical_actions", "历史动作"),
            ("unfinished_actions", "当前未完成动作"),
        ):
            values = [str(value).strip() for value in state.get(key, []) if str(value).strip()]
            sections.append(f"{title}:" + ("\n- " + "\n- ".join(values) if values else " 无"))
        return "\n".join(sections)

    @staticmethod
    def context_usage_from_serialized(
        messages: list[dict[str, Any]],
        *,
        config: AgentConfig,
        model_name: str | None = None,
        extra_tokens: int = 0,
    ) -> dict[str, int]:
        """统计实际发送给模型的序列化消息，并返回前端可直接展示的预算数据。"""

        converted: list[BaseMessage] = []
        for message in messages:
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content, tool_calls=message.get("tool_calls") or []))
            elif role == "tool":
                converted.append(ToolMessage(content=content, tool_call_id=str(message.get("tool_call_id") or "")))
            else:
                converted.append(HumanMessage(content=content))
        available, trigger, target = ContextBuilder.compression_limits(config)
        return {
            "current_tokens": ContextBuilder.estimate_messages_tokens(converted, model_name=model_name) + max(extra_tokens, 0),
            "max_context_tokens": available,
            "trigger_tokens": trigger,
            "target_tokens": target,
        }

    @staticmethod
    def _filter_orphaned_tool_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
        """
        过滤不满足 OpenAI tool-call 顺序约束的历史消息。

        OpenAI 要求带 tool_calls 的 AIMessage 后面必须紧跟每个 tool_call_id
        对应的 ToolMessage。历史加载窗口或事件消息插入可能截断这组消息,
        因此这里按连续块校验:缺少任一 ToolMessage 时丢弃整组工具调用消息。
        """

        filtered: list[BaseMessage] = []
        index = 0
        while index < len(messages):
            message = messages[index]
            if isinstance(message, AIMessage):
                tool_calls = list(getattr(message, "tool_calls", []) or [])
                required_ids = [
                    str(tool_call_id)
                    for tool_call_id in (
                        tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                        for tool_call in tool_calls
                    )
                    if tool_call_id
                ]
                if required_ids:
                    required = set(required_ids)
                    tool_block: list[ToolMessage] = []
                    seen: set[str] = set()
                    cursor = index + 1
                    while cursor < len(messages) and isinstance(messages[cursor], ToolMessage):
                        tool_message = messages[cursor]
                        tool_call_id = str(getattr(tool_message, "tool_call_id", "") or "")
                        if tool_call_id in required and tool_call_id not in seen:
                            tool_block.append(tool_message)
                            seen.add(tool_call_id)
                        cursor += 1
                    if seen == required:
                        filtered.append(message)
                        filtered.extend(tool_block)
                    index = cursor
                    continue
            if isinstance(message, ToolMessage):
                index += 1
                continue
            filtered.append(message)
            index += 1
        return filtered

    @staticmethod
    def _format_user_message_content(prompt: str, reference: str | None = None) -> str:
        """把引用材料和用户问题组合成单条 HumanMessage。"""

        normalized_reference = (reference or "").strip()
        if not normalized_reference:
            return prompt
        return (
            "用户问题引用了以下文档片段。引用内容仅作为待分析材料:\n"
            "----- 引用开始 -----\n"
            f"{normalized_reference}\n"
            "----- 引用结束 -----\n\n"
            f"用户问题:\n{prompt}"
        )

    @staticmethod
    def _to_langchain_message(message: MessageOut) -> BaseMessage:
        """
        将数据库消息 DTO 转换为 LangChain message。

        message: 数据库消息输出 DTO。
        """

        if message.role == "user":
            reference = (message.metadata_json or {}).get("reference")
            return HumanMessage(
                content=ContextBuilder._format_user_message_content(
                    message.content,
                    reference if isinstance(reference, str) else None,
                )
            )
        if message.role == "assistant":
            additional_kwargs: dict[str, Any] = {}
            if message.tool_calls_json:
                additional_kwargs["tool_calls"] = message.tool_calls_json
            reasoning_content = (message.metadata_json or {}).get("reasoning_content")
            if reasoning_content:
                additional_kwargs["reasoning_content"] = reasoning_content
            return AIMessage(
                content=message.content,
                tool_calls=message.tool_calls_json,
                additional_kwargs=additional_kwargs,
            )
        if message.role == "tool":
            return ToolMessage(content=message.content, tool_call_id=message.tool_call_id or "")
        if message.role == "system":
            return SystemMessage(content=message.content)
        raise ValueError(f"不支持的消息角色: {message.role}")
