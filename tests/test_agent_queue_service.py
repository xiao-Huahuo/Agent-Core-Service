"""Regression tests for durable Agent task queue priority scheduling."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from agent_service.models.agent_queue import AgentQueueTaskRecord
from agent_service.services.agent_queue_service import AgentQueueService


class StubSessionService:
    """Create predictable independent session IDs without a full Agent runtime."""

    def __init__(self) -> None:
        self.count = 0

    def create_session(self, _payload: object):
        """Return the minimum shape consumed by the queue service."""
        self.count += 1
        return type("CreatedSession", (), {"session_id": f"sess_{self.count}"})()

    def get_session_state(self, _session_id: str) -> None:
        """Queue progress is absent until the Agent creates its task list."""
        return None


def make_service() -> AgentQueueService:
    """Build an isolated SQLite-backed queue service."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return AgentQueueService(engine=engine, session_service=StubSessionService())


def test_claim_next_prefers_priority_and_respects_per_user_limit() -> None:
    """Highest priority pending task starts first and concurrency caps later claims."""
    service = make_service()
    service.update_settings("u1", 1)
    low = service.create_task(user_id="u1", prompt="low", priority="low")
    high = service.create_task(user_id="u1", prompt="high", priority="high")

    claimed = service.claim_next("u1")

    assert claimed is not None
    assert claimed["task_id"] == high["task_id"]
    assert claimed["status"] == "running"
    # Sessions are allocated while creating tasks so attachments can be bound
    # before the scheduler starts the task; the second created task is high.
    assert claimed["session_id"] == "sess_2"
    assert service.claim_next("u1") is None
    assert low["task_id"] != claimed["task_id"]


def test_finished_task_can_be_confirmed_or_terminated() -> None:
    """Only queue-owned state changes are persisted for task history."""
    service = make_service()
    task = service.create_task(user_id="u1", prompt="work")
    claimed = service.claim_next("u1")
    assert claimed is not None
    service.finish(task["task_id"], "review")

    confirmed = service.transition(user_id="u1", task_id=task["task_id"], status="confirmed")

    assert confirmed is not None
    assert confirmed["status"] == "confirmed"
    assert service.list_tasks(user_id="u1") == []
    assert [item["task_id"] for item in service.list_tasks(user_id="u1", history=True)] == [task["task_id"]]


def test_pending_edit_replaces_attachment_references() -> None:
    """Pending cards keep their stored attachment queue in sync with edits."""
    service = make_service()
    task = service.create_task(user_id="u1", prompt="old", attachments=[{"attachment_id": "old"}])

    updated = service.update_task(
        user_id="u1",
        task_id=task["task_id"],
        prompt="new",
        priority="high",
        attachments=[{"attachment_id": "new"}],
    )

    assert updated is not None
    assert updated["prompt"] == "new"
    assert updated["attachments"] == [{"attachment_id": "new"}]
