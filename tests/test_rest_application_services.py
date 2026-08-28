"""REST ApplicationServices 请求隔离测试。

验证 FastAPI Depends 从 ``app.state.services`` 绑定容器，两个应用实例不会共享
Service，并且未初始化应用返回 503。
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest.deps import _require_activity_service, bind_application_services


def _build_app(marker: str | None) -> FastAPI:
    """创建带可选测试容器的最小 FastAPI 应用。"""

    app = FastAPI()
    if marker is not None:
        app.state.services = SimpleNamespace(activity_service=SimpleNamespace(marker=marker))
    router = APIRouter(dependencies=[Depends(bind_application_services)])

    @router.get("/marker")
    def marker_endpoint() -> dict[str, str]:
        """返回当前请求绑定的 ActivityService 测试标识。"""

        return {"marker": _require_activity_service().marker}

    app.include_router(router)
    return app


def test_application_services_are_isolated_per_fastapi_app() -> None:
    """两个应用必须各自读取自己的 app.state 容器。"""

    with TestClient(_build_app("first")) as first, TestClient(_build_app("second")) as second:
        assert first.get("/marker").json() == {"marker": "first"}
        assert second.get("/marker").json() == {"marker": "second"}
        assert first.get("/marker").json() == {"marker": "first"}


def test_uninitialized_application_services_return_503() -> None:
    """没有 app.state.services 的应用不得伪装成初始化成功。"""

    with TestClient(_build_app(None)) as client:
        response = client.get("/marker")
    assert response.status_code == 503
    assert response.json()["detail"] == "Application services not initialized yet"
