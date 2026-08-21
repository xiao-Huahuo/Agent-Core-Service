"""Agent task queue REST and gRPC request DTOs.

Usage:
REST endpoints validate these DTOs before passing only typed data to
``AgentQueueService``. The same dictionary fields are accepted by the gRPC
Struct endpoints to keep both transports behaviorally identical.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS


AgentQueuePriority = Literal["critical", "high", "medium", "low", "whenever"]
AgentQueueTransition = Literal["confirmed", "terminated"]


class AgentQueueTaskCreate(BaseModel):
    """Create a queued Agent task and bind it to an existing isolated session."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    prompt: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    priority: AgentQueuePriority = "medium"
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.standard_id_max_length)


class AgentQueueTaskUpdate(BaseModel):
    """Edit prompt, priority, and attachment references before a task is claimed."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    prompt: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    priority: AgentQueuePriority
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class AgentQueueTaskContinue(BaseModel):
    """Queue a new prompt in the task's existing session after review."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    prompt: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class AgentQueueTaskTransitionRequest(BaseModel):
    """Confirm a reviewed task or terminate a pending/running/review task."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    status: AgentQueueTransition


class AgentQueueSettingsUpdate(BaseModel):
    """Persist the maximum number of independent tasks running for one user."""

    user_id: str = Field(min_length=DEFAULT_BUSINESS_LIMITS.nonempty_min_length, max_length=DEFAULT_BUSINESS_LIMITS.medium_name_max_length)
    max_concurrency: int = Field(
        ge=DEFAULT_BUSINESS_LIMITS.nonempty_min_length,
        le=DEFAULT_BUSINESS_LIMITS.agent_queue_max_concurrency,
    )
