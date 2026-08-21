"""
自动化任务 REST/gRPC 共享请求 DTO。

所有写操作先经过严格类型校验，再传入 AutomationService，避免字符串布尔值
或缺失字段被 Python 隐式转换成错误的调度状态。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, StrictBool

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS


AutomationFrequency = Literal["none", "daily", "weekly", "monthly"]
AutomationAccessMode = Literal["readonly", "sandbox", "full_access"]


class AutomationRecurrence(BaseModel):
    """自动化循环频率与间隔。"""

    frequency: AutomationFrequency = "none"
    interval: int = Field(
        default=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.todo_recurrence_max_interval,
    )


class AutomationCreateRequest(BaseModel):
    """创建一条定时自动化及其关联 TODO。"""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    text: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    prompt: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    next_run_at: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    timezone: str = Field(default="UTC", min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    recurrence: AutomationRecurrence = Field(default_factory=AutomationRecurrence)
    access_mode: AutomationAccessMode = "sandbox"


class AutomationToggleRequest(BaseModel):
    """严格启用或停用一条自动化。"""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    automation_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
    enabled: StrictBool


class AutomationDeleteRequest(BaseModel):
    """删除一条自动化及其 TODO、运行记录。"""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    automation_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)
