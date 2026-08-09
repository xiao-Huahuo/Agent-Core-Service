"""
定时自动化任务服务。

功能说明:
- 使用 SQLite 持久化自动化定义和每次运行记录。
- 通过数据库租约抢占到期任务,避免多进程重复执行。
- 负责计算下一次执行时间,但不直接决定 Agent 的业务内容。
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, update
from sqlmodel import Session, SQLModel, select

from agent_service.models.automation import AutomationRunRecord, AutomationTaskRecord
from agent_service.services.todo_service import TodoService


class AutomationService:
    """管理自动化任务定义、抢占和运行结果。"""

    _FREQUENCIES = {"none", "daily", "weekly", "monthly"}
    _ACCESS_MODES = {"readonly", "sandbox", "full_access"}

    def __init__(self, *, engine: Any, todo_service: TodoService) -> None:
        """初始化服务并确保自动化相关表已创建。"""

        self.engine = engine
        self.todo_service = todo_service
        SQLModel.metadata.create_all(self.engine)

    @staticmethod
    def _utc_now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    @classmethod
    def _parse_datetime(cls, value: Any) -> datetime:
        """解析带时区的 ISO 时间并转换为 UTC。"""

        if not value:
            raise ValueError("next_run_at is required")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("next_run_at must be a valid ISO datetime") from exc
        if parsed.tzinfo is None:
            raise ValueError("next_run_at must include a timezone offset")
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _normalize_recurrence(cls, value: Any) -> tuple[str, int]:
        """校验自动化任务的循环频率和间隔。"""

        payload = value if isinstance(value, dict) else {}
        frequency = str(payload.get("frequency") or "none").strip().lower()
        if frequency not in cls._FREQUENCIES:
            raise ValueError("recurrence.frequency must be none, daily, weekly, or monthly")
        try:
            interval = int(payload.get("interval", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("recurrence.interval must be an integer") from exc
        if not 1 <= interval <= 365:
            raise ValueError("recurrence.interval must be between 1 and 365")
        return frequency, interval

    @classmethod
    def _normalize_timezone(cls, value: str | None) -> str:
        """校验 IANA 时区名称,避免使用机器本地时区产生漂移。"""

        name = str(value or "UTC").strip()
        try:
            ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {name}") from exc
        return name

    @classmethod
    def _advance_datetime(cls, current: datetime, frequency: str, interval: int, timezone_name: str) -> datetime:
        """按任务时区推进下一次执行时间并转换回 UTC。"""

        if frequency == "none":
            return current
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        local = current.astimezone(ZoneInfo(timezone_name))
        if frequency == "daily":
            local += timedelta(days=interval)
        elif frequency == "weekly":
            local += timedelta(weeks=interval)
        else:
            month_index = local.month - 1 + interval
            year = local.year + month_index // 12
            month = month_index % 12 + 1
            day = min(local.day, calendar.monthrange(year, month)[1])
            local = local.replace(year=year, month=month, day=day)
        return local.astimezone(timezone.utc)

    @classmethod
    def _serialize_task(cls, record: AutomationTaskRecord) -> dict[str, Any]:
        """将自动化记录转换为前端使用的 camelCase 数据。"""

        def iso(value: datetime | None) -> str | None:
            if value is None:
                return None
            aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return aware.astimezone(timezone.utc).isoformat()

        return {
            "id": record.automation_id,
            "todoId": record.todo_id,
            "userId": record.user_id,
            "prompt": record.prompt,
            "timezone": record.timezone_name,
            "recurrence": {
                "frequency": record.recurrence_frequency,
                "interval": record.recurrence_interval,
            },
            "nextRunAt": iso(record.next_run_at),
            "accessMode": record.access_mode,
            "enabled": record.enabled,
            "lastRunAt": iso(record.last_run_at),
            "lastStatus": record.last_status,
            "lastError": record.last_error,
            "createdAt": iso(record.created_at),
            "updatedAt": iso(record.updated_at),
        }

    @classmethod
    def _serialize_run(cls, record: AutomationRunRecord) -> dict[str, Any]:
        """将运行记录转换为前端使用的 camelCase 数据。"""

        def iso(value: datetime | None) -> str | None:
            if value is None:
                return None
            aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return aware.astimezone(timezone.utc).isoformat()

        return {
            "id": record.run_id,
            "automationId": record.automation_id,
            "userId": record.user_id,
            "status": record.status,
            "startedAt": iso(record.started_at),
            "finishedAt": iso(record.finished_at),
            "output": record.output,
            "error": record.error,
        }

    def create_task(
        self,
        *,
        user_id: str,
        text: str,
        prompt: str,
        next_run_at: str,
        timezone_name: str = "UTC",
        recurrence: dict[str, Any] | None = None,
        access_mode: str = "sandbox",
    ) -> dict[str, Any]:
        """创建自动化任务,并在 TODO 列表中生成对应的 automation 项。"""

        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt is required")
        if access_mode not in self._ACCESS_MODES:
            raise ValueError("access_mode must be readonly, sandbox, or full_access")
        frequency, interval = self._normalize_recurrence(recurrence)
        zone = self._normalize_timezone(timezone_name)
        next_run = self._parse_datetime(next_run_at)
        todo = self.todo_service.add_todo(user_id=user_id, text=text, category="automation")
        now = self._utc_now()
        record = AutomationTaskRecord(
            automation_id=f"automation_{uuid4().hex[:12]}",
            todo_id=todo["id"],
            user_id=user_id,
            prompt=prompt,
            timezone_name=zone,
            recurrence_frequency=frequency,
            recurrence_interval=interval,
            next_run_at=next_run,
            access_mode=access_mode,
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize_task(record)

    def list_tasks(self, *, user_id: str) -> list[dict[str, Any]]:
        """列出用户的自动化任务,按下一次执行时间排序。"""

        with Session(self.engine) as db:
            records = db.exec(
                select(AutomationTaskRecord)
                .where(AutomationTaskRecord.user_id == user_id)
                .order_by(AutomationTaskRecord.next_run_at)
            ).all()
            return [self._serialize_task(record) for record in records]

    def list_runs(self, *, user_id: str, automation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """列出一个自动化任务最近的运行记录。"""

        safe_limit = max(1, min(limit, 100))
        with Session(self.engine) as db:
            task = db.get(AutomationTaskRecord, automation_id)
            if task is None or task.user_id != user_id:
                return []
            records = db.exec(
                select(AutomationRunRecord)
                .where(
                    AutomationRunRecord.automation_id == automation_id,
                    AutomationRunRecord.user_id == user_id,
                )
                .order_by(AutomationRunRecord.started_at.desc())
                .limit(safe_limit)
            ).all()
            return [self._serialize_run(record) for record in records]

    def set_enabled(self, *, user_id: str, automation_id: str, enabled: bool) -> dict[str, Any] | None:
        """启用或停用自动化任务。"""

        with Session(self.engine) as db:
            record = db.get(AutomationTaskRecord, automation_id)
            if record is None or record.user_id != user_id:
                return None
            record.enabled = enabled
            record.updated_at = self._utc_now()
            record.lease_id = None
            record.lease_until = None
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize_task(record)

    def delete_task(self, *, user_id: str, automation_id: str) -> bool:
        """删除自动化定义、运行记录和关联的 TODO。"""

        with Session(self.engine) as db:
            task = db.get(AutomationTaskRecord, automation_id)
            if task is None or task.user_id != user_id:
                return False
            runs = db.exec(
                select(AutomationRunRecord).where(AutomationRunRecord.automation_id == automation_id)
            ).all()
            for run in runs:
                db.delete(run)
            db.delete(task)
            db.commit()
        self.todo_service.delete_todo(user_id=user_id, todo_id=task.todo_id)
        return True

    def claim_due_tasks(self, *, now: datetime | None = None, lease_seconds: int = 300) -> list[dict[str, Any]]:
        """抢占到期任务并创建 running 运行记录。"""

        current = (now or self._utc_now()).astimezone(timezone.utc)
        lease_until = current + timedelta(seconds=lease_seconds)
        claimed: list[dict[str, Any]] = []
        with Session(self.engine) as db:
            candidates = db.exec(
                select(AutomationTaskRecord).where(
                    AutomationTaskRecord.enabled.is_(True),
                    AutomationTaskRecord.next_run_at <= current,
                    or_(AutomationTaskRecord.lease_until.is_(None), AutomationTaskRecord.lease_until < current),
                ).limit(20)
            ).all()
            for candidate in candidates:
                lease_id = f"lease_{uuid4().hex[:12]}"
                result = db.exec(
                    update(AutomationTaskRecord)
                    # SQLite returns naive datetimes; let the database evaluate
                    # this predicate instead of SQLAlchemy comparing them in Python.
                    .execution_options(synchronize_session=False)
                    .where(
                        AutomationTaskRecord.automation_id == candidate.automation_id,
                        AutomationTaskRecord.enabled.is_(True),
                        AutomationTaskRecord.next_run_at == candidate.next_run_at,
                        or_(AutomationTaskRecord.lease_until.is_(None), AutomationTaskRecord.lease_until < current),
                    )
                    .values(lease_id=lease_id, lease_until=lease_until)
                )
                if result.rowcount != 1:
                    continue
                run = AutomationRunRecord(
                    run_id=f"run_{uuid4().hex[:12]}",
                    automation_id=candidate.automation_id,
                    user_id=candidate.user_id,
                    started_at=current,
                )
                db.add(run)
                claimed.append({"task": self._serialize_task(candidate), "run": self._serialize_run(run)})
            db.commit()
        return claimed

    def finish_run(
        self,
        *,
        automation_id: str,
        run_id: str,
        status: str,
        output: str | None = None,
        error: str | None = None,
    ) -> None:
        """完成运行记录并安排下一次执行。"""

        if status not in {"success", "failed", "skipped"}:
            raise ValueError("status must be success, failed, or skipped")
        now = self._utc_now()
        with Session(self.engine) as db:
            task = db.get(AutomationTaskRecord, automation_id)
            run = db.get(AutomationRunRecord, run_id)
            if task is None or run is None:
                return
            run.status = status
            run.finished_at = now
            run.output = output
            run.error = error
            task.last_run_at = now
            task.last_status = status
            task.last_error = error
            task.updated_at = now
            task.lease_id = None
            task.lease_until = None
            if task.recurrence_frequency == "none":
                task.enabled = False
            else:
                task.next_run_at = self._advance_datetime(
                    task.next_run_at,
                    task.recurrence_frequency,
                    task.recurrence_interval,
                    task.timezone_name,
                )
            db.add(run)
            db.add(task)
            db.commit()
