"""
TODO 数据库服务。

功能说明:
- 使用现有 SQLModel/SQLite 数据库持久化 TODO。
- 支持截止时间、提醒时间和 daily/weekly/monthly 循环规则。
- 首次访问用户数据时兼容导入旧的 runtime/todos/{user}.json 文件。
"""

from __future__ import annotations

import json
import logging
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlmodel import Session, SQLModel, select

from agent_service.models.todo import TodoImportRecord, TodoRecord

logger = logging.getLogger(__name__)


class TodoService:
    """用户 TODO 数据库服务。"""

    def __init__(self, *, engine: Any, legacy_data_dir: str | None = None) -> None:
        """初始化数据库服务,并保留旧 JSON 目录作为一次性迁移来源。"""

        self.engine = engine
        self._legacy_storage_dir = Path(legacy_data_dir or "") / "todos" if legacy_data_dir else None
        SQLModel.metadata.create_all(self.engine)

    @staticmethod
    def _utc_now() -> datetime:
        """返回带 UTC 时区的当前时间。"""

        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """解析 ISO 时间,无效或空值返回 None。"""

        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _normalize_recurrence(value: Any) -> tuple[str, int]:
        """将循环规则规范化为频率和间隔。"""

        payload = value if isinstance(value, dict) else {}
        frequency = str(payload.get("frequency") or "none").strip().lower()
        if frequency not in {"none", "daily", "weekly", "monthly"}:
            raise ValueError("recurrence.frequency must be none, daily, weekly, or monthly")
        try:
            interval = int(payload.get("interval", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("recurrence.interval must be an integer") from exc
        if not 1 <= interval <= 365:
            raise ValueError("recurrence.interval must be between 1 and 365")
        return frequency, interval

    @classmethod
    def _advance_datetime(cls, current: datetime, frequency: str, interval: int) -> datetime:
        """根据循环规则计算下一次时间。"""

        if frequency == "daily":
            return current + timedelta(days=interval)
        if frequency == "weekly":
            return current + timedelta(weeks=interval)
        month_index = current.month - 1 + interval
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        day = min(current.day, monthrange(year, month)[1])
        return current.replace(year=year, month=month, day=day)

    @classmethod
    def _serialize(cls, record: TodoRecord) -> dict[str, Any]:
        """将数据库记录转换成现有前端使用的 camelCase 响应。"""

        def iso(value: datetime | None) -> str | None:
            """将 SQLite 可能返回的 naive 时间统一标记为 UTC。"""

            if value is None:
                return None
            aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return aware.isoformat()

        return {
            "id": record.todo_id,
            "text": record.text,
            "category": record.category,
            "done": record.done,
            "createdAt": iso(record.created_at),
            "updatedAt": iso(record.updated_at),
            "dueDate": iso(record.due_at),
            "reminderAt": iso(record.reminder_at),
            "recurrence": {
                "frequency": record.recurrence_frequency,
                "interval": record.recurrence_interval,
            },
            "lastCompletedAt": iso(record.last_completed_at),
        }

    def _legacy_path(self, user_id: str) -> Path | None:
        """返回旧 JSON 文件路径。"""

        if self._legacy_storage_dir is None:
            return None
        safe = user_id.replace("/", "_").replace("\\", "_")
        return self._legacy_storage_dir / f"{safe}.json"

    def _import_legacy_if_needed(self, user_id: str) -> None:
        """一次性导入旧 JSON TODO,导入后不再读取或写入 JSON。"""

        if self._legacy_storage_dir is None:
            return
        with Session(self.engine) as db:
            if db.get(TodoImportRecord, user_id) is not None:
                return
            path = self._legacy_path(user_id)
            payload: list[Any] = []
            if path and path.exists():
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    payload = raw if isinstance(raw, list) else []
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning("导入旧 TODO JSON 失败 user=%s: %s", user_id, exc)
            for item in payload:
                if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                    continue
                frequency, interval = self._normalize_recurrence(item.get("recurrence"))
                db.add(TodoRecord(
                    todo_id=str(item.get("id") or f"todo_{uuid4().hex[:12]}"),
                    user_id=user_id,
                    text=str(item["text"]).strip(),
                    category=str(item.get("category") or "task"),
                    done=bool(item.get("done", False)),
                    due_at=self._parse_datetime(item.get("dueDate")),
                    reminder_at=self._parse_datetime(item.get("reminderAt")),
                    recurrence_frequency=frequency,
                    recurrence_interval=interval,
                    last_completed_at=self._parse_datetime(item.get("lastCompletedAt")),
                    created_at=self._parse_datetime(item.get("createdAt")) or self._utc_now(),
                    updated_at=self._utc_now(),
                ))
            db.add(TodoImportRecord(user_id=user_id))
            db.commit()

    def list_todos(self, user_id: str) -> list[dict[str, Any]]:
        """列出用户 TODO,按更新时间倒序。"""

        self._import_legacy_if_needed(user_id)
        with Session(self.engine) as db:
            records = db.exec(
                select(TodoRecord).where(TodoRecord.user_id == user_id).order_by(TodoRecord.updated_at.desc())
            ).all()
            return [self._serialize(record) for record in records]

    def add_todo(self, user_id: str, text: str, due_date: str | None = None, reminder_at: str | None = None, recurrence: dict[str, Any] | None = None, category: str = "task") -> dict[str, Any]:
        """新增 TODO。"""

        self._import_legacy_if_needed(user_id)
        text = text.strip()
        if not text:
            raise ValueError("text is required")
        frequency, interval = self._normalize_recurrence(recurrence)
        now = self._utc_now()
        record = TodoRecord(
            todo_id=f"todo_{uuid4().hex[:12]}", user_id=user_id, text=text,
            category=category.strip() or "task", due_at=self._parse_datetime(due_date),
            reminder_at=self._parse_datetime(reminder_at), recurrence_frequency=frequency,
            recurrence_interval=interval, created_at=now, updated_at=now,
        )
        with Session(self.engine) as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def toggle_todo(self, user_id: str, todo_id: str) -> dict[str, Any] | None:
        """切换 TODO;循环 TODO 完成后推进到下一次而不是永久完成。"""

        self._import_legacy_if_needed(user_id)
        with Session(self.engine) as db:
            record = db.get(TodoRecord, todo_id)
            if record is None or record.user_id != user_id:
                return None
            now = self._utc_now()
            if not record.done and record.recurrence_frequency != "none":
                current = record.due_at or now
                next_due = self._advance_datetime(current, record.recurrence_frequency, record.recurrence_interval)
                if record.reminder_at and record.due_at:
                    record.reminder_at = next_due - (record.due_at - record.reminder_at)
                record.due_at = next_due
                record.last_completed_at = now
            else:
                record.done = not record.done
            record.updated_at = now
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def edit_todo(self, user_id: str, todo_id: str, text: str, due_date: str | None = None, reminder_at: str | None = None, recurrence: dict[str, Any] | None = None, category: str | None = None) -> dict[str, Any] | None:
        """编辑 TODO 内容、提醒、循环规则和分类。"""

        self._import_legacy_if_needed(user_id)
        text = text.strip()
        if not text:
            return None
        with Session(self.engine) as db:
            record = db.get(TodoRecord, todo_id)
            if record is None or record.user_id != user_id:
                return None
            record.text = text
            if due_date is not None:
                record.due_at = self._parse_datetime(due_date)
            if reminder_at is not None:
                record.reminder_at = self._parse_datetime(reminder_at)
            if recurrence is not None:
                record.recurrence_frequency, record.recurrence_interval = self._normalize_recurrence(recurrence)
            if category is not None:
                record.category = category.strip() or "task"
            record.updated_at = self._utc_now()
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize(record)

    def delete_todo(self, user_id: str, todo_id: str) -> bool:
        """删除指定 TODO。"""

        self._import_legacy_if_needed(user_id)
        with Session(self.engine) as db:
            record = db.get(TodoRecord, todo_id)
            if record is None or record.user_id != user_id:
                return False
            db.delete(record)
            db.commit()
            return True
