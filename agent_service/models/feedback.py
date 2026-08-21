"""
User feedback database model.

功能说明:
本文件定义用户反馈 SQLModel 表。用户反馈属于业务数据,必须通过后端数据库
持久化,禁止使用浏览器存储或临时 JSON 文件保存。

使用说明:
业务层通过 `agent_service.services.feedback_service.FeedbackService` 写入反馈记录。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC time for feedback creation timestamps."""

    return datetime.now(timezone.utc)


from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

class FeedbackRecord(SQLModel, table=True):
    """
    用户反馈数据库模型。

    feedback_id: 反馈主键,由服务层生成。
    user_id: 提交反馈的用户。
    content: 用户提交的反馈正文。
    source: 反馈来源入口,如 editor_activity_bar。
    page: 提交时所在前端页面或主视图。
    created_at: 反馈创建时间。
    """

    __tablename__ = "feedback"

    feedback_id: str = Field(primary_key=True, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    user_id: str = Field(index=True, min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    content: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.feedback_content_max_length)
    source: str = Field(default="editor_activity_bar", max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    page: str = Field(default="", max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    created_at: datetime = Field(default_factory=utc_now, index=True)
