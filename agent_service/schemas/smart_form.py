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


class SmartFormSaveRequest(BaseModel):
    """保存或创建智能表格请求。"""

    user_id: str = Field(min_length=1, max_length=128)
    form_id: str | None = Field(default=None, max_length=64)
    asset_dir: str = Field(default="", max_length=1024)
    form: dict[str, Any]


class SmartFormListItem(BaseModel):
    """智能表格列表条目。"""

    form_id: str
    title: str
    asset_dir: str
    updated_at: datetime


class SmartFormOut(BaseModel):
    """智能表格详情响应。"""

    form_id: str
    user_id: str
    asset_dir: str
    form: dict[str, Any]
    updated_at: datetime
