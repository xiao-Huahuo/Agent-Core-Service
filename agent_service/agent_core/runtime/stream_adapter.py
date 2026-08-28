"""AgentCore stream_adapter 职责实现。

本模块由机械迁移生成，方法体保持原业务逻辑。
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
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent_service.agent_core.graph import AgentGraphBuilder
from agent_service.agent_core.nodes.model_decision import ModelDecisionNode
from agent_service.agent_core.runtime import AttachmentRuntime, CancellationRuntime
from agent_service.agent_core.runtime.error_recovery import extract_friendly_error
from agent_service.agent_core.runtime.shared import (
    AGENT_LOOP_AUTO,
    AGENT_LOOP_DEEP_ALIAS,
    AGENT_LOOP_MODES,
    AGENT_LOOP_PLAN,
    AGENT_LOOP_REACT,
    AGENT_LOOP_SIMPLE,
)
from agent_service.agent_core.runtime.token_usage import extract_token_usage
from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.schemas.message import MessageCreate
from agent_service.scripts.draw_agent_graph import draw_agent_graph
from agent_service.services.memory.context_builder import ContextBuilder
from agent_service.services.child_agent import ChildAgentContract, ChildAgentEvent, ChildAgentManager
from agent_service.services.message.service import MessageService
from agent_service.services.session_attachment.service import SessionAttachmentService
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
    clear_context_compression_callback,
    clear_markdown_html_visualization_callback,
    clear_plan_state,
    clear_planner_content_callback,
    clear_observation_content_callback,
    clear_task_list_callback,
    clear_tool_runtime,
    clear_tool_trace_callback,
    get_plan_state,
    set_agent_token_callback,
    set_context_mirror_callback,
    set_context_compression_callback,
    set_markdown_html_visualization_callback,
    set_plan_state,
    set_planner_content_callback,
    set_observation_content_callback,
    set_task_list_callback,
    set_tool_runtime,
    set_tool_trace_callback,
    normalize_agent_access_mode,
)
from agent_service.services.task_list.service import extract_plan_state, merge_plan_state


logger = logging.getLogger(__name__)
CITATION_ANCHOR_PATTERN = re.compile(r"\[([A-Z]?\d+)\]")

class StreamAdapterMixin:
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
        used_citations = StreamAdapterMixin._extract_used_citation_ids(content)
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
        existing_ids = set(StreamAdapterMixin._extract_used_citation_ids(content))
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
            terms = StreamAdapterMixin._citation_match_terms(source)
            if not terms:
                continue
            for index, line in enumerate(lines):
                if f"[{citation_id}]" in line:
                    break
                normalized_line = StreamAdapterMixin._normalize_citation_match_text(line)
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
        for line in content.splitlines()[:DEFAULT_BUSINESS_LIMITS.citation_source_scan_lines]:
            stripped = line.strip()
            if stripped.startswith("#"):
                raw_terms.append(stripped.lstrip("#").strip())
                break
        seen: set[str] = set()
        for term in raw_terms:
            normalized = StreamAdapterMixin._normalize_citation_match_text(term)
            if len(normalized) < DEFAULT_BUSINESS_LIMITS.citation_term_min_chars or normalized in seen:
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
    def _last_human_text(messages: list[BaseMessage]) -> str:
        """Return the latest human message content as plain text."""

        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return StreamAdapterMixin._stringify_content(message.content)
        return ""
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
        content = StreamAdapterMixin._sanitize_agent_output(content or "")
        content = StreamAdapterMixin._drop_unmapped_citation_anchors(content, citation_map)
        content = StreamAdapterMixin._insert_missing_citation_anchors_inline(content, citation_map)
        metadata = StreamAdapterMixin._build_citation_metadata(content, citation_map)
        return {
            "node": node_name,
            "content": content,
            "tool_calls": tool_calls or [],
            "trace": state_update.get("trace", []),
            "metadata": metadata,
        }
    @staticmethod
    def _sanitize_streaming_content(
        cumulative_text: str,
        min_chars: int = AgentConfig.ModelConfig().streaming_sanitize_min_chars,
    ) -> str:
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
