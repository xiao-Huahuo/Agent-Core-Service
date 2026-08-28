"""
自动化调度器执行边界测试。

覆盖任务已抢占但仍在执行队列中时发生删除、停用，以及正常执行回写，
确保页面操作与后台实际行为保持一致。
"""

from __future__ import annotations

from concurrent.futures import Future
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.db_test_utils import create_test_engine as create_engine

from agent_service.services.automation.scheduler import AutomationScheduler
from agent_service.services.automation.service import AutomationService
from agent_service.services.todo.service import TodoService


class FakeSessionService:
    """记录调度器创建的独立会话，供测试断言。"""

    def __init__(self) -> None:
        self.created: list[Any] = []

    def create_session(self, payload: Any) -> Any:
        """返回具有 session_id 的最小会话对象。"""

        self.created.append(payload)
        return SimpleNamespace(session_id="session_automation")


class FakeAgent:
    """记录自动化 Prompt，避免测试启动真实 Agent。"""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.cancelled_sessions: list[str] = []

    def run_session_prompt(self, **kwargs: Any) -> dict[str, str]:
        """模拟一次同步 Agent 执行。"""

        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {"final_output": "执行完成"}

    def cancel_session(self, session_id: str) -> None:
        """记录因任务停用、删除或租约丢失触发的协作取消。"""

        self.cancelled_sessions.append(session_id)


def build_claim(tmp_path: Path) -> tuple[AutomationService, dict[str, Any]]:
    """创建并抢占一条立即到期任务。"""

    engine = create_engine("sqlite://")
    todo_service = TodoService(engine=engine, legacy_data_dir=str(tmp_path))
    service = AutomationService(engine=engine, todo_service=todo_service)
    now = service._utc_now()
    service.create_task(
        user_id="u1",
        text="自动化测试",
        prompt="整理今日资料",
        next_run_at=(now - timedelta(minutes=1)).isoformat(),
    )
    claim = service.claim_due_tasks(now=now)[0]
    return service, claim


def test_deleted_queued_claim_never_creates_agent_session(tmp_path: Path) -> None:
    """删除已经抢占但尚未开始的任务后，不得再创建会话或调用 Agent。"""

    service, claim = build_claim(tmp_path)
    service.delete_task(user_id="u1", automation_id=claim["task"]["id"])
    agent = FakeAgent()
    sessions = FakeSessionService()
    scheduler = AutomationScheduler(automation_service=service, agent=agent, session_service=sessions)

    scheduler._execute_claim(claim)

    assert sessions.created == []
    assert agent.calls == []


def test_disabled_queued_claim_never_creates_agent_session(tmp_path: Path) -> None:
    """停用排队中的任务后，旧抢占结果必须作废。"""

    service, claim = build_claim(tmp_path)
    service.set_enabled(user_id="u1", automation_id=claim["task"]["id"], enabled=False)
    agent = FakeAgent()
    sessions = FakeSessionService()
    scheduler = AutomationScheduler(automation_service=service, agent=agent, session_service=sessions)

    scheduler._execute_claim(claim)

    assert sessions.created == []
    assert agent.calls == []


def test_valid_claim_executes_and_records_success(tmp_path: Path) -> None:
    """仍有效的抢占应创建独立会话、执行 Prompt 并回写成功。"""

    service, claim = build_claim(tmp_path)
    agent = FakeAgent()
    sessions = FakeSessionService()
    scheduler = AutomationScheduler(automation_service=service, agent=agent, session_service=sessions)

    scheduler._execute_claim(claim)

    assert len(sessions.created) == 1
    assert len(agent.calls) == 1
    assert "整理今日资料" in agent.calls[0]["prompt"]
    runs = service.list_runs(user_id="u1", automation_id=claim["task"]["id"])
    assert runs[0]["status"] == "success"
    assert runs[0]["output"] == "执行完成"


def test_synchronous_renew_failure_stops_before_agent_call(tmp_path: Path, monkeypatch: Any) -> None:
    """会话创建后的同步续租失败时，必须取消会话且不得调用 Agent。"""

    service, claim = build_claim(tmp_path)
    monkeypatch.setattr(service, "renew_claim", lambda **_kwargs: False)
    agent = FakeAgent()
    sessions = FakeSessionService()
    scheduler = AutomationScheduler(
        automation_service=service,
        agent=agent,
        session_service=sessions,
        lease_seconds=30,
    )

    try:
        scheduler._execute_claim(claim)
    finally:
        scheduler.shutdown()

    assert len(sessions.created) == 1
    assert agent.calls == []
    assert agent.cancelled_sessions == ["session_automation"]


def test_heartbeat_lease_loss_cancels_session_without_waiting(tmp_path: Path, monkeypatch: Any) -> None:
    """后台续租失败应立即协作取消活跃 Session，测试不得真实等待心跳周期。"""

    service, claim = build_claim(tmp_path)
    renew_calls: list[dict[str, Any]] = []

    def reject_renewal(**kwargs: Any) -> bool:
        """记录一次心跳续租并模拟租约已被另一 worker 接管。"""

        renew_calls.append(kwargs)
        return False

    class ImmediateTick:
        """让心跳循环立即进入首次续租，避免测试 sleep。"""

        def __init__(self) -> None:
            self.intervals: list[float] = []

        def wait(self, interval: float) -> bool:
            """记录心跳间隔并立即返回未停止。"""

            self.intervals.append(interval)
            return False

    monkeypatch.setattr(service, "renew_claim", reject_renewal)
    agent = FakeAgent()
    scheduler = AutomationScheduler(
        automation_service=service,
        agent=agent,
        session_service=FakeSessionService(),
        lease_seconds=30,
    )
    stop_event = ImmediateTick()

    try:
        scheduler._renew_while_running(
            str(claim["task"]["id"]),
            str(claim["run"]["id"]),
            str(claim["leaseId"]),
            "session_automation",
            stop_event,  # type: ignore[arg-type]
        )
    finally:
        scheduler.shutdown()

    assert stop_event.intervals == [10.0]
    assert renew_calls == [{
        "automation_id": claim["task"]["id"],
        "run_id": claim["run"]["id"],
        "lease_id": claim["leaseId"],
        "lease_seconds": 30,
    }]
    assert agent.cancelled_sessions == ["session_automation"]


def test_run_loop_claims_only_current_worker_capacity(tmp_path: Path, monkeypatch: Any) -> None:
    """已有一个执行占用 worker 时，扫描只能再抢占一个任务。"""

    service, _claim = build_claim(tmp_path)
    claim_calls: list[dict[str, int]] = []

    def record_claim(**kwargs: int) -> list[dict[str, Any]]:
        """记录调度扫描的容量参数且不返回任务。"""

        claim_calls.append(kwargs)
        return []

    class OnePassStopEvent:
        """允许 run loop 执行一轮后立即退出。"""

        def __init__(self) -> None:
            self.stopped = False

        def is_set(self) -> bool:
            """返回当前停止状态。"""

            return self.stopped

        def wait(self, _timeout: float) -> bool:
            """在第一轮扫描末尾停止循环。"""

            self.stopped = True
            return True

        def set(self) -> None:
            """兼容 scheduler.shutdown。"""

            self.stopped = True

    monkeypatch.setattr(service, "claim_due_tasks", record_claim)
    scheduler = AutomationScheduler(
        automation_service=service,
        agent=FakeAgent(),
        session_service=FakeSessionService(),
        max_workers=2,
        lease_seconds=45,
    )
    scheduler._futures = {Future()}
    scheduler._stop_event = OnePassStopEvent()  # type: ignore[assignment]

    try:
        scheduler._run_loop()
    finally:
        scheduler.shutdown()

    assert claim_calls == [{"lease_seconds": 45, "limit": 1}]
