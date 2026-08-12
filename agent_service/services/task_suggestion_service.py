"""
Agent task suggestion service.

Usage:
Builds three short follow-up tasks from the current persisted conversation.
The service prefers the configured small model, falls back to the primary
model when the small model is unavailable, and only then uses local suggestions.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.agent_core.agent_core import AgentCore
from agent_service.services.message_service import MessageService
from agent_service.services.scheduler import BACKGROUND_SUMMARY_TASK, LARGE_MODEL_TIER, SMALL_MODEL_TIER

logger = logging.getLogger(__name__)


class TaskSuggestionService:
    """Generate compact next-step prompts for an Agent chat session."""

    def __init__(self, *, agent: AgentCore, message_service: MessageService) -> None:
        """Store the model runtime and message reader used by suggestion generation."""

        self.agent = agent
        self.message_service = message_service

    def generate_suggestions(self, *, user_id: str, session_id: str, limit: int = 50) -> dict[str, Any]:
        """Return up to three follow-up suggestions for the given persisted session."""

        messages = self.message_service.list_session_messages(
            user_id=user_id,
            session_id=session_id,
            limit=max(4, min(limit, 80)),
            exclude_roles=["system", "tool"],
        )
        conversation = self._format_conversation(messages)
        if not conversation:
            logger.info("Task suggestions skipped: empty conversation | user=%s session=%s", user_id, session_id)
            return {"suggestions": []}

        llm_config = self.agent._get_user_llm_config(user_id) or {}
        suggestions = self._generate_with_small_model(
            user_id=user_id,
            session_id=session_id,
            conversation=conversation,
            llm_config=llm_config,
        )
        # A background-model timeout is not worth another user-visible wait.
        if suggestions is None:
            return {"suggestions": self._fallback_suggestions(messages)}
        if not suggestions:
            suggestions = self._generate_with_large_model(
                user_id=user_id,
                session_id=session_id,
                conversation=conversation,
                llm_config=llm_config,
            )
        if not suggestions:
            suggestions = self._fallback_suggestions(messages)

        return {"suggestions": suggestions}

    def _generate_with_small_model(
        self,
        *,
        user_id: str,
        session_id: str,
        conversation: str,
        llm_config: dict[str, Any],
    ) -> list[str] | None:
        """Try the configured small model and return an empty list on failure."""

        try:
            response = self.agent.task_scheduler.invoke_chat(
                task_type=BACKGROUND_SUMMARY_TASK,
                messages=self._model_messages(conversation),
                tool_names=[],
                model_tier=SMALL_MODEL_TIER,
                temperature=0.35,
                timeout_seconds=20,
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model_name=llm_config.get("model_name"),
                small_api_key=llm_config.get("small_api_key") or llm_config.get("api_key"),
                small_base_url=llm_config.get("small_base_url") or llm_config.get("base_url"),
                small_model_name=llm_config.get("small_model_name") or llm_config.get("model_name"),
            )
            self._record_token_usage(
                user_id=user_id,
                session_id=session_id,
                response=response,
                model_tier=SMALL_MODEL_TIER,
            )
            suggestions = self._parse_suggestions(getattr(response, "content", ""))
            logger.debug(
                "Task suggestion small model output parsed | user=%s session=%s count=%s",
                user_id,
                session_id,
                len(suggestions),
            )
            return suggestions
        except FutureTimeoutError:
            logger.warning(
                "Task suggestion small model timed out; using local fallback | user=%s session=%s",
                user_id,
                session_id,
            )
            return None
        except Exception as exc:
            logger.warning(
                "Task suggestion small model failed, falling back to primary model | user=%s session=%s error=%s",
                user_id,
                session_id,
                exc,
            )
            return []

    def _generate_with_large_model(
        self,
        *,
        user_id: str,
        session_id: str,
        conversation: str,
        llm_config: dict[str, Any],
    ) -> list[str]:
        """Try the primary model and return an empty list on failure."""

        try:
            response = self.agent.task_scheduler.invoke_chat(
                task_type=BACKGROUND_SUMMARY_TASK,
                messages=self._model_messages(conversation),
                tool_names=[],
                model_tier=LARGE_MODEL_TIER,
                temperature=0.35,
                timeout_seconds=20,
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                model_name=llm_config.get("model_name"),
            )
            self._record_token_usage(
                user_id=user_id,
                session_id=session_id,
                response=response,
                model_tier=LARGE_MODEL_TIER,
            )
            suggestions = self._parse_suggestions(getattr(response, "content", ""))
            logger.debug(
                "Task suggestion primary model output parsed | user=%s session=%s count=%s",
                user_id,
                session_id,
                len(suggestions),
            )
            return suggestions
        except Exception as exc:
            logger.warning(
                "Task suggestion primary model failed, using local fallback | user=%s session=%s error=%s",
                user_id,
                session_id,
                exc,
            )
            return []

    def _record_token_usage(self, *, user_id: str, session_id: str, response: Any, model_tier: str) -> None:
        """Record task suggestion LLM usage without affecting session total charts."""

        self.message_service.token_usage_service.record_llm_response_token_usage(
            user_id=user_id,
            session_id=None,
            response=response,
            node="task_suggestion",
            event="suggestions_generated",
            model_tier=model_tier,
            source_id=f"task_suggestion_{session_id}",
        )

    @classmethod
    def _model_messages(cls, conversation: str) -> list[Any]:
        """Build the fixed prompt used for next-task generation."""

        return [
            SystemMessage(content=cls._system_prompt()),
            HumanMessage(content=f"当前对话上下文:\n{conversation}\n\n只输出 JSON。"),
        ]

    @staticmethod
    def _system_prompt() -> str:
        """Return the fixed instruction used for next-task generation."""

        return (
            "你是对话下一步任务推荐器。基于完整上下文，提出用户最可能继续点击的 3 个问题或任务。"
            "要求: 每条不超过 28 个中文字符；使用用户会自然发送给 Agent 的第一人称或祈使句；"
            "避免客套、寒暄、解释和重复已经完成的事；需要能直接作为下一轮用户输入。"
            '只输出 JSON: {"suggestions":["...","...","..."]}'
        )

    @staticmethod
    def _format_conversation(messages: list[Any]) -> str:
        """Compress persisted messages into a model prompt while preserving order."""

        lines: list[str] = []
        for message in messages:
            role = getattr(message, "role", "")
            content = (getattr(message, "content", "") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            label = "用户" if role == "user" else "Agent"
            preview = re.sub(r"\s+", " ", content)[:900]
            lines.append(f"{label}: {preview}")
        return "\n".join(lines)[-8000:]

    @staticmethod
    def _parse_suggestions(content: str) -> list[str]:
        """Parse and sanitize model output into at most three unique suggestions."""

        text = (content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        if "{" in text and "}" in text:
            text = text[text.find("{"):text.rfind("}") + 1]
        raw_items: list[Any] = []
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                raw_items = data.get("suggestions", [])
            elif isinstance(data, list):
                raw_items = data
        except json.JSONDecodeError:
            raw_items = [line.strip("- \u3000\t") for line in text.splitlines()]

        return TaskSuggestionService._sanitize_suggestions(raw_items)

    @staticmethod
    def _fallback_suggestions(messages: list[Any]) -> list[str]:
        """Build stable local suggestions when both background models are unavailable."""

        last_user = ""
        for message in reversed(messages):
            if getattr(message, "role", "") != "user":
                continue
            content = re.sub(r"\s+", " ", (getattr(message, "content", "") or "")).strip()
            if content:
                last_user = content
                break

        topic = last_user[:24].strip(" \t\r\n,.;，。；")
        candidates = [
            f"继续处理：{topic}" if topic else "继续处理当前问题",
            "把上面的结论整理成待办",
            "基于当前结果继续下一步",
        ]
        return TaskSuggestionService._sanitize_suggestions(candidates)

    @staticmethod
    def _sanitize_suggestions(raw_items: list[Any]) -> list[str]:
        """Normalize arbitrary suggestion-like values into three display strings."""

        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            suggestion = re.sub(r"\s+", " ", str(item or "")).strip(" \t\r\n\"'，。；;")
            if not suggestion or suggestion in seen:
                continue
            seen.add(suggestion)
            result.append(suggestion[:80])
            if len(result) >= 3:
                break
        return result
