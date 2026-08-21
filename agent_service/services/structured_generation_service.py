"""
Structured field generation service.

功能说明:
本服务提供通用的"上下文 + 字段定义 -> 字段结果"结构化生成能力。它复用项目的
LLM 调度器和用户模型配置,但不进入 Agent 对话图、不加载记忆、不做聊天输出清洗,
因此模型返回的 JSON 只在后端消费并被严格校验后返回给业务调用方。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_service.agent_core.nodes.model_decision import get_user_llm_overrides
from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.structured_generation import (
    StructuredGenerationField,
    StructuredGenerationFieldResult,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from agent_service.services.scheduler import (
    BACKGROUND_FACT_RESOLUTION_TASK,
    SMALL_MODEL_TIER,
    LLMTaskScheduler,
    get_llm_task_scheduler,
)

ChatInvoker = Callable[[list[Any], str], Any]


class StructuredGenerationService:
    """通用结构化字段生成服务。"""

    def __init__(
        self,
        *,
        config: AgentConfig,
        task_scheduler: LLMTaskScheduler | None = None,
        chat_invoker: ChatInvoker | None = None,
    ) -> None:
        """保存配置和可测试的模型调用入口。"""

        self.config = config
        self.task_scheduler = task_scheduler or get_llm_task_scheduler(config)
        self.chat_invoker = chat_invoker

    def generate_fields(self, request: StructuredGenerationRequest) -> StructuredGenerationResponse:
        """按字段定义生成结构化结果,并把解析或校验失败降级为字段级 failed。"""

        if not request.source.content.strip():
            return StructuredGenerationResponse(
                results=[
                    StructuredGenerationFieldResult(field_id=field.id, status="failed", error="缺少生成上下文")
                    for field in request.fields
                ],
                raw_output="",
            )
        messages = self._build_messages(request)
        try:
            raw_output = self._invoke_model(messages, request.user_id)
            parsed = parse_json_object(raw_output)
        except Exception as exc:  # noqa: BLE001
            return StructuredGenerationResponse(
                results=[
                    StructuredGenerationFieldResult(field_id=field.id, status="failed", error=str(exc))
                    for field in request.fields
                ],
                raw_output=locals().get("raw_output", ""),
            )
        return StructuredGenerationResponse(
            results=[self._validate_field_result(field, parsed) for field in request.fields],
            raw_output=raw_output,
        )

    def _invoke_model(self, messages: list[Any], user_id: str) -> str:
        """调用底层聊天模型并返回原始文本内容。"""

        if self.chat_invoker is not None:
            response = self.chat_invoker(messages, user_id)
        else:
            (
                user_api_key,
                user_base_url,
                user_model_name,
                user_small_api_key,
                user_small_base_url,
                user_small_model_name,
            ) = get_user_llm_overrides({"user_id": user_id})
            response = self.task_scheduler.invoke_chat(
                task_type=BACKGROUND_FACT_RESOLUTION_TASK,
                messages=messages,
                tool_names=[],
                temperature=0.0,
                model_tier=SMALL_MODEL_TIER,
                api_key=user_api_key,
                base_url=user_base_url,
                model_name=user_model_name,
                small_api_key=user_small_api_key,
                small_base_url=user_small_base_url,
                small_model_name=user_small_model_name,
            )
        content = getattr(response, "content", response)
        if isinstance(content, str):
            raw = content
        elif isinstance(content, list):
            raw = "".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
        else:
            raw = str(content or "")
        if not raw.strip():
            raise ValueError("模型未返回内容")
        return raw

    def _build_messages(self, request: StructuredGenerationRequest) -> list[Any]:
        """构造通用结构化字段生成提示。"""

        fields = [
            {
                "id": field.id,
                "title": field.title,
                "type": field.type,
                "description": field.description,
                "options": field.options,
                "required": field.required,
            }
            for field in request.fields
        ]
        system = self.config.prompts.structured_generation_system_prompt
        user = "\n".join([
            f"来源类型: {request.source.kind}",
            f"语言: {request.options.language}",
            "字段定义:",
            json.dumps(fields, ensure_ascii=False, indent=2),
            "上下文:",
            request.source.content[:self.config.limits.structured_prompt_source_chars],
        ])
        return [SystemMessage(content=system), HumanMessage(content=user)]

    def _validate_field_result(self, field: StructuredGenerationField, payload: dict[str, Any]) -> StructuredGenerationFieldResult:
        """从多种 JSON 形态中取出字段值并做字段级校验。"""

        marker = object()
        raw_value = extract_field_value(payload, field.id, marker)
        if raw_value is marker:
            return StructuredGenerationFieldResult(field_id=field.id, status="failed", error="模型结果缺少字段")
        value = normalize_value(raw_value)
        if field.required and not value:
            return StructuredGenerationFieldResult(field_id=field.id, status="failed", value="", error="字段为空", raw_value=raw_value)
        if field.type == "tag" and field.options and value:
            tags = split_tag_value(value)
            invalid = [tag for tag in tags if tag not in field.options]
            if invalid:
                return StructuredGenerationFieldResult(
                    field_id=field.id,
                    status="failed",
                    value=value,
                    error=f"标签不在可选项内: {', '.join(invalid)}",
                    raw_value=raw_value,
                )
            value = "; ".join(tags)
        return StructuredGenerationFieldResult(field_id=field.id, status="ready", value=value, raw_value=raw_value)


def parse_json_object(text: str) -> dict[str, Any]:
    """从 fenced JSON、普通文本或裸 JSON 中提取第一个 JSON object。"""

    source = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", source, flags=re.IGNORECASE)
    if fenced:
        source = fenced.group(1).strip()
    candidate = first_json_object(source)
    if not candidate:
        raise ValueError("模型未返回有效 JSON")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("模型 JSON 解析失败") from exc
    if not isinstance(parsed, dict):
        raise ValueError("模型 JSON 顶层不是对象")
    return parsed


def first_json_object(text: str) -> str:
    """返回文本中的第一个完整顶层 JSON object 字符串。"""

    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = in_string
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if depth == 0:
            return text[start:index + 1]
    return ""


def extract_field_value(payload: dict[str, Any], field_id: str, default: Any) -> Any:
    """兼容 fields/results 列表、values 对象和直接字段映射三种模型 JSON 形态。"""

    for list_key in ("fields", "results"):
        items = payload.get(list_key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and str(item.get("id") or item.get("field_id") or "") == field_id:
                    return item.get("value", default)
    values = payload.get("values")
    if isinstance(values, dict) and field_id in values:
        return values[field_id]
    return payload.get(field_id, default)


def normalize_value(value: Any) -> str:
    """将模型字段值归一为前端可写入的字符串。"""

    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(normalize_value(item) for item in value if normalize_value(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def split_tag_value(value: str) -> list[str]:
    """按常见中英文分隔符拆分标签值。"""

    return [part.strip() for part in re.split(r"[;,，、；]+", value) if part.strip()]
