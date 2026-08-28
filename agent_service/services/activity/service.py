"""
Daily activity persistence and heatmap aggregation service.

Usage:
Call `record_event` after a successful meaningful operation. Dashboard readers
call `get_heatmap`, which first idempotently backfills activity visible in the
existing business tables and then returns privacy-safe daily aggregates.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.activity import ActivityEventRecord
from agent_service.models.agent_queue import AgentQueueTaskRecord
from agent_service.models.favorite import FavoriteRecord
from agent_service.models.library import LibraryItem
from agent_service.models.message import MessageRecord
from agent_service.models.smart_form import SmartFormRecord
from agent_service.models.todo import TodoRecord
from agent_service.models.vault import VaultItem


ACTIVITY_MODULES = ("library", "documents", "knowledge", "agent", "tasks", "other")

class ActivityService:
    """Persist meaningful activity and aggregate fixed-threshold heatmap data."""

    def __init__(
        self,
        *,
        engine: Engine,
        config: AgentConfig | None = None,
        create_tables: bool = True,
    ) -> None:
        """Reuse the application database engine and create the event table when requested."""

        self.engine = engine
        self.config = config or AgentConfig()

    def record_event(
        self,
        *,
        user_id: str,
        module: str,
        action: str,
        score: int,
        object_id: str = "",
        title: str = "",
        source: str = "runtime",
        occurred_at: datetime | None = None,
        dedupe_minutes: int | None = None,
        event_key: str = "",
    ) -> bool:
        """Append one event, optionally merging repeated saves of the same object."""

        normalized_user_id = user_id.strip()
        if not normalized_user_id or module not in ACTIVITY_MODULES or score <= 0:
            return False
        timestamp = self._as_utc(occurred_at or datetime.now(timezone.utc))
        event_id = self._stable_event_id(event_key) if event_key else f"act_{uuid4().hex}"
        with Session(self.engine) as db:
            if db.get(ActivityEventRecord, event_id) is not None:
                return False
            dedupe_minutes = (
                self.config.limits.activity_event_dedupe_minutes
                if dedupe_minutes is None
                else dedupe_minutes
            )
            if dedupe_minutes > 0 and object_id:
                cutoff = timestamp - timedelta(minutes=dedupe_minutes)
                ceiling = timestamp + timedelta(minutes=dedupe_minutes)
                duplicate = db.exec(
                    select(ActivityEventRecord)
                    .where(ActivityEventRecord.user_id == normalized_user_id)
                    .where(ActivityEventRecord.module == module)
                    .where(ActivityEventRecord.action == action)
                    .where(ActivityEventRecord.object_id == object_id[:self.config.limits.summary_max_length])
                    .where(ActivityEventRecord.created_at >= cutoff)
                    .where(ActivityEventRecord.created_at <= ceiling)
                    .limit(1)
                ).first()
                if duplicate is not None:
                    return False
            db.add(
                ActivityEventRecord(
                    event_id=event_id,
                    user_id=normalized_user_id,
                    module=module,
                    action=action[:self.config.limits.standard_id_max_length],
                    score=min(score, self.config.limits.activity_event_score_max),
                    object_id=object_id[:self.config.limits.summary_max_length],
                    title=title[:self.config.limits.title_max_length],
                    source=source[:self.config.limits.short_type_max_length],
                    created_at=timestamp,
                )
            )
            db.commit()
        return True

    def sync_existing_records(self, *, user_id: str) -> int:
        """Idempotently turn existing business timestamps into honest historical events."""

        inserted = 0
        with Session(self.engine) as db:
            messages = list(
                db.exec(
                    select(MessageRecord)
                    .where(MessageRecord.user_id == user_id)
                    .where(MessageRecord.role == "assistant")
                ).all()
            )
            library_items = list(db.exec(select(LibraryItem).where(LibraryItem.user_id == user_id)).all())
            favorites = list(db.exec(select(FavoriteRecord).where(FavoriteRecord.user_id == user_id)).all())
            forms = list(db.exec(select(SmartFormRecord).where(SmartFormRecord.user_id == user_id)).all())
            todos = list(db.exec(select(TodoRecord).where(TodoRecord.user_id == user_id)).all())
            queue_tasks = list(db.exec(select(AgentQueueTaskRecord).where(AgentQueueTaskRecord.user_id == user_id)).all())
            vault_items = list(db.exec(select(VaultItem).where(VaultItem.user_id == user_id)).all())

        for message in messages:
            inserted += self.record_event(
                user_id=user_id,
                module="agent",
                action="agent_task_completed",
                score=3,
                object_id=message.message_id,
                title="完成 Agent 任务",
                occurred_at=message.created_at,
                source="backfill",
                event_key=f"message:{message.message_id}",
            )
        for item in library_items:
            inserted += self.record_event(
                user_id=user_id,
                module="library",
                action="library_item_created",
                score=2,
                object_id=item.item_id,
                title="新建图书馆项目",
                occurred_at=item.created_at,
                source="backfill",
                event_key=f"library-create:{item.item_id}",
            )
            if self._is_distinct_update(item.created_at, item.updated_at):
                inserted += self.record_event(
                    user_id=user_id,
                    module="library",
                    action="metadata_updated",
                    score=1,
                    object_id=item.item_id,
                    title="完善图书馆项目",
                    occurred_at=item.updated_at,
                    source="backfill",
                    dedupe_minutes=self.config.limits.activity_backfill_dedupe_minutes,
                    event_key=f"library-update:{item.item_id}:{item.updated_at.isoformat()}",
                )
        for favorite in favorites:
            inserted += self.record_event(
                user_id=user_id,
                module="library",
                action="favorite_added",
                score=1,
                object_id=favorite.favorite_id,
                title="收藏项目",
                occurred_at=favorite.created_at,
                source="backfill",
                event_key=f"favorite:{favorite.favorite_id}",
            )
        for form in forms:
            inserted += self.record_event(
                user_id=user_id,
                module="other",
                action="smart_form_saved",
                score=2,
                object_id=form.form_id,
                title="新建智能表格",
                occurred_at=form.created_at,
                source="backfill",
                dedupe_minutes=self.config.limits.activity_backfill_dedupe_minutes,
                event_key=f"form-create:{form.form_id}",
            )
            if self._is_distinct_update(form.created_at, form.updated_at):
                inserted += self.record_event(
                    user_id=user_id,
                    module="other",
                    action="smart_form_saved",
                    score=2,
                    object_id=form.form_id,
                    title="更新智能表格",
                    occurred_at=form.updated_at,
                    source="backfill",
                    dedupe_minutes=self.config.limits.activity_backfill_dedupe_minutes,
                    event_key=f"form-update:{form.form_id}:{form.updated_at.isoformat()}",
                )
        for todo in todos:
            inserted += self.record_event(
                user_id=user_id,
                module="tasks",
                action="task_created",
                score=1,
                object_id=todo.todo_id,
                title="新建任务",
                occurred_at=todo.created_at,
                source="backfill",
                event_key=f"todo-create:{todo.todo_id}",
            )
            if todo.last_completed_at is not None:
                inserted += self.record_event(
                    user_id=user_id,
                    module="tasks",
                    action="task_completed",
                    score=3,
                    object_id=todo.todo_id,
                    title="完成任务",
                    occurred_at=todo.last_completed_at,
                    source="backfill",
                    event_key=f"todo-complete:{todo.todo_id}:{todo.last_completed_at.isoformat()}",
                )
        for task in queue_tasks:
            if task.finished_at is not None:
                inserted += self.record_event(
                    user_id=user_id,
                    module="tasks",
                    action="queue_task_completed",
                    score=2,
                    object_id=task.task_id,
                    title="完成队列任务",
                    occurred_at=task.finished_at,
                    source="backfill",
                    dedupe_minutes=self.config.limits.activity_backfill_dedupe_minutes,
                    event_key=f"queue-complete:{task.task_id}:{task.finished_at.isoformat()}",
                )
        for item in vault_items:
            inserted += self.record_event(
                user_id=user_id,
                module="other",
                action="vault_item_changed",
                score=1,
                object_id=item.item_id,
                title="更新密码库条目",
                occurred_at=item.created_at,
                source="backfill",
                event_key=f"vault-create:{item.item_id}",
            )
            if self._is_distinct_update(item.created_at, item.updated_at):
                inserted += self.record_event(
                    user_id=user_id,
                    module="other",
                    action="vault_item_changed",
                    score=1,
                    object_id=item.item_id,
                    title="更新密码库条目",
                    occurred_at=item.updated_at,
                    source="backfill",
                    dedupe_minutes=self.config.limits.activity_backfill_dedupe_minutes,
                    event_key=f"vault-update:{item.item_id}:{item.updated_at.isoformat()}",
                )
        return inserted

    def record_skills(self, *, user_id: str, skills: list[dict[str, Any]]) -> int:
        """Record Skill bodies routed into one Agent run without storing their content."""

        inserted = 0
        for skill in skills:
            skill_id = str(skill.get("skill_id") or skill.get("name") or "").strip()
            if not skill_id:
                continue
            inserted += self.record_event(
                user_id=user_id,
                module="agent",
                action="skill_used",
                score=1,
                object_id=skill_id,
                title=f"使用 Skill：{str(skill.get('name') or skill_id)[:self.config.limits.activity_title_preview_chars]}",
            )
        return inserted

    def get_heatmap(
        self,
        *,
        user_id: str,
        days: int | None = None,
        timezone_name: str = "Asia/Shanghai",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return capped daily scores, module breakdowns, activities, and summaries."""

        zone = self._timezone(timezone_name)
        end_date = self._as_utc(now or datetime.now(timezone.utc)).astimezone(zone).date()
        normalized_days = max(
            self.config.limits.activity_heatmap_min_days,
            min(
                days or self.config.limits.activity_heatmap_max_days,
                self.config.limits.activity_heatmap_max_days,
            ),
        )
        start_date = end_date - timedelta(days=normalized_days - 1)
        start_utc = datetime.combine(start_date, time.min, zone).astimezone(timezone.utc)
        end_utc = datetime.combine(end_date + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
        with Session(self.engine) as db:
            events = list(
                db.exec(
                    select(ActivityEventRecord)
                    .where(ActivityEventRecord.user_id == user_id)
                    .where(ActivityEventRecord.created_at >= start_utc)
                    .where(ActivityEventRecord.created_at < end_utc)
                    .order_by(ActivityEventRecord.created_at.desc())
                ).all()
            )

        events_by_day: dict[str, list[ActivityEventRecord]] = defaultdict(list)
        for event in events:
            local_date = self._as_utc(event.created_at).astimezone(zone).date().isoformat()
            events_by_day[local_date].append(event)
        day_rows = [self._aggregate_day(day, rows) for day, rows in sorted(events_by_day.items())]
        return {
            "timezone": zone.key,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": day_rows,
            "summaries": {
                "all": self._summary(day_rows, start_date=start_date, end_date=end_date),
                **{
                    module: self._summary(day_rows, module=module, start_date=start_date, end_date=end_date)
                    for module in ACTIVITY_MODULES
                },
            },
        }

    @staticmethod
    def level_for_score(score: int) -> int:
        """Map a fixed daily score to the seven agreed heat levels."""

        if score <= 0:
            return 0
        if score <= 3:
            return 1
        if score <= 7:
            return 2
        if score <= 12:
            return 3
        if score <= 18:
            return 4
        if score <= 27:
            return 5
        return 6

    def _aggregate_day(self, day: str, events: list[ActivityEventRecord]) -> dict[str, Any]:
        """Apply per-action caps and build one privacy-safe daily row."""

        action_totals: dict[str, int] = defaultdict(int)
        module_scores: dict[str, int] = defaultdict(int)
        module_counts: dict[str, int] = defaultdict(int)
        for event in events:
            cap = self.config.limits.activity_daily_caps.get(
                event.action,
                self.config.limits.activity_default_daily_cap,
            )
            accepted = min(event.score, max(cap - action_totals[event.action], 0))
            action_totals[event.action] += accepted
            module_scores[event.module] += accepted
            module_counts[event.module] += 1
        score = sum(module_scores.values())
        return {
            "date": day,
            "score": score,
            "level": self.level_for_score(score),
            "event_count": len(events),
            "modules": {
                module: {"score": module_scores[module], "event_count": module_counts[module]}
                for module in ACTIVITY_MODULES
                if module_counts[module] > 0
            },
            "activities": [
                {
                    "module": event.module,
                    "action": event.action,
                    "score": event.score,
                    "title": event.title,
                    "created_at": self._as_utc(event.created_at).isoformat(),
                }
                for event in events[:self.config.limits.activity_daily_preview_limit]
            ],
        }

    def _summary(
        self,
        days: list[dict[str, Any]],
        *,
        start_date: date,
        end_date: date,
        module: str = "",
    ) -> dict[str, int]:
        """Compute total, active days, current streak, and peak for one filter."""

        scores = {
            date.fromisoformat(day["date"]): (
                int(day["modules"].get(module, {}).get("score", 0)) if module else int(day["score"])
            )
            for day in days
        }
        active_scores = [score for score in scores.values() if score > 0]
        streak = 0
        cursor = end_date
        while cursor >= start_date and scores.get(cursor, 0) > 0:
            streak += 1
            cursor -= timedelta(days=1)
        return {
            "total_score": sum(active_scores),
            "active_days": len(active_scores),
            "current_streak": streak,
            "peak_score": max(active_scores, default=0),
        }

    def _stable_event_id(self, event_key: str) -> str:
        """Create a compact deterministic id for idempotent source backfill."""

        return f"act_{sha256(event_key.encode('utf-8')).hexdigest()[:self.config.limits.stable_event_hash_chars]}"

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Normalize SQLite-naive and timezone-aware timestamps to UTC."""

        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _is_distinct_update(created_at: datetime, updated_at: datetime) -> bool:
        """Ignore model defaults that stamp create and update at effectively the same instant."""

        created = ActivityService._as_utc(created_at)
        updated = ActivityService._as_utc(updated_at)
        return updated - created > timedelta(seconds=1)

    @staticmethod
    def _timezone(name: str) -> ZoneInfo:
        """Resolve the requested timezone with the project display timezone as fallback."""

        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("Asia/Shanghai")
