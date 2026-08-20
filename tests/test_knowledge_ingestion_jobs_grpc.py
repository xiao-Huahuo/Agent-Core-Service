"""单文件灌库任务 gRPC 与 REST 等价行为测试。"""

from __future__ import annotations

from typing import Any

import grpc
import pytest
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct

from agent_service.api.grpc.servicer import AgentServiceServicer


class FakeJobService:
    """提供 gRPC 测试所需的任务接口。"""

    def submit(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"job_id": "ingest_1", "status": "queued", **kwargs}]

    def list_jobs(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"job_id": "ingest_1", "progress": 64, **kwargs}]

    def cancel(self, **kwargs: Any) -> dict[str, Any] | None:
        if kwargs["job_id"] == "missing":
            return None
        return {"job_id": kwargs["job_id"], "status": "cancelled", "progress": 0}


class AbortError(RuntimeError):
    """保存 gRPC 终止状态供断言。"""

    def __init__(self, code: grpc.StatusCode, details: str) -> None:
        super().__init__(details)
        self.code = code


class FakeContext:
    """只实现 servicer 测试所需的 abort。"""

    def abort(self, code: grpc.StatusCode, details: str) -> None:
        raise AbortError(code, details)


def request(payload: dict[str, Any]) -> Struct:
    return ParseDict(payload, Struct())


def build_servicer() -> AgentServiceServicer:
    return AgentServiceServicer(
        agent=object(),  # type: ignore[arg-type]
        session_service=object(),  # type: ignore[arg-type]
        knowledge_ingestion_job_service=FakeJobService(),  # type: ignore[arg-type]
    )


def test_grpc_create_list_and_cancel_match_rest_payloads() -> None:
    """三个 RPC 都使用与 REST 相同的 user_id、paths、job_id 和任务字段。"""

    servicer = build_servicer()
    context = FakeContext()

    created = MessageToDict(servicer.CreateKnowledgeIngestionJobs(
        request({"user_id": "u1", "paths": ["a.md", "b.pdf"]}), context,  # type: ignore[arg-type]
    ))
    listed = MessageToDict(servicer.ListKnowledgeIngestionJobs(
        request({"user_id": "u1", "active_only": True}), context,  # type: ignore[arg-type]
    ))
    cancelled = MessageToDict(servicer.CancelKnowledgeIngestionJob(
        request({"user_id": "u1", "job_id": "ingest_1"}), context,  # type: ignore[arg-type]
    ))

    assert created["jobs"][0]["paths"] == ["a.md", "b.pdf"]
    assert listed["jobs"][0]["active_only"] is True
    assert cancelled["status"] == "cancelled"
    assert cancelled["progress"] == 0


def test_grpc_cancel_missing_job_maps_not_found() -> None:
    """不存在任务通过标准 NOT_FOUND 状态返回。"""

    with pytest.raises(AbortError) as exc_info:
        build_servicer().CancelKnowledgeIngestionJob(
            request({"user_id": "u1", "job_id": "missing"}), FakeContext(),  # type: ignore[arg-type]
        )

    assert exc_info.value.code == grpc.StatusCode.NOT_FOUND
