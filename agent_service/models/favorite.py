"""
Favorite database models.

功能说明:
本文件定义用户收藏的 SQLModel 表模型。收藏属于用户级业务数据,必须通过后端
SQLite 持久化,禁止用浏览器存储或临时 JSON 文件保存。

使用说明:
业务层应通过 `agent_service.services.favorite_service.FavoriteService` 操作本模型。
`target_type` 用于区分知识库文件、图书馆条目和 Agent 会话,`library_id` 用于隔离
同一用户的不同知识库收藏。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


def utc_now() -> datetime:
    """Return the current UTC time for favorite creation timestamps."""

    return datetime.now(timezone.utc)


class FavoriteRecord(SQLModel, table=True):
    """
    用户收藏数据库模型。

    favorite_id: 收藏主键,由服务层生成。
    user_id: 收藏所属用户。
    library_id: 知识库作用域;会话收藏可为空字符串。
    target_type: 收藏目标类型,如 knowledge_path/library_item/session。
    target_id: 目标业务 ID,如文件相对路径、图书馆 item_id、session_id。
    created_at: 收藏创建时间。
    """

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", "target_type", "target_id", name="uq_favorites_target"),
    )

    favorite_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, min_length=1, max_length=128)
    library_id: str = Field(default="", index=True, max_length=128)
    target_type: str = Field(index=True, min_length=1, max_length=64)
    target_id: str = Field(index=True, min_length=1, max_length=2048)
    created_at: datetime = Field(default_factory=utc_now, index=True)
