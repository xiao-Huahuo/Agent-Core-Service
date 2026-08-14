"""
自动化任务 REST/gRPC 共享请求 DTO。

所有写操作先经过严格类型校验，再传入 AutomationService，避免字符串布尔值
或缺失字段被 Python 隐式转换成错误的调度状态。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, StrictBool


AutomationFrequency = Literal["none", "daily", "weekly", "monthly"]
AutomationAccessMode = Literal["readonly", "sandbox", "full_access"]


class AutomationRecurrence(BaseModel):
    """自动化循环频率与间隔。"""

    frequency: AutomationFrequency = "none"
    interval: int = Field(default=1, ge=1, le=365)


class AutomationCreateRequest(BaseModel):
    """创建一条定时自动化及其关联 TODO。"""

    user_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    next_run_at: str = Field(min_length=1)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    recurrence: AutomationRecurrence = Field(default_factory=AutomationRecurrence)
    access_mode: AutomationAccessMode = "sandbox"


class AutomationToggleRequest(BaseModel):
    """严格启用或停用一条自动化。"""

    user_id: str = Field(min_length=1, max_length=128)
    automation_id: str = Field(min_length=1, max_length=64)
    enabled: StrictBool


class AutomationDeleteRequest(BaseModel):
    """删除一条自动化及其 TODO、运行记录。"""

    user_id: str = Field(min_length=1, max_length=128)
    automation_id: str = Field(min_length=1, max_length=64)
