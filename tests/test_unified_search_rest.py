"""四库联合搜索 REST 请求构造与来源门控测试。

使用说明：本文件只启动最小 FastAPI 应用，不加载模型或完整服务。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest.deps import bind_application_services
from agent_service.api.rest.unified_search import router as unified_search_router


class _UnifiedSearchStub:
    """记录 REST 层传入领域服务的完整查询。"""

    def __init__(self) -> None:
        """初始化调用记录。"""

        self.call: dict[str, Any] = {}

    def search(self, **kwargs: Any) -> dict[str, Any]:
        """保存请求并返回最小合法搜索响应。"""

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


def test_rest_forwards_only_user_selected_sources_and_search_capabilities() -> None:
    """REST 不得擅自补回未选中的库或改变全文、语义开关。"""

    service = _UnifiedSearchStub()
    app = FastAPI()
    app.state.services = SimpleNamespace(unified_search_service=service)
    router = APIRouter(dependencies=[Depends(bind_application_services)])
    router.include_router(unified_search_router)
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get(
            "/search",
            params={
                "user_id": "u1",
                "query": "向量数据库",
                "sources": "library,literature",
                "fulltext": "false",
                "semantic": "true",
            },
        )

    assert response.status_code == 200
    assert service.call == {
        "user_id": "u1",
        "query": "向量数据库",
        "sources": {"library", "literature"},
        "fulltext": False,
        "semantic": True,
    }
