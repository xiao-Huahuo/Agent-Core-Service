"""
Structured generation service tests.

功能说明:
验证通用结构化字段生成服务不依赖 Agent 流式输出,可以从多种 JSON 形态中提取字段,
并对空字段、无效 JSON 和标签选项错误返回字段级失败。

使用说明:
运行 `python -m pytest tests/test_structured_generation_service.py`。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import agent_service.services.structured_generation_service as structured_generation_module
from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.structured_generation import (
    StructuredGenerationField,
    StructuredGenerationRequest,
    StructuredGenerationSource,
)
from agent_service.services.structured_generation_service import StructuredGenerationService


def make_request(*, fields: list[StructuredGenerationField] | None = None) -> StructuredGenerationRequest:
    """构造测试用结构化生成请求。"""

    return StructuredGenerationRequest(
        user_id="u1",
        source=StructuredGenerationSource(kind="literature_document", content="A paper about ROS signaling."),
        fields=fields or [
            StructuredGenerationField(id="title", title="标题", type="text"),
            StructuredGenerationField(id="paper_type", title="文献类型", type="tag", options=["研究论文", "综述论文"]),
        ],
    )


def make_service(raw: str) -> StructuredGenerationService:
    """构造返回固定模型文本的服务实例。"""

    config = AgentConfig.load_config(ensure_directories=False, ensure_models=False)
    return StructuredGenerationService(config=config, chat_invoker=lambda _messages, _user_id: raw)


def test_structured_generation_reads_fenced_fields_json() -> None:
    """fenced JSON fields 列表应解析为逐字段 ready。"""

    service = make_service('```json\n{"fields":[{"id":"title","value":"ROS signaling"},{"id":"paper_type","value":"研究论文"}]}\n```')

    response = service.generate_fields(make_request())

    assert [(item.field_id, item.status, item.value) for item in response.results] == [
        ("title", "ready", "ROS signaling"),
        ("paper_type", "ready", "研究论文"),
    ]


def test_structured_generation_reads_nested_values_json() -> None:
    """values 对象形态应被兼容,避免调用方绑定单一模型输出结构。"""

    service = make_service('prefix {"values":{"title":"Nested title","paper_type":"综述论文"}} suffix')

    response = service.generate_fields(make_request())

    assert response.results[0].value == "Nested title"
    assert response.results[1].value == "综述论文"


def test_structured_generation_marks_invalid_json_failed_per_field() -> None:
    """无有效 JSON 时不能伪装成功,每个字段都应返回 failed。"""

    response = make_service("not json").generate_fields(make_request())

    assert [item.status for item in response.results] == ["failed", "failed"]
    assert response.results[0].error == "模型未返回有效 JSON"


def test_structured_generation_marks_empty_field_failed() -> None:
    """必填字段为空时应字段级失败。"""

    response = make_service('{"fields":[{"id":"title","value":""},{"id":"paper_type","value":"研究论文"}]}').generate_fields(make_request())

    assert response.results[0].status == "failed"
    assert response.results[0].error == "字段为空"
    assert response.results[1].status == "ready"


def test_structured_generation_rejects_tag_outside_options() -> None:
    """标签字段提供 options 时,模型返回非候选标签应失败。"""

    response = make_service('{"paper_type":"新闻"}').generate_fields(make_request())

    assert response.results[1].status == "failed"
    assert "标签不在可选项内" in response.results[1].error


def test_structured_generation_uses_foreground_small_model_queue(monkeypatch) -> None:
    """用户点击触发的结构化生成必须避开后台事实队列,同时继续使用小模型层。"""

    scheduler = MagicMock()
    scheduler.invoke_chat.return_value = SimpleNamespace(content='{"title":"Fast","paper_type":"研究论文"}')
    monkeypatch.setattr(
        structured_generation_module,
        "get_user_llm_overrides",
        lambda _configurable: (None, None, None, None, None, None),
    )
    service = StructuredGenerationService(
        config=AgentConfig.load_config(ensure_directories=False, ensure_models=False),
        task_scheduler=scheduler,
    )

    response = service.generate_fields(make_request())

    assert response.results[0].value == "Fast"
    assert scheduler.invoke_chat.call_args.kwargs["task_type"] == "foreground_agent"
    assert scheduler.invoke_chat.call_args.kwargs["model_tier"] == "small"
