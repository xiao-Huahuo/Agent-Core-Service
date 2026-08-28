"""
自动化内置工具与事务边界测试。

功能说明:
- 验证 Agent 的 TODO 工具会把自动化任务路由到启停和级联删除服务。
- 验证普通 TODO 仍保持原有切换与删除行为。
- 验证自动化创建、删除在数据库提交失败时不会留下部分记录。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlmodel import Session, select

from tests.db_test_utils import create_test_engine as create_engine

import agent_service.tools.builtin.tasks as builtin
from agent_service.models.automation import AutomationRunRecord, AutomationTaskRecord
from agent_service.models.todo import TodoRecord
from agent_service.services.automation.service import AutomationService
from agent_service.services.todo.service import TodoService


def install_tool_services(
    monkeypatch: pytest.MonkeyPatch,
    *,
    automation_service: Mock,
    todo_service: Mock,
) -> None:
    """向内置工具注入最小用户运行时及可观测的服务替身。"""

    monkeypatch.setattr(builtin, "get_tool_runtime", lambda: SimpleNamespace(user_id="u1"))
    monkeypatch.setattr(builtin, "_get_automation_service", lambda: automation_service)
    monkeypatch.setattr(builtin, "_get_todo_service", lambda: todo_service)


@pytest.mark.parametrize(
    ("currently_enabled", "expected_enabled", "expected_status"),
    [(True, False, "已暂停"), (False, True, "已启用")],
)
def test_toggle_todo_routes_automation_to_enablement(
    monkeypatch: pytest.MonkeyPatch,
    currently_enabled: bool,
    expected_enabled: bool,
    expected_status: str,
) -> None:
    """自动化 TODO 的切换动作应改变调度启用态，不得修改普通完成态。"""

    automation_service = Mock()
    automation_service.get_task_by_todo_id.return_value = {
        "id": "automation_1",
        "enabled": currently_enabled,
    }
    automation_service.set_enabled.return_value = {
        "id": "automation_1",
        "enabled": expected_enabled,
    }
    todo_service = Mock()
    install_tool_services(
        monkeypatch,
        automation_service=automation_service,
        todo_service=todo_service,
    )

    result = builtin.toggle_todo("todo_automation")

    automation_service.get_task_by_todo_id.assert_called_once_with(
        user_id="u1",
        todo_id="todo_automation",
    )
    automation_service.set_enabled.assert_called_once_with(
        user_id="u1",
        automation_id="automation_1",
        enabled=expected_enabled,
    )
    todo_service.toggle_todo.assert_not_called()
    assert expected_status in result


def test_delete_todo_routes_automation_to_cascade_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """自动化 TODO 删除应走完整生命周期服务，不得退化为普通 TODO 删除。"""

    automation_service = Mock()
    automation_service.delete_task_by_todo_id.return_value = True
    todo_service = Mock()
    install_tool_services(
        monkeypatch,
        automation_service=automation_service,
        todo_service=todo_service,
    )

    result = builtin.delete_todo("todo_automation")

    automation_service.delete_task_by_todo_id.assert_called_once_with(
        user_id="u1",
        todo_id="todo_automation",
    )
    todo_service.delete_todo.assert_not_called()
    assert result == "已取消并删除自动化任务: todo_automation"


def test_toggle_todo_preserves_regular_todo_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    """非自动化 TODO 仍应调用原有完成态切换服务并返回原提示。"""

    automation_service = Mock()
    automation_service.get_task_by_todo_id.return_value = None
    todo_service = Mock()
    todo_service.toggle_todo.return_value = {
        "id": "todo_regular",
        "text": "普通任务",
        "done": True,
    }
    install_tool_services(
        monkeypatch,
        automation_service=automation_service,
        todo_service=todo_service,
    )

    result = builtin.toggle_todo("todo_regular")

    todo_service.toggle_todo.assert_called_once_with(user_id="u1", todo_id="todo_regular")
    automation_service.set_enabled.assert_not_called()
    assert result == "已切换待办 [todo_regular] 状态为: 已完成 — 普通任务"


def test_delete_todo_preserves_regular_todo_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    """非自动化 TODO 在自动化查询未命中后仍应由原服务删除。"""

    automation_service = Mock()
    automation_service.delete_task_by_todo_id.return_value = False
    todo_service = Mock()
    todo_service.delete_todo.return_value = True
    install_tool_services(
        monkeypatch,
        automation_service=automation_service,
        todo_service=todo_service,
    )

    result = builtin.delete_todo("todo_regular")

    todo_service.delete_todo.assert_called_once_with(user_id="u1", todo_id="todo_regular")
    assert result == "已删除待办: todo_regular"


def test_create_automation_rolls_back_both_records_when_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """创建事务提交失败时不得留下 TODO 或自动化定义。"""

    engine = create_engine("sqlite://")
    service = AutomationService(engine=engine, todo_service=TodoService(engine=engine))

    def reject_commit(_session: Session) -> None:
        """模拟数据库在原子创建事务提交阶段失败。"""

        raise RuntimeError("commit failed")

    with monkeypatch.context() as scoped:
        scoped.setattr(Session, "commit", reject_commit)
        with pytest.raises(RuntimeError, match="commit failed"):
            service.create_task(
                user_id="u1",
                text="事务创建",
                prompt="不得留下部分数据",
                next_run_at="2026-08-15T09:00:00+08:00",
            )

    with Session(engine) as db:
        assert db.exec(select(TodoRecord)).all() == []
        assert db.exec(select(AutomationTaskRecord)).all() == []


def test_delete_automation_rolls_back_all_records_when_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """删除事务提交失败时 TODO、自动化定义和运行记录必须全部保留。"""

    engine = create_engine("sqlite://")
    service = AutomationService(engine=engine, todo_service=TodoService(engine=engine))
    task = service.create_task(
        user_id="u1",
        text="事务删除",
        prompt="失败时全部保留",
        next_run_at="2026-08-15T09:00:00+08:00",
    )
    claim = service.claim_due_tasks(now=service._parse_datetime("2026-08-15T09:01:00+08:00"))[0]

    def reject_commit(_session: Session) -> None:
        """模拟数据库在原子删除事务提交阶段失败。"""

        raise RuntimeError("commit failed")

    with monkeypatch.context() as scoped:
        scoped.setattr(Session, "commit", reject_commit)
        with pytest.raises(RuntimeError, match="commit failed"):
            service.delete_task(user_id="u1", automation_id=task["id"])

    with Session(engine) as db:
        assert db.get(TodoRecord, task["todoId"]) is not None
        assert db.get(AutomationTaskRecord, task["id"]) is not None
        assert db.get(AutomationRunRecord, claim["run"]["id"]) is not None
