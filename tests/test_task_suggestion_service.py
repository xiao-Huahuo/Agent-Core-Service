"""
Task suggestion service tests.

Usage:
Validates parsing, small-to-large model fallback, and final local fallback
behavior without calling a real model.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from agent_service.services.scheduler import LARGE_MODEL_TIER, SMALL_MODEL_TIER
from agent_service.services.task_suggestion_service import TaskSuggestionService


@dataclass
class _Message:
    role: str
    content: str


class _FakeMessageService:
    def __init__(self) -> None:
        self.token_usage_service = _FakeTokenUsageService()

    def list_session_messages(self, **_: Any) -> list[_Message]:
        return [
            _Message("user", "帮我分析一下这个知识库"),
            _Message("assistant", "已经发现重复实体和图谱显示问题。"),
        ]


class _FakeTokenUsageService:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record_llm_response_token_usage(self, **kwargs: Any) -> int:
        self.records.append(kwargs)
        return 1


class _FakeScheduler:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def invoke_chat(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            content=response,
            usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        )


class _FakeAgent:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.task_scheduler = _FakeScheduler(responses)

    @staticmethod
    def _get_user_llm_config(_: str) -> dict[str, str]:
        return {
            "api_key": "large-key",
            "base_url": "https://large.example/v1",
            "small_api_key": "small-key",
            "small_base_url": "https://small.example/v1",
        }


def test_generate_suggestions_parses_three_unique_items_from_small_model() -> None:
    """The service should use the small model result when it succeeds."""

    agent = _FakeAgent(['{"suggestions":["继续修复图谱布局","继续修复图谱布局","补充测试报告","整理成待办"]}'])
    message_service = _FakeMessageService()
    service = TaskSuggestionService(agent=agent, message_service=message_service)  # type: ignore[arg-type]

    payload = service.generate_suggestions(user_id="u1", session_id="s1")

    assert payload["suggestions"] == ["继续修复图谱布局", "补充测试报告", "整理成待办"]
    assert len(agent.task_scheduler.calls) == 1
    call = agent.task_scheduler.calls[0]
    assert call["model_tier"] == SMALL_MODEL_TIER
    assert call["small_api_key"] == "small-key"
    assert call["small_base_url"] == "https://small.example/v1"
    assert message_service.token_usage_service.records[0]["session_id"] is None
    assert message_service.token_usage_service.records[0]["node"] == "task_suggestion"
    assert message_service.token_usage_service.records[0]["model_tier"] == SMALL_MODEL_TIER


def test_generate_suggestions_falls_back_to_large_model_when_small_model_fails() -> None:
    """Small-model quota failures should retry through the primary model before local fallback."""

    agent = _FakeAgent(
        [
            RuntimeError("small quota exhausted"),
            '{"suggestions":["用主模型继续推荐","补充关键测试","整理实现说明"]}',
        ]
    )
    message_service = _FakeMessageService()
    service = TaskSuggestionService(agent=agent, message_service=message_service)  # type: ignore[arg-type]

    payload = service.generate_suggestions(user_id="u1", session_id="s1")

    assert payload["suggestions"] == ["用主模型继续推荐", "补充关键测试", "整理实现说明"]
    assert [call["model_tier"] for call in agent.task_scheduler.calls] == [SMALL_MODEL_TIER, LARGE_MODEL_TIER]
    assert "small_api_key" not in agent.task_scheduler.calls[1]
    assert agent.task_scheduler.calls[1]["api_key"] == "large-key"
    assert agent.task_scheduler.calls[1]["base_url"] == "https://large.example/v1"
    assert message_service.token_usage_service.records[0]["model_tier"] == LARGE_MODEL_TIER


def test_generate_suggestions_uses_local_fallback_when_both_models_fail() -> None:
    """A double model failure should still not make the suggestion API return 500."""

    agent = _FakeAgent([RuntimeError("small quota exhausted"), RuntimeError("primary unavailable")])
    service = TaskSuggestionService(agent=agent, message_service=_FakeMessageService())  # type: ignore[arg-type]

    payload = service.generate_suggestions(user_id="u1", session_id="s1")

    assert payload["suggestions"] == [
        "继续处理：帮我分析一下这个知识库",
        "把上面的结论整理成待办",
        "基于当前结果继续下一步",
    ]
    assert [call["model_tier"] for call in agent.task_scheduler.calls] == [SMALL_MODEL_TIER, LARGE_MODEL_TIER]


def test_parse_suggestions_accepts_plain_lines() -> None:
    """Fallback parsing should handle non-JSON model output."""

    suggestions = TaskSuggestionService._parse_suggestions("- A\n- B\n- B\n- C\n- D")

    assert suggestions == ["A", "B", "C"]
