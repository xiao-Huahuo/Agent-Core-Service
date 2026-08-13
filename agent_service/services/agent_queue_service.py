"""Durable priority scheduling for independent Agent sessions.

Usage:
The REST and gRPC transports delegate all queue mutations here.  The scheduler
claims work through :meth:`claim_next`, so priority and concurrency decisions
are made in one place and persisted in the database.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlmodel import Session, SQLModel, select

from agent_service.models.agent_queue import AgentQueueSettingsRecord, AgentQueueTaskRecord
from agent_service.schemas.session import SessionCreate
from agent_service.services.session_service import SessionService


class AgentQueueService:
    """Persist, order, and transition user-owned queue tasks."""

    _PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "whenever": 4}
    _BOARD_STATUSES = ("pending", "running", "review")
    _HISTORY_STATUSES = ("confirmed", "terminated")

    def __init__(self, *, engine: Any, session_service: SessionService) -> None:
        """Bind queue persistence to the application database and session service."""
        self.engine = engine
        self.session_service = session_service
        # ponytail: one app process owns this scheduler; use a database lease if workers become multi-process.
        self._claim_lock = threading.Lock()
        SQLModel.metadata.create_all(engine)

    @staticmethod
    def _now() -> datetime:
        """Return an aware UTC timestamp for persisted state transitions."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        """Serialize optional timestamps for transport responses."""
        return value.isoformat() if value else None

    def _task_list(self, session_id: str | None) -> dict[str, Any] | None:
        """Read the Agent-created checklist without duplicating it in queue storage."""
        if not session_id:
            return None
        try:
            state = json.loads(self.session_service.get_session_state(session_id) or "{}")
        except json.JSONDecodeError:
            return None
        task_list = state.get("task_list") if isinstance(state, dict) else None
        return task_list if isinstance(task_list, dict) else None

    def _serialize(self, record: AgentQueueTaskRecord) -> dict[str, Any]:
        """Convert one database task to the shared REST/gRPC representation."""
        try:
            attachments = json.loads(record.attachments_json)
        except json.JSONDecodeError:
            attachments = []
        return {
            "task_id": record.task_id,
            "user_id": record.user_id,
            "prompt": record.prompt,
            "priority": record.priority,
            "status": record.status,
            "session_id": record.session_id,
            "attachments": attachments if isinstance(attachments, list) else [],
            "previous_task_id": record.previous_task_id,
            "started_at": self._iso(record.started_at),
            "finished_at": self._iso(record.finished_at),
            "terminated_at": self._iso(record.terminated_at),
            "created_at": self._iso(record.created_at),
            "updated_at": self._iso(record.updated_at),
            "task_list": self._task_list(record.session_id),
        }

    def get_settings(self, user_id: str) -> dict[str, int]:
        """Return the user's persisted concurrency override or service default."""
        with Session(self.engine) as db:
            settings = db.get(AgentQueueSettingsRecord, user_id)
            return {"max_concurrency": settings.max_concurrency if settings else 5}

    def update_settings(self, user_id: str, max_concurrency: int) -> dict[str, int]:
        """Persist an explicit per-user concurrency override."""
        if not 1 <= max_concurrency <= 20:
            raise ValueError("max_concurrency must be between 1 and 20")
        with Session(self.engine) as db:
            settings = db.get(AgentQueueSettingsRecord, user_id)
            if settings is None:
                settings = AgentQueueSettingsRecord(user_id=user_id)
            settings.max_concurrency = max_concurrency
            settings.updated_at = self._now()
            db.add(settings)
            db.commit()
        return {"max_concurrency": max_concurrency}

    def create_task(self, *, user_id: str, prompt: str, priority: str = "medium", attachments: list[dict[str, Any]] | None = None, session_id: str | None = None, previous_task_id: str | None = None) -> dict[str, Any]:
        """Create a pending task with one private Agent session for its attachments and history."""
        if not prompt.strip():
            raise ValueError("prompt is required")
        if priority not in self._PRIORITY_ORDER:
            raise ValueError("invalid priority")
        now = self._now()
        task_session_id = session_id or self.session_service.create_session(
            SessionCreate(user_id=user_id, session_name=prompt[:80])
        ).session_id
        record = AgentQueueTaskRecord(
            task_id=f"queue_{uuid4().hex[:12]}",
            user_id=user_id,
            prompt=prompt.strip(),
            priority=priority,
            session_id=task_session_id,
            attachments_json=json.dumps(attachments or [], ensure_ascii=False),
            previous_task_id=previous_task_id,
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def list_tasks(self, *, user_id: str, history: bool = False) -> list[dict[str, Any]]:
        """List live board tasks or terminal history in stable priority order."""
        statuses = self._HISTORY_STATUSES if history else self._BOARD_STATUSES
        with Session(self.engine) as db:
            records = db.exec(
                select(AgentQueueTaskRecord).where(
                    AgentQueueTaskRecord.user_id == user_id,
                    AgentQueueTaskRecord.status.in_(statuses),
                )
            ).all()
        return [self._serialize(record) for record in sorted(records, key=lambda item: (self._PRIORITY_ORDER[item.priority], item.created_at))]

    def claim_next(self, user_id: str) -> dict[str, Any] | None:
        """Atomically reserve the highest-priority eligible task for one scheduler worker."""
        with self._claim_lock, Session(self.engine) as db:
            settings = db.get(AgentQueueSettingsRecord, user_id)
            limit = settings.max_concurrency if settings else 5
            running = db.exec(
                select(AgentQueueTaskRecord).where(
                    AgentQueueTaskRecord.user_id == user_id,
                    AgentQueueTaskRecord.status == "running",
                )
            ).all()
            if len(running) >= limit:
                return None
            pending = db.exec(
                select(AgentQueueTaskRecord).where(
                    AgentQueueTaskRecord.user_id == user_id,
                    AgentQueueTaskRecord.status == "pending",
                )
            ).all()
            if not pending:
                return None
            record = min(pending, key=lambda item: (self._PRIORITY_ORDER[item.priority], item.created_at))
            record.status = "running"
            record.started_at = self._now()
            record.updated_at = record.started_at
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def pending_user_ids(self) -> list[str]:
        """Return users with work that may fit an available scheduler slot."""
        with Session(self.engine) as db:
            return list(db.exec(select(AgentQueueTaskRecord.user_id).where(AgentQueueTaskRecord.status == "pending").distinct()).all())

    def finish(self, task_id: str, status: str) -> None:
        """Move a completed worker task to review unless it was already terminated."""
        if status not in {"review", "terminated"}:
            raise ValueError("invalid terminal status")
        with Session(self.engine) as db:
            record = db.get(AgentQueueTaskRecord, task_id)
            if record is None or record.status != "running":
                return
            record.status = status
            record.finished_at = self._now()
            record.updated_at = record.finished_at
            db.add(record)
            db.commit()

    def transition(self, *, user_id: str, task_id: str, status: str) -> dict[str, Any] | None:
        """Confirm a reviewed result or terminate any nonterminal task."""
        if status not in {"confirmed", "terminated"}:
            raise ValueError("invalid status")
        with Session(self.engine) as db:
            record = db.get(AgentQueueTaskRecord, task_id)
            if record is None or record.user_id != user_id:
                return None
            if status == "confirmed" and record.status != "review":
                raise ValueError("only review tasks can be confirmed")
            if record.status in self._HISTORY_STATUSES:
                raise ValueError("terminal tasks cannot change status")
            record.status = status
            record.updated_at = self._now()
            if status == "terminated":
                record.terminated_at = record.updated_at
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def update_task(self, *, user_id: str, task_id: str, prompt: str, priority: str, attachments: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Replace the editable prompt, priority, and attachment reference list of a pending task."""
        if not prompt.strip() or priority not in self._PRIORITY_ORDER:
            raise ValueError("invalid task data")
        with Session(self.engine) as db:
            record = db.get(AgentQueueTaskRecord, task_id)
            if record is None or record.user_id != user_id:
                return None
            if record.status != "pending":
                raise ValueError("only pending tasks can be edited")
            record.prompt = prompt.strip()
            record.priority = priority
            record.attachments_json = json.dumps(attachments, ensure_ascii=False)
            record.updated_at = self._now()
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def delete_task(self, *, user_id: str, task_id: str) -> bool:
        """Delete only an unclaimed task; running work must be explicitly terminated."""
        with Session(self.engine) as db:
            record = db.get(AgentQueueTaskRecord, task_id)
            if record is None or record.user_id != user_id:
                return False
            if record.status != "pending":
                raise ValueError("only pending tasks can be deleted")
            db.delete(record)
            db.commit()
            return True

    def restart_task(self, *, user_id: str, task_id: str, prompt: str, attachments: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Return a reviewed task to pending while retaining its complete prior Agent session."""
        if not prompt.strip():
            raise ValueError("prompt is required")
        with Session(self.engine) as db:
            record = db.get(AgentQueueTaskRecord, task_id)
            if record is None or record.user_id != user_id:
                return None
            if record.status != "review":
                raise ValueError("only review tasks can continue")
            record.prompt = prompt.strip()
            record.attachments_json = json.dumps(attachments, ensure_ascii=False)
            record.status = "pending"
            record.started_at = None
            record.finished_at = None
            record.updated_at = self._now()
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)
