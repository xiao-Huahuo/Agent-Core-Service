"""会话附件解析状态 REST/gRPC 对齐测试。

使用说明:
通过轻量 service stub 验证传输层参数与 DTO，不解析真实文件或加载模型。
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

from agent_service.api.grpc.agent_service_pb2 import AttachmentRawRequest
from agent_service.api.grpc.agent_service_pb2_grpc import AgentServiceStub, add_AgentServiceServicer_to_server
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.api.rest import agent as agent_rest


class _AttachmentStub:
    """返回稳定附件解析状态。"""

    def get_attachment(self, *, user_id: str, session_id: str, attachment_id: str) -> dict[str, Any]:
        """回显所有权字段并返回 processing 状态。"""

        return {
            "attachment_id": attachment_id,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": {"processing_status": "processing", "processing_progress": 42},
        }

    def get_attachment_file_by_uri(self, *, uri: str):  # noqa: ANN201
        """该基础 stub 不提供原文件。"""

        raise ValueError(uri)


class _AgentStub:
    """提供 gRPC servicer 所需的最小 Agent。"""

    config = SimpleNamespace()

    def close(self) -> None:
        """测试无需释放资源。"""


def _struct(payload: dict[str, object]) -> Struct:
    """构造 Struct 请求。"""

    return ParseDict(payload, Struct())


def test_attachment_status_matches_over_rest_and_grpc(monkeypatch: Any) -> None:
    """REST 与 gRPC 必须返回相同的附件级解析进度。"""

    service = _AttachmentStub()
    monkeypatch.setattr(agent_rest, "_require_attachment_service", lambda: service)
    app = FastAPI()
    app.include_router(agent_rest.router)
    rest = TestClient(app).get(
        "/agent/attachments/att-1",
        params={"user_id": "u1", "session_id": "s1"},
    )

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_AgentStub(),  # type: ignore[arg-type]
            session_service=SimpleNamespace(),  # type: ignore[arg-type]
            attachment_service=service,  # type: ignore[arg-type]
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        grpc_payload = MessageToDict(AgentServiceStub(channel).GetSessionAttachment(_struct({
            "user_id": "u1", "session_id": "s1", "attachment_id": "att-1",
        }), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert rest.status_code == 200
    assert grpc_payload == rest.json()


def test_grpc_attachment_raw_returns_exact_bytes(tmp_path) -> None:
    """gRPC 原文件接口必须按完整 URI 返回对应图片字节。"""

    image_path = tmp_path / "image11.png"
    image_path.write_bytes(b"exact-image")

    class _RawAttachmentStub(_AttachmentStub):
        """返回当前测试唯一原文件。"""

        def get_attachment_file_by_uri(self, *, uri: str):  # noqa: ANN201
            assert uri == "session-upload://u1/library/s1/image11.png"
            return image_path, "image/png", "image11.png"

    server = grpc.server(ThreadPoolExecutor(max_workers=1))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_AgentStub(),  # type: ignore[arg-type]
            session_service=SimpleNamespace(),  # type: ignore[arg-type]
            attachment_service=_RawAttachmentStub(),  # type: ignore[arg-type]
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        response = AgentServiceStub(channel).GetSessionAttachmentRaw(AttachmentRawRequest(
            uri="session-upload://u1/library/s1/image11.png",
        ), timeout=5)
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert response.content == b"exact-image"
    assert response.filename == "image11.png"
