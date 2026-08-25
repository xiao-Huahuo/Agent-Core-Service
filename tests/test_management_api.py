"""
模型管理与编译管理 REST/gRPC 对齐测试。

使用说明:
验证两个管理面板通过正式后端服务获得同形数据，用户标识缺失时保持传输层校验。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import grpc
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct

from agent_service.api.grpc.agent_service_pb2_grpc import (
    AgentServiceStub,
    add_AgentServiceServicer_to_server,
)
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.api.rest import settings as settings_rest


class _ModelManagementStub:
    """返回一条带真实管理字段形状的模型记录。"""

    def get_management_status(self, *, user_id: str) -> dict[str, Any]:
        """保留 user_id 以验证 REST/gRPC 参数一致。"""

        return {"models": [{
            "key": "embedding", "name": "demo", "path": "D:/models/demo",
            "size_bytes": 12, "file_count": 3, "enabled": True, "active": True,
            "downloaded": True, "status": "ready", "progress": {"status": "idle"},
            "details": {"user_id": user_id},
        }]}


class _LatexManagementStub:
    """返回系统 MiKTeX 管理详情。"""

    def get_management_status(self) -> dict[str, Any]:
        """返回编译器来源、路径、大小和引擎。"""

        return {
            "status": "ready", "source": "system", "distribution": "MiKTeX",
            "distribution_path": "D:/MiKTeX", "size_bytes": 100, "file_count": 20,
            "default_engine": "pdflatex", "engines": [{"name": "pdflatex", "available": True}],
        }


class _AgentStub:
    """提供 gRPC servicer 所需的最小 Agent。"""

    config = SimpleNamespace()

    def close(self) -> None:
        """测试无需释放资源。"""


def _struct(payload: dict[str, object]) -> Struct:
    """构造通用 protobuf 请求。"""

    return ParseDict(payload, Struct())


def test_management_rest_returns_service_owned_details(monkeypatch: Any) -> None:
    """REST 管理接口不得由前端拼接模型或编译器详情。"""

    monkeypatch.setattr(settings_rest, "_require_model_management_service", lambda: _ModelManagementStub())
    monkeypatch.setattr(settings_rest, "_require_latex_service", lambda: _LatexManagementStub())
    app = FastAPI()
    app.include_router(settings_rest.router)
    client = TestClient(app)

    models = client.get("/settings/models/management", params={"user_id": "u1"})
    compiler = client.get("/settings/latex/management", params={"user_id": "u1"})

    assert models.status_code == 200
    assert models.json()["models"][0]["details"]["user_id"] == "u1"
    assert compiler.status_code == 200
    assert compiler.json()["source"] == "system"


def test_management_grpc_matches_rest_fields() -> None:
    """gRPC 暴露与 REST 相同的模型和编译器字段。"""

    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_AgentStub(),  # type: ignore[arg-type]
            session_service=SimpleNamespace(),  # type: ignore[arg-type]
            model_management_service=_ModelManagementStub(),  # type: ignore[arg-type]
            latex_service=_LatexManagementStub(),  # type: ignore[arg-type]
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        stub = AgentServiceStub(channel)
        models = MessageToDict(stub.GetModelManagement(_struct({"user_id": "u1"}), timeout=5))
        compiler = MessageToDict(stub.GetLatexManagement(_struct({"user_id": "u1"}), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert models["models"][0]["path"] == "D:/models/demo"
    assert compiler["distribution"] == "MiKTeX"
