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

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.message import MessageOut
from agent_service.services.memory.retrieval_service import MemoryRetrievalService
from agent_service.services.message_service import MessageService


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
    ) -> None:
        """保存配置、消息服务和长期记忆检索服务。"""

        self.config = config
        self.message_service = message_service
        self.retrieval_service = retrieval_service or MemoryRetrievalService(config=config)

    def build_messages(self, *, user_id: str, session_id: str, current_prompt: str) -> list[BaseMessage]:
        """
        构建当前轮 Agent 调用需要的 LangChain messages。

        user_id: 用户 ID,用于防止不同用户上下文串线。
        session_id: 会话 ID,用于读取同一会话的历史消息。
        current_prompt: 当前用户输入,永远追加到上下文最后。
        """

        history = self.message_service.list_session_messages(
            user_id=user_id,
            session_id=session_id,
            limit=self.config.memory.max_context_messages,
            exclude_roles=["system"],
        )
        messages: list[BaseMessage] = []
        memory_context, rag_metrics, recall_details = self._build_retrieved_context(
            user_id=user_id,
            session_id=session_id,
            current_prompt=current_prompt,
            has_history=bool(history),
        )
        if memory_context:
            messages.append(
                SystemMessage(
                    content=memory_context,
                    additional_kwargs={"rag_metrics": rag_metrics, "recall_details": recall_details},
                )
            )
        messages.extend(self._to_langchain_message(message) for message in history)
        messages = self._filter_orphaned_tool_messages(messages)
        messages.append(HumanMessage(content=current_prompt))
        if self.estimate_messages_tokens(messages) > self.config.memory.summary_trigger_tokens:
            compressed_history = history[-self.config.memory.context_compression_tail_messages :]
            messages = self._rebuild_messages_for_compressed_context(
                user_id=user_id,
                session_id=session_id,
                current_prompt=current_prompt,
                history=compressed_history,
            )
        return messages

    def _build_retrieved_context(
        self,
        *,
        user_id: str,
        session_id: str,
        current_prompt: str,
        has_history: bool,
    ) -> tuple[str, dict[str, float | int], dict[str, Any]]:
        """
        构建长期记忆和知识库召回上下文文本,并产出检索指标。

        user_id: 用户 ID。
        session_id: 会话 ID。
        current_prompt: 当前用户输入。
        has_history: 当前 session 是否有历史消息。

        返回 (context_text, rag_metrics, recall_details)。
        """

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
        knowledge_snapshot = self.retrieval_service.retrieve_knowledge_with_debug(
            query=current_prompt,
            top_k=self.config.memory.rerank_top_k,
        )
        knowledge = knowledge_snapshot.post_rerank_results
        important_summary = self.retrieval_service.get_latest_important_fact_summary(
            user_id=user_id,
            session_id=session_id,
        )

        # ---- 计算 RAG 指标 ----
        top_k = max(self.config.memory.rerank_top_k, 1)
        memory_count = len(memories)
        knowledge_count = len(knowledge)
        important_count = 1 if important_summary is not None else 0

        recall_memory = (memory_count / top_k) * 100
        recall_knowledge = (knowledge_count / top_k) * 100
        recall = round((recall_memory + recall_knowledge) / 2, 1)

        hit_memory = 1 if memories else 0
        hit_knowledge = 1 if knowledge else 0
        hit_rate = round(((hit_memory + hit_knowledge) / 2) * 100, 1)

        all_scored = list(memories) + list(knowledge)
        if all_scored:
            confidence = round(sum(item.final_score for item in all_scored) / len(all_scored) * 100, 1)
        else:
            confidence = 0.0

        metrics: dict[str, float | int] = {
            "recall": min(recall, 100.0),
            "hit_rate": hit_rate,
            "confidence": confidence,
            "memory_count": memory_count,
            "knowledge_count": knowledge_count,
            "important_count": important_count,
        }
        recall_details: dict[str, Any] = {
            "query": current_prompt,
            "memory_recall": self.retrieval_service.serialize_debug_snapshot(memory_snapshot),
            "knowledge_recall": self.retrieval_service.serialize_debug_snapshot(knowledge_snapshot),
        }

        # ---- 构建上下文文本 ----
        sections: list[str] = []
        sections.extend(self.config.model.retrieval_context_system_prompt.splitlines())
        if has_history:
            sections.append("短期上下文状态: 当前 session 已存在历史消息,回答时优先使用这些历史事实。")
        has_refs = important_summary is not None or memories or knowledge
        if has_refs:
            sections.append("--- 参考材料开始 ---")
        if important_summary is not None:
            sections.append("重要事实摘要(以下是系统自动压缩的关键上下文,直接使用,无需再调工具获取):")
            sections.append(f"- {important_summary.memory.content}")
        if memories:
            sections.append(
                f"长期记忆索引: 系统中检索到 {memory_count} 条与当前问题相关的历史记忆。"
                f"如果你需要查看具体内容,请调用 get_long_term_memory 工具来获取全文。"
            )
        if knowledge:
            sections.append(
                f"知识库索引: 系统中检索到 {knowledge_count} 条与当前问题相关的知识库片段。"
                f"如果你需要查看具体内容,请调用 get_knowledge_context 工具来获取全文。"
            )
        if has_refs:
            sections.append("--- 参考材料结束 ---")
        if len(sections) <= 4 and not has_history:
            return "", metrics, recall_details
        return "\n".join(sections), metrics, recall_details

    def _rebuild_messages_for_compressed_context(
        self,
        *,
        user_id: str,
        session_id: str,
        current_prompt: str,
        history: list[MessageOut],
    ) -> list[BaseMessage]:
        """
        在上下文接近 token 上限时重建更紧凑的消息列表。

        user_id: 用户 ID。
        session_id: 会话 ID。
        current_prompt: 当前用户输入。
        history: 已裁剪后的近期历史消息。
        """

        messages: list[BaseMessage] = []
        memory_context, rag_metrics, recall_details = self._build_retrieved_context(
            user_id=user_id,
            session_id=session_id,
            current_prompt=current_prompt,
            has_history=bool(history),
        )
        if memory_context:
            messages.append(
                SystemMessage(
                    content=memory_context,
                    additional_kwargs={"rag_metrics": rag_metrics, "recall_details": recall_details},
                )
            )
        messages.extend(self._to_langchain_message(message) for message in history)
        messages = self._filter_orphaned_tool_messages(messages)
        messages.append(HumanMessage(content=current_prompt))
        return messages

    @staticmethod
    def estimate_messages_tokens(messages: list[BaseMessage]) -> int:
        """
        使用轻量字符启发式估算消息 token 数量。

        messages: 待估算的 LangChain 消息列表。
        """

        total_characters = 0
        for message in messages:
            total_characters += len(str(getattr(message, "content", "") or ""))
            tool_calls = getattr(message, "tool_calls", []) or []
            if tool_calls:
                total_characters += len(str(tool_calls))
        return max(1, total_characters // 4)

    @staticmethod
    def _filter_orphaned_tool_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
        """
        过滤孤立的 ToolMessage:其 tool_call_id 对应的 AIMessage 不在消息列表中。
        历史加载窗口或上下文裁剪可能截断 AIMessage 而留下 ToolMessage,导致 API 400 错误。
        """

        normalized: list[BaseMessage] = []
        index = 0
        total = len(messages)

        while index < total:
            message = messages[index]

            if isinstance(message, ToolMessage):
                index += 1
                continue

            if not isinstance(message, AIMessage) or not getattr(message, "tool_calls", None):
                normalized.append(message)
                index += 1
                continue

            required_ids: list[str] = []
            for tool_call in getattr(message, "tool_calls", []) or []:
                tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                if tool_call_id:
                    required_ids.append(str(tool_call_id))

            if not required_ids:
                normalized.append(message)
                index += 1
                continue

            next_index = index + 1
            trailing_tool_messages: list[ToolMessage] = []
            matched_ids: set[str] = set()
            required_id_set = set(required_ids)

            while next_index < total and isinstance(messages[next_index], ToolMessage):
                tool_message = messages[next_index]
                tool_call_id = getattr(tool_message, "tool_call_id", None)
                if tool_call_id in required_id_set:
                    trailing_tool_messages.append(tool_message)
                    matched_ids.add(str(tool_call_id))
                next_index += 1

            if matched_ids == required_id_set:
                normalized.append(message)
                normalized.extend(trailing_tool_messages)
            index = next_index

        return normalized

    @staticmethod
    def _to_langchain_message(message: MessageOut) -> BaseMessage:
        """
        将数据库消息 DTO 转换为 LangChain message。

        message: 数据库消息输出 DTO。
        """

        if message.role == "user":
            return HumanMessage(content=message.content)
        if message.role == "assistant":
            additional_kwargs: dict[str, Any] = {}
            if message.tool_calls_json:
                additional_kwargs["tool_calls"] = message.tool_calls_json
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
