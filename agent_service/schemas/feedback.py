"""
User feedback DTO schemas.

功能说明:
本文件定义用户反馈 REST/gRPC 共享的请求与响应数据结构,避免 API 层直接暴露
数据库模型。

使用说明:
前端提交 `FeedbackCreate` 创建反馈,用 `FeedbackUpdate` 修改反馈内容,列表接口返回
`FeedbackListOut`。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """创建用户反馈 DTO。"""

    user_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="editor_activity_bar", max_length=128)
    page: str = Field(default="", max_length=128)


class FeedbackUpdate(BaseModel):
    """修改用户反馈 DTO。"""

    content: str = Field(min_length=1, max_length=4000)


class FeedbackOut(BaseModel):
    """用户反馈响应 DTO。"""

    feedback_id: str
    user_id: str
    content: str
    source: str
    page: str
    created_at: datetime


class FeedbackListOut(BaseModel):
    """用户反馈列表响应 DTO。"""

    feedback: list[FeedbackOut]
