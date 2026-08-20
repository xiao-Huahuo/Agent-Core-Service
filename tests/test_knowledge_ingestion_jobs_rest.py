"""单文件灌库任务 REST 端点参数、持久化列表与中止映射测试。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest import knowledge as knowledge_rest


class FakeKnowledgeIngestionJobService:
    """记录 REST 传参并返回稳定任务数据。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def submit(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("submit", kwargs))
        if "missing.md" in kwargs["paths"]:
            raise ValueError("file not found: missing.md")
        return [{"job_id": "ingest_1", "status": "queued", "path": kwargs["paths"][0]}]

    def list_jobs(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("list", kwargs))
        return [{"job_id": "ingest_1", "status": "running", "progress": 37}]

    def cancel(self, **kwargs: Any) -> dict[str, Any] | None:
        self.calls.append(("cancel", kwargs))
        if kwargs["job_id"] == "missing":
            return None
        return {"job_id": kwargs["job_id"], "status": "cancelled", "progress": 0}


def build_client(monkeypatch: Any) -> tuple[TestClient, FakeKnowledgeIngestionJobService]:
    service = FakeKnowledgeIngestionJobService()
    monkeypatch.setattr(knowledge_rest, "_require_knowledge_ingestion_job_service", lambda: service)
    app = FastAPI()
    app.include_router(knowledge_rest.router)
    return TestClient(app), service


def test_create_and_list_ingestion_jobs(monkeypatch: Any) -> None:
    """创建应逐路径透传，列表应保留 active_only 过滤。"""

    client, service = build_client(monkeypatch)
    created = client.post("/knowledge/ingestion/jobs", json={"user_id": "u1", "paths": ["a.md", "b.pdf"]})
    listed = client.get("/knowledge/ingestion/jobs", params={"user_id": "u1", "active_only": "true"})

    assert created.status_code == 200
    assert created.json()["jobs"][0]["status"] == "queued"
    assert listed.json()["jobs"][0]["progress"] == 37
    assert service.calls == [
        ("submit", {"user_id": "u1", "paths": ["a.md", "b.pdf"]}),
        ("list", {"user_id": "u1", "active_only": True}),
    ]


def test_cancel_returns_zero_progress_and_maps_missing_job(monkeypatch: Any) -> None:
    """中止应返回未灌库进度，错误用户或不存在任务应为 404。"""

    client, service = build_client(monkeypatch)
    cancelled = client.post("/knowledge/ingestion/jobs/ingest_1/cancel", json={"user_id": "u1"})
    missing = client.post("/knowledge/ingestion/jobs/missing/cancel", json={"user_id": "u1"})

    assert cancelled.json() == {"job_id": "ingest_1", "status": "cancelled", "progress": 0}
    assert missing.status_code == 404
    assert service.calls[-1] == ("cancel", {"job_id": "missing", "user_id": "u1"})


def test_create_rejects_empty_and_invalid_paths(monkeypatch: Any) -> None:
    """空任务与服务层文件校验错误均返回可读的 422。"""

    client, _ = build_client(monkeypatch)
    empty = client.post("/knowledge/ingestion/jobs", json={"user_id": "u1", "paths": []})
    missing = client.post("/knowledge/ingestion/jobs", json={"user_id": "u1", "paths": ["missing.md"]})

    assert empty.status_code == 422
    assert missing.status_code == 422
    assert "file not found" in missing.json()["detail"]
