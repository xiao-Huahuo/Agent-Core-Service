"""知识图谱动态队列 REST 端点回归测试。

功能说明:
验证运行中的重复请求仍会进入队列服务，由服务执行在途去重而不是被路由拒绝。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest import knowledge as knowledge_rest


class _SettingsStub:
    """提供图谱入队端点所需的活动知识库与模型配置。"""

    def __init__(self, root: Path) -> None:
        self.config = object()
        self.root = root

    def ensure_user_profile(self, *, user_id: str) -> dict[str, Any]:
        """返回稳定的用户与知识库标识。"""

        return {
            "user_id": user_id,
            "active_knowledge_library": {
                "library_id": "library-1",
                "knowledge_dir": str(self.root),
            },
        }

    def get_llm_config(self, *, user_id: str) -> dict[str, str]:
        """返回不含敏感值的测试配置。"""

        return {"model_name": "test-model"}


class _QueueStub:
    """记录每次 REST 入队，不在路由层模拟运行状态锁。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def submit(self, **kwargs: Any) -> dict[str, str]:
        """记录参数并模拟服务层在途去重。"""

        self.calls.append(kwargs)
        status = "queued" if len(self.calls) == 1 else "deduplicated"
        return {"status": status, "message": status}

    def cancel(self, **kwargs: Any) -> dict[str, str] | None:
        """记录任务终止参数并模拟不存在的任务。"""

        self.calls.append(kwargs)
        if kwargs["identity"] == "missing.md":
            return None
        return {"status": "cancelling", "message": "图谱任务正在中止"}


class _GraphMutationStub:
    """Record graph mutation requests after REST resolves the active library."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def delete_entity_node(self, **kwargs: str) -> dict[str, int]:
        """Return stable entity deletion counts."""

        self.calls.append(("delete", kwargs))
        return {"deleted_nodes": 1, "deleted_edges": 3}

    def clear_document_children(self, **kwargs: str) -> dict[str, int]:
        """Return stable document-clear counts."""

        self.calls.append(("clear", kwargs))
        return {"deleted_nodes": 2, "deleted_edges": 4}


def test_graph_rebuild_route_forwards_repeated_requests_to_queue(monkeypatch: Any, tmp_path: Path) -> None:
    """第二次同文件请求必须到达队列服务并返回去重结果。"""

    source = tmp_path / "notes.md"
    source.write_text("# notes", encoding="utf-8")
    settings = _SettingsStub(tmp_path)
    queue = _QueueStub()
    monkeypatch.setattr(knowledge_rest, "_require_settings_service", lambda: settings)
    monkeypatch.setattr(knowledge_rest, "_require_knowledge_graph_queue_service", lambda: queue)
    app = FastAPI()
    app.include_router(knowledge_rest.router)
    client = TestClient(app)

    first = client.post("/knowledge/graph/rebuild", json={"user_id": "u1", "path": "notes.md"})
    repeated = client.post("/knowledge/graph/rebuild", json={"user_id": "u1", "path": "notes.md"})

    assert first.json()["status"] == "queued"
    assert repeated.json()["status"] == "deduplicated"
    assert len(queue.calls) == 2
    assert queue.calls[0]["target_display_path"] == "notes.md"


def test_graph_rebuild_cancel_resolves_library_and_task_path(monkeypatch: Any, tmp_path: Path) -> None:
    """图谱终止端点须按当前知识库和稳定相对路径取消准确任务。"""

    queue = _QueueStub()
    monkeypatch.setattr(knowledge_rest, "_require_settings_service", lambda: _SettingsStub(tmp_path))
    monkeypatch.setattr(knowledge_rest, "_require_knowledge_graph_queue_service", lambda: queue)
    app = FastAPI()
    app.include_router(knowledge_rest.router)
    client = TestClient(app)

    cancelled = client.post("/knowledge/graph/rebuild/cancel", json={"user_id": "u1", "path": "notes/a.md"})
    missing = client.post("/knowledge/graph/rebuild/cancel", json={"user_id": "u1", "path": "missing.md"})

    assert cancelled.json() == {"status": "cancelling", "message": "图谱任务正在中止"}
    assert missing.status_code == 404
    assert queue.calls[0] == {"user_id": "u1", "library_id": "library-1", "identity": "notes/a.md"}


def test_graph_node_mutation_routes_resolve_active_library(monkeypatch: Any, tmp_path: Path) -> None:
    """Entity delete and document clear must pass normalized ownership to the service."""

    graph = _GraphMutationStub()
    monkeypatch.setattr(knowledge_rest, "_require_settings_service", lambda: _SettingsStub(tmp_path))
    monkeypatch.setattr(knowledge_rest, "_require_knowledge_graph_service", lambda: graph)
    app = FastAPI()
    app.include_router(knowledge_rest.router)
    client = TestClient(app)

    deleted = client.delete("/knowledge/graph/nodes/entity-1", params={"user_id": "u1"})
    cleared = client.post("/knowledge/graph/nodes/document-1/clear", json={"user_id": "u1"})

    assert deleted.json() == {"ok": True, "deleted_nodes": 1, "deleted_edges": 3}
    assert cleared.json() == {"ok": True, "deleted_nodes": 2, "deleted_edges": 4}
    assert graph.calls == [
        ("delete", {"user_id": "u1", "library_id": "library-1", "node_id": "entity-1"}),
        ("clear", {"user_id": "u1", "library_id": "library-1", "node_id": "document-1"}),
    ]
