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

from agent_service.core.agent_config import AgentConfig
from agent_service.models.automation import AutomationRunRecord, AutomationTaskRecord
from agent_service.models.todo import TodoRecord
from agent_service.services.todo_service import TodoService


class AutomationService:
    """管理自动化任务定义、抢占和运行结果。"""

    _FREQUENCIES = {"none", "daily", "weekly", "monthly"}
    _ACCESS_MODES = {"readonly", "sandbox", "full_access"}

    def __init__(
        self,
        *,
        engine: Any,
        todo_service: TodoService,
        config: AgentConfig | None = None,
    ) -> None:
        """初始化服务并确保自动化相关表已创建。"""

        self.engine = engine
        self.todo_service = todo_service
        self.config = config or AgentConfig()
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

    def _normalize_recurrence(self, value: Any) -> tuple[str, int]:
        """校验自动化任务的循环频率和间隔。"""

        payload = value if isinstance(value, dict) else {}
        frequency = str(payload.get("frequency") or "none").strip().lower()
        if frequency not in self._FREQUENCIES:
            raise ValueError("recurrence.frequency must be none, daily, weekly, or monthly")
        try:
            interval = int(payload.get("interval", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("recurrence.interval must be an integer") from exc
        if not self.config.limits.nonempty_min_length <= interval <= self.config.limits.todo_recurrence_max_interval:
            raise ValueError(
                "recurrence.interval must be between "
                f"{self.config.limits.nonempty_min_length} and "
                f"{self.config.limits.todo_recurrence_max_interval}"
            )
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
    def _advance_datetime_after(
        cls,
        current: datetime,
        frequency: str,
        interval: int,
        timezone_name: str,
        after: datetime,
    ) -> datetime:
        """跳过停机期间错过的周期，直接返回严格晚于指定时间的下一次执行。"""

        next_run = cls._advance_datetime(current, frequency, interval, timezone_name)
        while next_run <= after:
            next_run = cls._advance_datetime(next_run, frequency, interval, timezone_name)
        return next_run

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

    @staticmethod
    def _delete_task_record(db: Session, task: AutomationTaskRecord) -> None:
        """在当前事务中删除自动化定义及其全部运行记录。"""

        runs = db.exec(
            select(AutomationRunRecord).where(
                AutomationRunRecord.automation_id == task.automation_id,
                AutomationRunRecord.user_id == task.user_id,
            )
        ).all()
        for run in runs:
            db.delete(run)
        db.delete(task)

    def _purge_orphaned_tasks(self, db: Session, *, user_id: str | None = None) -> int:
        """清理关联 TODO 已消失或归属异常的旧自动化，阻止幽灵任务被扫描。"""

        statement = select(AutomationTaskRecord)
        if user_id is not None:
            statement = statement.where(AutomationTaskRecord.user_id == user_id)
        removed = 0
        for task in db.exec(statement).all():
            todo = db.get(TodoRecord, task.todo_id)
            if todo is not None and todo.user_id == task.user_id and todo.category == "automation":
                continue
            self._delete_task_record(db, task)
            removed += 1
        if removed:
            db.commit()
        return removed

    @staticmethod
    def _reconcile_stale_runs(db: Session, *, current: datetime) -> int:
        """收敛崩溃、停用或租约过期后遗留的 running 记录。"""

        reconciled = 0
        running = db.exec(
            select(AutomationRunRecord).where(AutomationRunRecord.status == "running")
        ).all()
        for run in running:
            task = db.get(AutomationTaskRecord, run.automation_id)
            lease_until = task.lease_until if task is not None else None
            if lease_until is not None and lease_until.tzinfo is None:
                lease_until = lease_until.replace(tzinfo=timezone.utc)
            if task is not None and task.enabled and lease_until is not None and lease_until > current:
                continue
            run.status = "skipped" if task is not None and not task.enabled else "failed"
            run.finished_at = current
            run.error = "任务已停用，运行记录已收敛" if run.status == "skipped" else "执行租约已过期，运行记录已安全回收"
            db.add(run)
            reconciled += 1
        return reconciled

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

        text = text.strip()
        if not text:
            raise ValueError("text is required")
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt is required")
        if access_mode not in self._ACCESS_MODES:
            raise ValueError("access_mode must be readonly, sandbox, or full_access")
        frequency, interval = self._normalize_recurrence(recurrence)
        zone = self._normalize_timezone(timezone_name)
        next_run = self._parse_datetime(next_run_at)
        self.todo_service._import_legacy_if_needed(user_id)
        now = self._utc_now()
        todo_id = f"todo_{uuid4().hex[:self.config.limits.generated_id_suffix_chars]}"
        todo = TodoRecord(
            todo_id=todo_id,
            user_id=user_id,
            text=text,
            category="automation",
            created_at=now,
            updated_at=now,
        )
        record = AutomationTaskRecord(
            automation_id=f"automation_{uuid4().hex[:self.config.limits.generated_id_suffix_chars]}",
            todo_id=todo_id,
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
            db.add(todo)
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._serialize_task(record)

    def list_tasks(self, *, user_id: str) -> list[dict[str, Any]]:
        """列出用户的自动化任务,按下一次执行时间排序。"""

        with Session(self.engine) as db:
            self._purge_orphaned_tasks(db, user_id=user_id)
            records = db.exec(
                select(AutomationTaskRecord)
                .where(AutomationTaskRecord.user_id == user_id)
                .order_by(AutomationTaskRecord.next_run_at)
            ).all()
            return [self._serialize_task(record) for record in records]

    def get_task_by_todo_id(self, *, user_id: str, todo_id: str) -> dict[str, Any] | None:
        """按关联 TODO 查找自动化定义，供所有 TODO 删除入口统一路由。"""

        with Session(self.engine) as db:
            record = db.exec(
                select(AutomationTaskRecord).where(
                    AutomationTaskRecord.user_id == user_id,
                    AutomationTaskRecord.todo_id == todo_id,
                )
            ).first()
            return self._serialize_task(record) if record is not None else None

    def list_runs(self, *, user_id: str, automation_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """列出一个自动化任务最近的运行记录。"""

        safe_limit = max(
            self.config.limits.nonempty_min_length,
            min(
                limit or self.config.limits.automation_run_default_limit,
                self.config.limits.automation_run_max_limit,
            ),
        )
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
            if not enabled:
                now = self._utc_now()
                running = db.exec(
                    select(AutomationRunRecord).where(
                        AutomationRunRecord.automation_id == automation_id,
                        AutomationRunRecord.user_id == user_id,
                        AutomationRunRecord.status == "running",
                    )
                ).all()
                for run in running:
                    run.status = "skipped"
                    run.finished_at = now
                    run.error = "任务已停用，取消尚未开始的执行"
                    db.add(run)
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
            todo_id = task.todo_id
            self._delete_task_record(db, task)
            todo = db.get(TodoRecord, todo_id)
            if todo is not None and todo.user_id == user_id:
                db.delete(todo)
            db.commit()
        return True

    def delete_task_by_todo_id(self, *, user_id: str, todo_id: str) -> bool:
        """通过 TODO 标识删除完整自动化，兼容旧客户端的普通删除入口。"""

        task = self.get_task_by_todo_id(user_id=user_id, todo_id=todo_id)
        if task is None:
            return False
        return self.delete_task(user_id=user_id, automation_id=str(task["id"]))

    def is_claim_executable(
        self,
        *,
        automation_id: str,
        run_id: str,
        lease_id: str,
        now: datetime | None = None,
    ) -> bool:
        """确认已抢占执行仍有效，拦截排队期间发生的删除或停用。"""

        current = (now or self._utc_now()).astimezone(timezone.utc)
        with Session(self.engine) as db:
            task = db.get(AutomationTaskRecord, automation_id)
            run = db.get(AutomationRunRecord, run_id)
            if (
                task is None
                or run is None
                or run.automation_id != automation_id
                or run.user_id != task.user_id
                or not task.enabled
                or run.status != "running"
            ):
                return False
            lease_until = task.lease_until
            if lease_until is not None and lease_until.tzinfo is None:
                lease_until = lease_until.replace(tzinfo=timezone.utc)
            if task.lease_id != lease_id or lease_until is None or lease_until <= current:
                return False
            todo = db.get(TodoRecord, task.todo_id)
            return bool(todo is not None and todo.user_id == task.user_id and todo.category == "automation")

    def renew_claim(
        self,
        *,
        automation_id: str,
        run_id: str,
        lease_id: str,
        lease_seconds: int | None = None,
        now: datetime | None = None,
    ) -> bool:
        """为仍在运行且仍归当前 worker 所有的任务续租。"""

        current = (now or self._utc_now()).astimezone(timezone.utc)
        with Session(self.engine) as db:
            run = db.get(AutomationRunRecord, run_id)
            if run is None or run.automation_id != automation_id or run.status != "running":
                return False
            result = db.exec(
                update(AutomationTaskRecord)
                .execution_options(synchronize_session=False)
                .where(
                    AutomationTaskRecord.automation_id == automation_id,
                    AutomationTaskRecord.enabled.is_(True),
                    AutomationTaskRecord.lease_id == lease_id,
                    AutomationTaskRecord.lease_until > current,
                )
                .values(
                    lease_until=current + timedelta(
                        seconds=lease_seconds or self.config.limits.automation_lease_seconds
                    )
                )
            )
            db.commit()
            return result.rowcount == 1

    def claim_due_tasks(
        self,
        *,
        now: datetime | None = None,
        lease_seconds: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """抢占到期任务并创建 running 运行记录。"""

        current = (now or self._utc_now()).astimezone(timezone.utc)
        lease_until = current + timedelta(
            seconds=lease_seconds or self.config.limits.automation_lease_seconds
        )
        safe_limit = max(
            0,
            min(
                limit or self.config.limits.automation_run_default_limit,
                self.config.limits.automation_run_max_limit,
            ),
        )
        if safe_limit == 0:
            return []
        claimed: list[dict[str, Any]] = []
        with Session(self.engine) as db:
            self._purge_orphaned_tasks(db)
            self._reconcile_stale_runs(db, current=current)
            candidates = db.exec(
                select(AutomationTaskRecord).where(
                    AutomationTaskRecord.enabled.is_(True),
                    AutomationTaskRecord.next_run_at <= current,
                    or_(AutomationTaskRecord.lease_until.is_(None), AutomationTaskRecord.lease_until < current),
                )
                .order_by(AutomationTaskRecord.next_run_at, AutomationTaskRecord.created_at)
                .limit(safe_limit)
            ).all()
            for candidate in candidates:
                lease_id = f"lease_{uuid4().hex[:self.config.limits.generated_id_suffix_chars]}"
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
                stale_runs = db.exec(
                    select(AutomationRunRecord).where(
                        AutomationRunRecord.automation_id == candidate.automation_id,
                        AutomationRunRecord.status == "running",
                    )
                ).all()
                for stale_run in stale_runs:
                    stale_run.status = "failed"
                    stale_run.finished_at = current
                    stale_run.error = "执行租约已过期，已由调度器安全回收"
                    db.add(stale_run)
                run = AutomationRunRecord(
                    run_id=f"run_{uuid4().hex[:self.config.limits.generated_id_suffix_chars]}",
                    automation_id=candidate.automation_id,
                    user_id=candidate.user_id,
                    started_at=current,
                )
                db.add(run)
                claimed.append({
                    "task": self._serialize_task(candidate),
                    "run": self._serialize_run(run),
                    "leaseId": lease_id,
                })
            db.commit()
        return claimed

    def finish_run(
        self,
        *,
        automation_id: str,
        run_id: str,
        status: str,
        lease_id: str,
        output: str | None = None,
        error: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        """完成运行记录并安排下一次执行。"""

        if status not in {"success", "failed", "skipped"}:
            raise ValueError("status must be success, failed, or skipped")
        finished_at = (now or self._utc_now()).astimezone(timezone.utc)
        with Session(self.engine) as db:
            task = db.get(AutomationTaskRecord, automation_id)
            run = db.get(AutomationRunRecord, run_id)
            if (
                task is None
                or run is None
                or run.automation_id != automation_id
                or run.user_id != task.user_id
                or run.status != "running"
                or not task.enabled
            ):
                return False
            lease_until = task.lease_until
            if lease_until is not None and lease_until.tzinfo is None:
                lease_until = lease_until.replace(tzinfo=timezone.utc)
            if task.lease_id != lease_id or lease_until is None or lease_until <= finished_at:
                return False
            run.status = status
            run.finished_at = finished_at
            run.output = output
            run.error = error
            task.last_run_at = finished_at
            task.last_status = status
            task.last_error = error
            task.updated_at = finished_at
            task.lease_id = None
            task.lease_until = None
            if task.recurrence_frequency == "none":
                task.enabled = False
            else:
                task.next_run_at = self._advance_datetime_after(
                    task.next_run_at,
                    task.recurrence_frequency,
                    task.recurrence_interval,
                    task.timezone_name,
                    finished_at,
                )
            db.add(run)
            db.add(task)
            db.commit()
            return True
