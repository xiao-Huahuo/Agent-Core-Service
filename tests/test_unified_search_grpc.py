"""四库联合搜索 gRPC 与 REST 等价参数测试。

使用说明：直接调用领域 handler 并检查生成后的 protobuf descriptor，不启动端口。
"""

from __future__ import annotations

from typing import Any

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct

from agent_service.api.grpc.agent_service_pb2 import DESCRIPTOR
from agent_service.api.grpc.handlers.knowledge import KnowledgeGrpcHandlerMixin


class _SearchStub:
    """记录 gRPC handler 传入领域用例的参数。"""

    def __init__(self) -> None:
        """初始化调用记录。"""

        self.call: dict[str, Any] = {}

    def search(self, **kwargs: Any) -> dict[str, Any]:
        """保存请求并返回可转换为 Struct 的响应。"""

        self.call = kwargs
        return {
            "query": kwargs["query"],
            "selected_sources": sorted(kwargs["sources"]),
            "fulltext": kwargs["fulltext"],
            "semantic": kwargs["semantic"],
            "results": [],
            "groups": {"files": [], "library": [], "components": [], "literature": []},
            "counts": {"files": 0, "library": 0, "components": 0, "literature": 0},
            "total": 0,
        }


class _Handler(KnowledgeGrpcHandlerMixin):
    """只注入联合搜索依赖的知识领域 handler。"""

    def __init__(self, service: _SearchStub) -> None:
        """保存测试服务。"""

        self.service = service

    def _require_unified_search_service(self, _: object) -> _SearchStub:
        """返回测试联合搜索服务。"""

        return self.service


def test_grpc_forwards_selected_sources_and_capability_flags() -> None:
    """gRPC 必须与 REST 一样保持用户来源和全文、语义开关。"""

    service = _SearchStub()
    request = ParseDict(
        {
            "user_id": "u1",
            "query": "视觉组件",
            "sources": ["components", "library"],
            "fulltext": False,
            "semantic": True,
        },
        Struct(),
    )

    response = _Handler(service).SearchAllLibraries(request, object())

    assert service.call == {
        "user_id": "u1",
        "query": "视觉组件",
        "sources": {"components", "library"},
        "fulltext": False,
        "semantic": True,
    }
    assert MessageToDict(response)["selected_sources"] == ["components", "library"]
    service_descriptor = DESCRIPTOR.services_by_name["AgentService"]
    assert "SearchAllLibraries" in service_descriptor.methods_by_name
