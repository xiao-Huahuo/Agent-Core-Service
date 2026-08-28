"""
Automation gRPC transport integration tests.

功能说明:
本文件通过临时 gRPC 服务器验证自动化列表、创建、启停、运行记录和删除 RPC
均注册到生成代码，并复用与 REST 相同的字段和 AutomationService 业务语义。

使用说明:
在项目根目录执行 `python -m pytest tests/test_automation_grpc.py`。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

import grpc
import pytest
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from sqlalchemy.pool import StaticPool
from tests.db_test_utils import create_test_engine as create_engine

from agent_service.api.grpc.agent_service_pb2_grpc import (
    AgentServiceStub,
    add_AgentServiceServicer_to_server,
)
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.services.automation.service import AutomationService
from agent_service.services.todo.service import TodoService


class _StubAgent:
    """提供 gRPC Servicer 构造所需的最小 Agent 接口。"""

    def close(self) -> None:
        """测试服务器关闭时无需释放其他资源。"""


class _StubSessionService:
    """自动化 CRUD 测试不会访问会话服务，仅保留显式依赖占位。"""


def _struct(payload: dict[str, object]) -> Struct:
    """将 REST 形态字典转换为 gRPC Struct 请求。"""

    return ParseDict(payload, Struct())


@contextmanager
def _running_automation_stub() -> Iterator[tuple[AgentServiceStub, TodoService]]:
    """启动绑定随机本机端口的真实 gRPC 服务，并在退出时完整关闭端口。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    todo_service = TodoService(engine=engine)
    automation_service = AutomationService(engine=engine, todo_service=todo_service)
    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_StubAgent(),  # type: ignore[arg-type]
            session_service=_StubSessionService(),  # type: ignore[arg-type]
            automation_service=automation_service,
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    assert port > 0
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        grpc.channel_ready_future(channel).result(timeout=5)
        yield AgentServiceStub(channel), todo_service
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)


def test_automation_grpc_crud_matches_rest_field_semantics() -> None:
    """五个自动化 RPC 应通过真实传输完成完整 CRUD 生命周期。"""

    with _running_automation_stub() as (stub, todo_service):
        created = MessageToDict(
            stub.CreateAutomation(
                _struct({
                    "user_id": "u1",
                    "text": "每日检查",
                    "prompt": "检查项目状态",
                    "next_run_at": "2026-08-15T09:30:00+08:00",
                    "timezone": "Asia/Shanghai",
                    "recurrence": {"frequency": "daily", "interval": 2},
                    "access_mode": "readonly",
                }),
                timeout=5,
            )
        )
        automation_id = str(created["id"])

        assert created["todoId"]
        assert created["userId"] == "u1"
        assert created["timezone"] == "Asia/Shanghai"
        assert created["recurrence"] == {"frequency": "daily", "interval": 2.0}
        assert created["accessMode"] == "readonly"

        listed = MessageToDict(stub.ListAutomations(_struct({"user_id": "u1"}), timeout=5))
        assert [item["id"] for item in listed["automations"]] == [automation_id]

        toggled = MessageToDict(
            stub.ToggleAutomation(
                _struct({"user_id": "u1", "automation_id": automation_id, "enabled": False}),
                timeout=5,
            )
        )
        assert toggled["enabled"] is False

        runs = MessageToDict(
            stub.ListAutomationRuns(
                _struct({"user_id": "u1", "automation_id": automation_id, "limit": 5}),
                timeout=5,
            )
        )
        assert runs == {"runs": []}

        deleted = MessageToDict(
            stub.DeleteAutomation(
                _struct({"user_id": "u1", "automation_id": automation_id}),
                timeout=5,
            )
        )
        assert deleted == {"deleted": True}
        assert todo_service.list_todos("u1") == []
        assert MessageToDict(stub.ListAutomations(_struct({"user_id": "u1"}), timeout=5)) == {
            "automations": []
        }


def test_automation_grpc_maps_rest_validation_and_not_found_errors() -> None:
    """非法请求和不存在的任务应映射为标准 gRPC 状态码。"""

    with _running_automation_stub() as (stub, _todo_service):
        with pytest.raises(grpc.RpcError) as missing_user:
            stub.ListAutomations(Struct(), timeout=5)
        assert missing_user.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as invalid_create:
            stub.CreateAutomation(
                _struct({"user_id": "u1", "text": "缺少执行内容"}),
                timeout=5,
            )
        assert invalid_create.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as invalid_recurrence:
            stub.CreateAutomation(
                _struct({
                    "user_id": "u1",
                    "text": "无效循环",
                    "prompt": "检查项目状态",
                    "next_run_at": "2026-08-15T09:30:00+08:00",
                    "recurrence": {"frequency": "daily", "interval": 0},
                }),
                timeout=5,
            )
        assert invalid_recurrence.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as invalid_toggle:
            stub.ToggleAutomation(
                _struct({
                    "user_id": "u1",
                    "automation_id": "automation_missing",
                    "enabled": "false",
                }),
                timeout=5,
            )
        assert invalid_toggle.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as missing_task:
            stub.DeleteAutomation(
                _struct({"user_id": "u1", "automation_id": "automation_missing"}),
                timeout=5,
            )
        assert missing_task.value.code() == grpc.StatusCode.NOT_FOUND

        with pytest.raises(grpc.RpcError) as invalid_limit:
            stub.ListAutomationRuns(
                _struct({"user_id": "u1", "automation_id": "automation_missing", "limit": 0}),
                timeout=5,
            )
        assert invalid_limit.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as fractional_limit:
            stub.ListAutomationRuns(
                _struct({"user_id": "u1", "automation_id": "automation_missing", "limit": 1.5}),
                timeout=5,
            )
        assert fractional_limit.value.code() == grpc.StatusCode.INVALID_ARGUMENT
