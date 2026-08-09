"""
Structured field generation DTO schemas.

功能说明:
本文件定义通用结构化字段生成 REST API 的请求与响应结构。调用方提供一段上下文
和字段定义,后端返回逐字段的生成结果与失败原因。该能力不属于 Agent 对话链路,
供智能表格、知识库标签、图书馆元数据等业务复用。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StructuredFieldType = Literal["text", "tag", "number", "boolean", "date"]
StructuredFieldStatus = Literal["ready", "failed"]


class StructuredGenerationSource(BaseModel):
    """字段生成的数据来源。"""

    kind: str = Field(min_length=1, max_length=128)
    content: str = Field(default="", max_length=200000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredGenerationField(BaseModel):
    """需要生成的字段定义。"""

    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    type: StructuredFieldType = "text"
    description: str = Field(default="", max_length=1024)
    options: list[str] = Field(default_factory=list)
    required: bool = True


class StructuredGenerationOptions(BaseModel):
    """结构化生成选项。"""

    language: str = Field(default="zh", max_length=32)
    strict_json: bool = True


class StructuredGenerationRequest(BaseModel):
    """结构化字段生成请求。"""

    user_id: str = Field(min_length=1, max_length=128)
    source: StructuredGenerationSource
    fields: list[StructuredGenerationField] = Field(min_length=1, max_length=64)
    options: StructuredGenerationOptions = Field(default_factory=StructuredGenerationOptions)


class StructuredGenerationFieldResult(BaseModel):
    """单个字段的结构化生成结果。"""

    field_id: str
    status: StructuredFieldStatus
    value: str = ""
    error: str = ""
    raw_value: Any = None


class StructuredGenerationResponse(BaseModel):
    """结构化字段生成响应。"""

    results: list[StructuredGenerationFieldResult]
    raw_output: str = ""
