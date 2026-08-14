"""
TODO 数据库服务测试。

覆盖旧 JSON 一次性迁移、提醒字段持久化和循环 TODO 推进逻辑。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest
from sqlmodel import Session, create_engine

from agent_service.models.automation import AutomationRunRecord, AutomationTaskRecord
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
        lease_id=claims[0]["leaseId"],
        now=service._parse_datetime("2026-08-02T21:02:00+08:00"),
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


def test_deleted_automation_todo_is_reconciled_before_claim(tmp_path: Path) -> None:
    """即使旧客户端只删除 TODO，调度扫描也必须清理孤儿自动化且绝不执行。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="不应再执行",
        prompt="发送已经过期的报告",
        next_run_at="2026-08-02T21:00:00+08:00",
        timezone_name="Asia/Shanghai",
    )

    assert todo_service.delete_todo(user_id="u1", todo_id=task["todoId"]) is True
    with Session(engine) as db:
        assert db.get(AutomationTaskRecord, task["id"]) is None
    assert service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00")) == []
    assert service.list_tasks(user_id="u1") == []


def test_delete_automation_removes_definition_todo_and_runs(tmp_path: Path) -> None:
    """从自动化入口删除时，定义、关联 TODO 和运行记录必须一起消失。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="待删除任务",
        prompt="执行一次",
        next_run_at="2026-08-02T21:00:00+08:00",
    )
    claim = service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00"))[0]

    assert service.delete_task_by_todo_id(user_id="u1", todo_id=task["todoId"]) is True
    assert todo_service.list_todos("u1") == []
    with Session(engine) as db:
        assert db.get(AutomationTaskRecord, task["id"]) is None
        assert db.get(AutomationRunRecord, claim["run"]["id"]) is None


def test_disabled_or_deleted_claim_cannot_start(tmp_path: Path) -> None:
    """已抢占但尚未执行的任务在停用或删除后必须立即失去执行资格。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="竞态任务",
        prompt="不应启动",
        next_run_at="2026-08-02T21:00:00+08:00",
    )
    claim = service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00"))[0]

    check_time = service._parse_datetime("2026-08-02T21:01:01+08:00")
    assert service.is_claim_executable(
        automation_id=task["id"], run_id=claim["run"]["id"], lease_id=claim["leaseId"], now=check_time,
    ) is True
    service.set_enabled(user_id="u1", automation_id=task["id"], enabled=False)
    assert service.is_claim_executable(
        automation_id=task["id"], run_id=claim["run"]["id"], lease_id=claim["leaseId"], now=check_time,
    ) is False

    service.delete_task(user_id="u1", automation_id=task["id"])
    assert service.is_claim_executable(
        automation_id=task["id"], run_id=claim["run"]["id"], lease_id=claim["leaseId"], now=check_time,
    ) is False


def test_reenable_does_not_revive_an_old_claim(tmp_path: Path) -> None:
    """停用后再启用只能产生新抢占，旧 run 不得恢复执行资格。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="重新启用任务",
        prompt="执行",
        next_run_at="2026-08-02T21:00:00+08:00",
    )
    claim = service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00"))[0]

    service.set_enabled(user_id="u1", automation_id=task["id"], enabled=False)
    service.set_enabled(user_id="u1", automation_id=task["id"], enabled=True)

    assert service.is_claim_executable(
        automation_id=task["id"],
        run_id=claim["run"]["id"],
        lease_id=claim["leaseId"],
        now=service._parse_datetime("2026-08-02T21:01:01+08:00"),
    ) is False


def test_concurrent_schedulers_claim_one_run_only(tmp_path: Path) -> None:
    """两个调度实例同时扫描时，同一到期任务只能产生一条运行记录。"""

    db_path = tmp_path / "automation-concurrent.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    first = AutomationService(engine=engine, todo_service=todo_service)
    second = AutomationService(engine=engine, todo_service=todo_service)
    task = first.create_task(
        user_id="u1",
        text="并发任务",
        prompt="只执行一次",
        next_run_at="2026-08-02T21:00:00+08:00",
    )
    barrier = Barrier(3)

    def claim(service: AutomationService) -> list[dict[str, object]]:
        """与另一调度实例同时开始抢占，并将线程异常传回主测试。"""

        barrier.wait()
        return service.claim_due_tasks(now=service._parse_datetime("2026-08-02T21:01:00+08:00"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(claim, service) for service in (first, second)]
        barrier.wait()
        results = [future.result(timeout=5) for future in futures]

    assert sum(len(items) for items in results) == 1
    assert len(first.list_runs(user_id="u1", automation_id=task["id"])) == 1


def test_claim_lease_is_required_and_wrong_or_expired_lease_fails_closed(tmp_path: Path) -> None:
    """缺失、错误或过期的租约都不得执行、续租或完成任务。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="租约校验任务",
        prompt="执行",
        next_run_at="2026-08-02T21:00:00+08:00",
    )
    claimed_at = service._parse_datetime("2026-08-02T21:01:00+08:00")
    claim = service.claim_due_tasks(now=claimed_at, lease_seconds=30)[0]
    run_id = claim["run"]["id"]

    with pytest.raises(TypeError):
        service.is_claim_executable(automation_id=task["id"], run_id=run_id)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        service.finish_run(automation_id=task["id"], run_id=run_id, status="success")  # type: ignore[call-arg]

    assert service.is_claim_executable(
        automation_id=task["id"], run_id=run_id, lease_id="lease_wrong", now=claimed_at,
    ) is False
    assert service.finish_run(
        automation_id=task["id"],
        run_id=run_id,
        lease_id="lease_wrong",
        status="success",
        now=claimed_at,
    ) is False

    expired_at = claimed_at.replace(second=30)
    assert service.is_claim_executable(
        automation_id=task["id"], run_id=run_id, lease_id=claim["leaseId"], now=expired_at,
    ) is False
    assert service.renew_claim(
        automation_id=task["id"],
        run_id=run_id,
        lease_id=claim["leaseId"],
        now=expired_at,
    ) is False
    assert service.finish_run(
        automation_id=task["id"],
        run_id=run_id,
        lease_id=claim["leaseId"],
        status="success",
        now=expired_at,
    ) is False

    run = service.list_runs(user_id="u1", automation_id=task["id"])[0]
    assert run["status"] == "running"
    assert service.list_tasks(user_id="u1")[0]["nextRunAt"] == "2026-08-02T13:00:00+00:00"


def test_finish_rejects_a_run_owned_by_another_automation(tmp_path: Path) -> None:
    """run_id 与 automation_id 错配时不得污染任一任务或运行记录。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    for text in ("任务一", "任务二"):
        service.create_task(
            user_id="u1",
            text=text,
            prompt="执行",
            next_run_at="2026-08-02T21:00:00+08:00",
        )
    claimed_at = service._parse_datetime("2026-08-02T21:01:00+08:00")
    claims = service.claim_due_tasks(now=claimed_at, limit=2)
    first, second = claims

    assert service.finish_run(
        automation_id=first["task"]["id"],
        run_id=second["run"]["id"],
        lease_id=first["leaseId"],
        status="success",
        now=claimed_at,
    ) is False

    tasks_by_id = {task["id"]: task for task in service.list_tasks(user_id="u1")}
    for claim in claims:
        runs = service.list_runs(user_id="u1", automation_id=claim["task"]["id"])
        assert runs[0]["status"] == "running"
        assert tasks_by_id[claim["task"]["id"]]["enabled"] is True


def test_expired_lease_invalidates_old_worker_and_finish_is_idempotent(tmp_path: Path) -> None:
    """租约过期重抢后旧 worker 不得写回，新 worker 只能完成一次并跳过错过周期。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="租约任务",
        prompt="长任务",
        next_run_at="2026-08-01T21:00:00+08:00",
        timezone_name="Asia/Shanghai",
        recurrence={"frequency": "daily", "interval": 1},
    )
    old_claim = service.claim_due_tasks(
        now=service._parse_datetime("2026-08-02T21:00:00+08:00"),
        lease_seconds=30,
    )[0]
    new_claim = service.claim_due_tasks(
        now=service._parse_datetime("2026-08-02T21:00:31+08:00"),
        lease_seconds=30,
    )[0]
    finish_at = service._parse_datetime("2026-08-05T21:01:00+08:00")
    with Session(engine) as db:
        record = db.get(AutomationTaskRecord, task["id"])
        assert record is not None
        # 模拟长任务期间 heartbeat 持续续租后的最终数据库状态。
        record.lease_until = finish_at + timedelta(seconds=30)
        db.add(record)
        db.commit()

    assert service.finish_run(
        automation_id=task["id"],
        run_id=old_claim["run"]["id"],
        lease_id=old_claim["leaseId"],
        status="success",
        now=finish_at,
    ) is False
    assert service.finish_run(
        automation_id=task["id"],
        run_id=new_claim["run"]["id"],
        lease_id=new_claim["leaseId"],
        status="success",
        now=finish_at,
    ) is True
    assert service.finish_run(
        automation_id=task["id"],
        run_id=new_claim["run"]["id"],
        lease_id=new_claim["leaseId"],
        status="success",
        now=service._parse_datetime("2026-08-05T21:02:00+08:00"),
    ) is False

    updated = service.list_tasks(user_id="u1")[0]
    assert updated["nextRunAt"] == "2026-08-06T13:00:00+00:00"
    statuses = [run["status"] for run in service.list_runs(user_id="u1", automation_id=task["id"])]
    assert statuses == ["success", "failed"]


def test_scan_reconciles_stale_running_record_even_when_task_is_not_due(tmp_path: Path) -> None:
    """崩溃遗留的过期 running 记录不应永久挂起，也不应要求任务再次到期才收敛。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    task = service.create_task(
        user_id="u1",
        text="未来任务",
        prompt="稍后执行",
        next_run_at="2026-08-20T09:00:00+08:00",
    )
    current = service._parse_datetime("2026-08-14T09:00:00+08:00")
    run = AutomationRunRecord(
        run_id="run_stale",
        automation_id=task["id"],
        user_id="u1",
        status="running",
        started_at=current - timedelta(minutes=10),
    )
    with Session(engine) as db:
        record = db.get(AutomationTaskRecord, task["id"])
        assert record is not None
        record.lease_id = "lease_stale"
        record.lease_until = current - timedelta(seconds=1)
        db.add(record)
        db.add(run)
        db.commit()

    assert service.claim_due_tasks(now=current) == []

    reconciled = service.list_runs(user_id="u1", automation_id=task["id"])[0]
    assert reconciled["status"] == "failed"
    assert reconciled["finishedAt"] is not None
    assert "租约已过期" in str(reconciled["error"])
