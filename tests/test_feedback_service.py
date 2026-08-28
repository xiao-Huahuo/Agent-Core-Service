"""
用户反馈服务测试。

功能说明:
验证反馈接口既能按用户读取,也能在用户态暂不可用时读取全部反馈。

使用说明:
在项目根目录执行 `python -m pytest tests/test_feedback_service.py`。
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from tests.db_test_utils import create_test_engine as create_engine

import agent_service.api.rest.deps as rest_deps
from agent_service.api.rest.feedback import router as feedback_router
from agent_service.services.feedback.service import FeedbackService
from agent_service.schemas.feedback import FeedbackCreate
from main import app as main_app


def make_client() -> TestClient:
    """创建共享内存 SQLite 的反馈接口测试客户端。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = FastAPI()
    app.state.services = SimpleNamespace(feedback_service=FeedbackService(engine=engine))
    app.include_router(
        feedback_router,
        dependencies=[Depends(rest_deps.bind_application_services)],
    )
    return TestClient(app)


def test_list_feedback_reads_all_when_user_id_is_missing() -> None:
    """不传 user_id 时应返回全部反馈,避免反馈面板因用户态未同步而空读。"""

    client = make_client()
    try:
        client.post("/feedback", json={"user_id": "u1", "content": "first"}).raise_for_status()
        client.post("/feedback", json={"user_id": "u2", "content": "second"}).raise_for_status()

        scoped = client.get("/feedback", params={"user_id": "u1"})
        unscoped = client.get("/feedback")

        assert scoped.status_code == 200
        assert [item["content"] for item in scoped.json()["feedback"]] == ["first"]
        assert unscoped.status_code == 200
        assert {item["content"] for item in unscoped.json()["feedback"]} == {"first", "second"}
    finally:
        client.close()


def test_feedback_allows_electron_renderer_cors_preflight() -> None:
    """Electron 开发渲染页直连后端时应通过本地 CORS 预检。"""

    client = TestClient(main_app)
    response = client.options(
        "/feedback",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_feedback_allows_file_origin_private_network_preflight() -> None:
    """Electron 打包文件页直连本机后端时应通过 null origin 预检。"""

    client = TestClient(main_app)
    response = client.options(
        "/feedback",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "null"
    assert response.headers["access-control-allow-private-network"] == "true"


def test_feedback_get_enforces_optional_user_ownership() -> None:
    """Agent 单条反馈读取不得跨用户返回同一 feedback_id。"""

    engine = create_engine("sqlite:///:memory:")
    service = FeedbackService(engine=engine)
    created = service.add_feedback(FeedbackCreate(user_id="u1", content="only mine"))

    assert service.get_feedback(feedback_id=created.feedback_id, user_id="u1") == created
    assert service.get_feedback(feedback_id=created.feedback_id, user_id="u2") is None
