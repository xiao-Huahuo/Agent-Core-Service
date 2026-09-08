"""
Favorite DTO schemas.

功能说明:
本文件定义收藏 REST API 的请求与响应结构,避免 API 层直接暴露数据库模型。

使用说明:
前端通过 `FavoriteCreate` 增加收藏,通过查询参数读取或删除收藏。`FavoriteOut`
作为统一响应条目。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FavoriteTargetType = Literal["knowledge_path", "library_item", "component", "session", "smart_form_row", "scanner"]


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class FavoriteCreate(BaseModel):
    """创建收藏 DTO。"""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    target_type: FavoriteTargetType
    target_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.path_max_length)
    library_id: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)


class FavoriteOut(BaseModel):
    """收藏响应 DTO。"""

    favorite_id: str
    user_id: str
    library_id: str
    target_type: FavoriteTargetType
    target_id: str
    created_at: datetime


class FavoriteListOut(BaseModel):
    """收藏列表响应 DTO。"""

    favorites: list[FavoriteOut]
