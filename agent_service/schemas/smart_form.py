"""
Smart form DTO schemas.

功能说明:
本文件定义智能表格 REST API 的请求与响应结构。为保持前端已有智能表格结构兼容,
表格主体使用字典传输,后端服务负责校验必要字段并拆分写入关系表。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class SmartFormSaveRequest(BaseModel):
    """保存或创建智能表格请求。"""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    form_id: str | None = Field(default=None, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    library_id: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.graph_identifier_max_length)
    form_kind: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.short_type_max_length)
    asset_dir: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.secret_max_length)
    form: dict[str, Any]


class SmartFormListItem(BaseModel):
    """智能表格列表条目。"""

    form_id: str
    title: str
    asset_dir: str
    library_id: str = ""
    form_kind: str = "literature"
    updated_at: datetime


class SmartFormOut(BaseModel):
    """智能表格详情响应。"""

    form_id: str
    user_id: str
    asset_dir: str
    library_id: str = ""
    form_kind: str = "literature"
    form: dict[str, Any]
    updated_at: datetime
