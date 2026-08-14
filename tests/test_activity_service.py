"""
Daily activity heatmap service tests.

Usage:
Verifies persisted event scoring, edit-session deduplication, category summaries,
and privacy-safe backfill from existing business tables.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from agent_service.models.agent_queue import AgentQueueTaskRecord
from agent_service.models.library import LibraryItem
from agent_service.models.message import MessageRecord
from agent_service.models.session import SessionRecord
from agent_service.models.smart_form import SmartFormRecord
from agent_service.models.todo import TodoRecord
from agent_service.models.vault import VaultItem
from agent_service.services.activity_service import ActivityService


def _service() -> ActivityService:
    """Create an isolated activity service with all project tables registered."""

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return ActivityService(engine=engine, create_tables=False)


def test_heatmap_applies_action_caps_and_builds_filter_summaries() -> None:
    """Daily totals should cap repeated actions and expose module-specific statistics."""

    service = _service()
    occurred_at = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
    for index in range(8):
        service.record_event(
            user_id="u1",
            module="library",
            action="metadata_updated",
            score=1,
            object_id=f"book-{index}",
            title="完善图书馆项目",
            occurred_at=occurred_at + timedelta(minutes=index),
        )
    service.record_event(
        user_id="u1",
        module="agent",
        action="agent_task_completed",
        score=3,
        object_id="message-1",
        title="完成 Agent 任务",
        occurred_at=occurred_at,
    )

    result = service.get_heatmap(user_id="u1", days=7, timezone_name="UTC", now=occurred_at)

    day = result["days"][0]
    assert day["date"] == "2026-08-14"
    assert day["score"] == 9  # metadata_updated caps at 6, Agent contributes 3.
    assert day["modules"]["library"] == {"score": 6, "event_count": 8}
    assert result["summaries"]["all"]["total_score"] == 9
    assert result["summaries"]["library"]["total_score"] == 6
    assert result["summaries"]["agent"]["peak_score"] == 3


def test_edit_events_are_deduplicated_within_one_continuous_session() -> None:
    """Repeated saves of the same object within 30 minutes should count once."""

    service = _service()
    started_at = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)

    first = service.record_event(
        user_id="u1",
        module="documents",
        action="content_edited",
        score=2,
        object_id="notes/a.md",
        title="编辑文档",
        occurred_at=started_at,
        dedupe_minutes=30,
    )
    duplicate = service.record_event(
        user_id="u1",
        module="documents",
        action="content_edited",
        score=2,
        object_id="notes/a.md",
        title="编辑文档",
        occurred_at=started_at + timedelta(minutes=10),
        dedupe_minutes=30,
    )
    later = service.record_event(
        user_id="u1",
        module="documents",
        action="content_edited",
        score=2,
        object_id="notes/a.md",
        title="编辑文档",
        occurred_at=started_at + timedelta(minutes=45),
        dedupe_minutes=30,
    )

    assert first is True
    assert duplicate is False
    assert later is True


def test_routed_skills_are_recorded_without_persisting_skill_bodies() -> None:
    """Skill contribution events should retain identity only, never prompt bodies."""

    service = _service()
    assert service.record_skills(
        user_id="u1",
        skills=[{"skill_id": "apple-design", "name": "Apple Design", "body": "private instructions"}],
    ) == 1

    result = service.get_heatmap(user_id="u1", days=7, timezone_name="UTC")
    activity = result["days"][0]["activities"][0]
    assert activity["action"] == "skill_used"
    assert "private instructions" not in activity["title"]


def test_existing_business_data_backfills_real_privacy_safe_events() -> None:
    """Existing records should seed the heatmap without exposing vault metadata."""

    service = _service()
    occurred_at = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with Session(service.engine) as db:
        db.add(SessionRecord(session_id="session-1", user_id="u1", session_name="研究任务"))
        db.add(
            MessageRecord(
                message_id="message-1",
                session_id="session-1",
                user_id="u1",
                role="assistant",
                content="done",
                created_at=occurred_at,
            )
        )
        db.add(
            LibraryItem(
                item_id="book-1",
                user_id="u1",
                library_id="library-1",
                title="Private book title",
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        db.add(
            SmartFormRecord(
                form_id="form-1",
                user_id="u1",
                title="Reading table",
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        db.add(
            TodoRecord(
                todo_id="todo-1",
                user_id="u1",
                text="Finish chapter",
                done=True,
                last_completed_at=occurred_at,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        db.add(
            AgentQueueTaskRecord(
                task_id="queue-1",
                user_id="u1",
                prompt="Private queue prompt",
                status="completed",
                finished_at=occurred_at,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        db.add(
            VaultItem(
                item_id="vault-1",
                user_id="u1",
                item_type="login",
                encrypted_payload="secret payload",
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        db.commit()

    service.record_event(
        user_id="u1",
        module="other",
        action="smart_form_saved",
        score=2,
        object_id="form-1",
        title="保存智能表格",
        occurred_at=occurred_at + timedelta(milliseconds=500),
        source="runtime",
        dedupe_minutes=30,
    )
    service.sync_existing_records(user_id="u1")
    result = service.get_heatmap(user_id="u1", days=7, timezone_name="UTC", now=occurred_at)

    activities = result["days"][0]["activities"]
    assert result["summaries"]["all"]["total_score"] == 14
    assert {item["module"] for item in activities} >= {"agent", "library", "tasks", "other"}
    assert all("Private" not in item["title"] for item in activities)
    assert all("secret" not in item["title"] for item in activities)
