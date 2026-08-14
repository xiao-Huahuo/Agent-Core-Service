"""自动化 REST DTO、错误映射与调用参数测试。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest import automation as automation_rest


class FakeAutomationService:
    """提供 REST 测试所需的最小自动化服务。"""

    def __init__(self) -> None:
        self.toggle_calls: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    def list_tasks(self, **kwargs: Any) -> list[dict[str, Any]]:
        """返回一条可用于验证列表参数的任务。"""

        return [{"id": "automation_1", "userId": kwargs["user_id"]}]

    def create_task(self, **kwargs: Any) -> dict[str, Any]:
        """记录创建参数，并模拟领域校验错误。"""

        self.create_calls.append(kwargs)
        if kwargs["timezone_name"] == "Invalid/Zone":
            raise ValueError("unknown timezone: Invalid/Zone")
        return {"id": "automation_created", "todoId": "todo_created", **kwargs}

    def set_enabled(self, **kwargs: Any) -> dict[str, Any] | None:
        """记录严格布尔值并返回任务。"""

        self.toggle_calls.append(kwargs)
        if kwargs["automation_id"] == "missing":
            return None
        return {"id": kwargs["automation_id"], "enabled": kwargs["enabled"]}

    def list_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        """返回运行记录并保留查询参数供断言。"""

        return [{"id": "run_1", **kwargs}]

    def delete_task(self, **kwargs: Any) -> bool:
        """记录删除参数，并模拟不存在任务。"""

        self.delete_calls.append(kwargs)
        return kwargs["automation_id"] != "missing"


def build_client(monkeypatch: Any) -> tuple[TestClient, FakeAutomationService]:
    """创建只挂载自动化路由的测试应用。"""

    service = FakeAutomationService()
    monkeypatch.setattr(automation_rest, "_require_automation_service", lambda: service)
    app = FastAPI()
    app.include_router(automation_rest.router)
    return TestClient(app), service


def test_toggle_rejects_string_boolean(monkeypatch: Any) -> None:
    """字符串 'false' 不得被 Python bool() 错误转换成启用。"""

    client, service = build_client(monkeypatch)

    response = client.post("/automation/toggle", json={
        "user_id": "u1",
        "automation_id": "automation_1",
        "enabled": "false",
    })

    assert response.status_code == 422
    assert service.toggle_calls == []


def test_toggle_accepts_boolean_and_maps_not_found(monkeypatch: Any) -> None:
    """真实布尔值应透传，错误用户或不存在任务保持 404。"""

    client, service = build_client(monkeypatch)
    success = client.post("/automation/toggle", json={
        "user_id": "u1",
        "automation_id": "automation_1",
        "enabled": False,
    })
    missing = client.post("/automation/toggle", json={
        "user_id": "u1",
        "automation_id": "missing",
        "enabled": True,
    })

    assert success.status_code == 200
    assert success.json()["enabled"] is False
    assert service.toggle_calls[0]["enabled"] is False
    assert missing.status_code == 404


def test_rest_lifecycle_uses_consistent_automation_identifiers(monkeypatch: Any) -> None:
    """列表、创建、运行记录和删除端点应保持同一套字段与标识语义。"""

    client, service = build_client(monkeypatch)
    listed = client.get("/automation/list", params={"user_id": "u/1"})
    created = client.post("/automation/add", json={
        "user_id": "u/1",
        "text": "整理日报",
        "prompt": "汇总今天的进展",
        "next_run_at": "2026-08-15T09:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "recurrence": {"frequency": "daily", "interval": 2},
        "access_mode": "sandbox",
    })
    runs = client.get("/automation/runs", params={
        "user_id": "u/1",
        "automation_id": "automation_1",
        "limit": 7,
    })
    deleted = client.post("/automation/delete", json={
        "user_id": "u/1",
        "automation_id": "automation_1",
    })

    assert listed.status_code == 200
    assert listed.json()[0]["userId"] == "u/1"
    assert created.status_code == 200
    assert service.create_calls == [{
        "user_id": "u/1",
        "text": "整理日报",
        "prompt": "汇总今天的进展",
        "next_run_at": "2026-08-15T09:00:00+08:00",
        "timezone_name": "Asia/Shanghai",
        "recurrence": {"frequency": "daily", "interval": 2},
        "access_mode": "sandbox",
    }]
    assert runs.status_code == 200
    assert runs.json()[0]["limit"] == 7
    assert deleted.json() == {"deleted": True}
    assert service.delete_calls == [{"user_id": "u/1", "automation_id": "automation_1"}]


def test_create_and_delete_map_validation_and_not_found_errors(monkeypatch: Any) -> None:
    """非法枚举、领域校验错误和不存在删除都应返回稳定的 HTTP 状态。"""

    client, service = build_client(monkeypatch)
    invalid_access = client.post("/automation/add", json={
        "user_id": "u1",
        "text": "任务",
        "prompt": "执行",
        "next_run_at": "2026-08-15T09:00:00+08:00",
        "access_mode": "root",
    })
    invalid_timezone = client.post("/automation/add", json={
        "user_id": "u1",
        "text": "任务",
        "prompt": "执行",
        "next_run_at": "2026-08-15T09:00:00+08:00",
        "timezone": "Invalid/Zone",
    })
    missing = client.post("/automation/delete", json={
        "user_id": "u1",
        "automation_id": "missing",
    })

    assert invalid_access.status_code == 422
    assert service.create_calls == [{
        "user_id": "u1",
        "text": "任务",
        "prompt": "执行",
        "next_run_at": "2026-08-15T09:00:00+08:00",
        "timezone_name": "Invalid/Zone",
        "recurrence": {"frequency": "none", "interval": 1},
        "access_mode": "sandbox",
    }]
    assert invalid_timezone.status_code == 422
    assert "unknown timezone" in invalid_timezone.json()["detail"]
    assert missing.status_code == 404
