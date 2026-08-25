"""
LaTeX gRPC 与 REST 能力对齐测试。

使用说明:
启动真实 gRPC server，验证状态、编译和缓存 RPC 使用同一 LaTeX 服务字段。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct

from agent_service.api.grpc.agent_service_pb2_grpc import (
    AgentServiceStub,
    add_AgentServiceServicer_to_server,
)
from agent_service.api.grpc.servicer import AgentServiceServicer


class _AgentStub:
    """提供 StorageService 构造所需配置和关闭方法。"""

    def __init__(self, tmp_path: Any) -> None:
        self.config = SimpleNamespace(storage=SimpleNamespace(base_data_dir=tmp_path / "runtime"))

    def close(self) -> None:
        """测试无需释放资源。"""


class _LatexStub:
    """返回 gRPC 可断言的固定 LaTeX 数据。"""

    def get_status(self) -> dict[str, Any]:
        """返回系统编译器状态。"""

        return {"status": "ready", "source": "system", "compiler_path": "C:/tex/xelatex.exe"}

    def compile_file(self, **kwargs: Any) -> dict[str, Any]:
        """返回携带请求路径的编译结果。"""

        return {"success": True, "path": kwargs["path"], "preview": {"kind": "pdf"}}


def _struct(payload: dict[str, object]) -> Struct:
    """构造 protobuf Struct 请求。"""

    return ParseDict(payload, Struct())


def test_latex_grpc_status_and_compile_match_rest_shape(tmp_path: Any) -> None:
    """gRPC 状态和编译结果必须保持 REST 字段名称。"""

    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_AgentStub(tmp_path),  # type: ignore[arg-type]
            session_service=SimpleNamespace(),  # type: ignore[arg-type]
            latex_service=_LatexStub(),  # type: ignore[arg-type]
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        stub = AgentServiceStub(channel)
        status = MessageToDict(stub.GetLatexStatus(_struct({"user_id": "u1"}), timeout=5))
        compiled = MessageToDict(stub.CompileLatex(_struct({"user_id": "u1", "path": "paper.tex"}), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert status["source"] == "system"
    assert compiled["success"] is True
    assert compiled["path"] == "paper.tex"
    assert compiled["preview"]["kind"] == "pdf"
