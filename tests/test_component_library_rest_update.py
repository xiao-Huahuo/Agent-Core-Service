"""组件库源码更新 REST 参数转发测试。

使用说明：构造最小 FastAPI 应用，验证搜索侧栏保存源码调用正式组件服务。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from agent_service.api.rest.component_library import router as component_router
from agent_service.api.rest.deps import bind_application_services


class _ComponentServiceStub:
    """记录增量组件更新参数。"""

    def __init__(self) -> None:
        """初始化调用记录。"""

        self.call: dict[str, Any] = {}

    def update_component(self, **kwargs: Any) -> dict[str, object]:
        """返回更新后的最小组件响应。"""

        self.call = kwargs
        return {"component": {"component_id": kwargs["component_id"], "source": kwargs["source"]}}

    def create_component(self, **kwargs: Any) -> dict[str, object]:
        """Return one drawing script while retaining the forwarded request."""

        self.call = kwargs
        return {"component": {"component_id": "drawing scripts/chart.script", **kwargs}}


def _app(service: _ComponentServiceStub) -> FastAPI:
    """Bind one component stub through the production REST dependency."""

    app = FastAPI()
    app.state.services = SimpleNamespace(component_library_service=service)
    router = APIRouter(dependencies=[Depends(bind_application_services)])
    router.include_router(component_router)
    app.include_router(router)
    return app


def test_post_drawing_script_forwards_language_and_optional_cover() -> None:
    """REST creation must preserve drawing-script metadata at the service boundary."""

    service = _ComponentServiceStub()
    with TestClient(_app(service)) as client:
        response = client.post("/component-library/components", json={
            "user_id": "u1", "source": "plot(data)", "tag": "drawing scripts",
            "filename": "chart.script", "script_language": "R", "cover_asset_id": "asset-1",
        })

    assert response.status_code == 200
    assert service.call == {
        "user_id": "u1", "source": "plot(data)", "tag": "drawing scripts",
        "filename": "chart.script", "script_language": "R", "cover_asset_id": "asset-1",
    }


def test_patch_component_source_without_forcing_title_or_tag() -> None:
    """REST 源码保存不得把空标题或空标签传给领域服务。"""

    service = _ComponentServiceStub()
    with TestClient(_app(service)) as client:
        response = client.patch("/component-library/components", json={
            "user_id": "u1",
            "component_id": "cards/demo.vue",
            "source": "<template><article>new</article></template>",
        })

    assert response.status_code == 200
    assert service.call == {
        "user_id": "u1",
        "component_id": "cards/demo.vue",
        "title": None,
        "source": "<template><article>new</article></template>",
        "tag": None,
        "script_language": None,
        "cover_asset_id": None,
    }
