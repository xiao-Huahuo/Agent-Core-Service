"""
TODO 数据库服务测试。

覆盖旧 JSON 一次性迁移、提醒字段持久化和循环 TODO 推进逻辑。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, create_engine

from agent_service.models.automation import AutomationTaskRecord
from agent_service.services.automation_service import AutomationService
from agent_service.services.todo_service import TodoService


def test_legacy_json_is_imported_once(tmp_path: Path) -> None:
    """旧 JSON 应被导入数据库,之后 JSON 修改不应影响读取结果。"""

    legacy_dir = tmp_path / "todos"
    legacy_dir.mkdir()
    (legacy_dir / "u1.json").write_text(
        json.dumps([{"id": "old-1", "text": "旧任务", "done": False}], ensure_ascii=False),
        encoding="utf-8",
    )
    service = TodoService(engine=create_engine("sqlite://"), legacy_data_dir=str(tmp_path))

    assert service.list_todos("u1")[0]["id"] == "old-1"
    (legacy_dir / "u1.json").write_text("[]", encoding="utf-8")
    assert service.list_todos("u1")[0]["text"] == "旧任务"


def test_repeating_todo_advances_due_and_reminder(tmp_path: Path) -> None:
    """完成每日循环 TODO 后应推进截止时间和提醒时间,而不是永久完成。"""

    service = TodoService(engine=create_engine("sqlite://"), legacy_data_dir=str(tmp_path))
    item = service.add_todo(
        "u1",
        "每日备份",
        due_date="2026-08-02T21:00:00+00:00",
        reminder_at="2026-08-02T20:30:00+00:00",
        recurrence={"frequency": "daily", "interval": 1},
    )

    updated = service.toggle_todo("u1", item["id"])

    assert updated is not None
    assert updated["done"] is False
    assert updated["lastCompletedAt"]
    assert updated["dueDate"] == "2026-08-03T21:00:00+00:00"
    assert updated["reminderAt"] == "2026-08-03T20:30:00+00:00"


def test_automation_claim_and_finish_schedules_next_run(tmp_path: Path) -> None:
    """到期自动化任务只能被抢占一次,成功后应安排下一次执行。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="每日提交代码",
        prompt="检查变更并提交",
        next_run_at="2026-08-02T21:00:00+08:00",
        timezone_name="Asia/Shanghai",
        recurrence={"frequency": "daily", "interval": 1},
        access_mode="full_access",
    )

    claims = service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00"))
    assert len(claims) == 1
    assert service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:01+08:00")) == []

    service.finish_run(
        automation_id=task["id"],
        run_id=claims[0]["run"]["id"],
        status="success",
        output="done",
    )
    updated = service.list_tasks(user_id="u1")[0]
    assert updated["enabled"] is True
    assert updated["nextRunAt"] == "2026-08-03T13:00:00+00:00"
    assert service.list_runs(user_id="u1", automation_id=task["id"])[0]["status"] == "success"


def test_automation_claim_handles_expired_sqlite_lease(tmp_path: Path) -> None:
    """SQLite 读出的无时区租约过期时间也应能参与任务抢占。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="过期租约任务",
        prompt="检查任务",
        next_run_at="2026-08-02T21:00:00+08:00",
        timezone_name="Asia/Shanghai",
    )

    with Session(engine) as db:
        record = db.get(AutomationTaskRecord, task["id"])
        assert record is not None
        record.lease_until = datetime(2026, 8, 2, 12, 59, tzinfo=timezone.utc)
        db.add(record)
        db.commit()

    claims = service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00"))
    assert len(claims) == 1
