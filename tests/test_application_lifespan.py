"""拆分后应用生命周期的启动与清理顺序测试。

测试使用轻量替身，不创建真实模型、数据库、线程、gRPC server 或网络端口。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI

import agent_service.core.lifespan as lifespan_module


class FakeServices:
    """记录后台服务启动和关闭的应用容器替身。"""

    def __init__(self, events: list[str]) -> None:
        """保存共享事件列表。"""

        self.events = events

    def start_background_services(self) -> None:
        """记录后台组件启动。"""

        self.events.append("services.start")

    def shutdown_background_services(self) -> None:
        """记录后台组件关闭。"""

        self.events.append("services.stop")


class FakeGrpcRuntime:
    """记录 gRPC 启动和关闭的运行时替身。"""

    def __init__(self, events: list[str]) -> None:
        """保存共享事件列表并初始化运行状态。"""

        self.events = events
        self.running = False

    def start(self, _services: Any) -> None:
        """记录启动并设置运行状态。"""

        self.events.append("grpc.start")
        self.running = True

    def stop(self) -> None:
        """记录关闭并清除运行状态。"""

        self.events.append("grpc.stop")
        self.running = False


def _install_fakes(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    """把 lifespan 的外部装配点替换为不产生资源的测试对象。"""

    config = SimpleNamespace()
    services = FakeServices(events)
    monkeypatch.setattr(lifespan_module, "load_startup_config", lambda: config)
    monkeypatch.setattr(lifespan_module, "create_database_engine", lambda _config: object())
    monkeypatch.setattr(lifespan_module, "upgrade_database", lambda **_kwargs: events.append("database.upgrade"))
    monkeypatch.setattr(
        lifespan_module,
        "create_application_services",
        lambda _config, database_engine: services,
    )
    monkeypatch.setattr(lifespan_module, "GrpcRuntime", lambda: FakeGrpcRuntime(events))

def test_lifespan_starts_and_stops_resources_in_stable_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常生命周期必须先完成服务启动，且启动阶段不得验证或加载任何模型。"""

    events: list[str] = []
    _install_fakes(monkeypatch, events)
    app = FastAPI()

    async def run_lifespan() -> None:
        """进入生命周期并验证容器在运行期间可见。"""

        async with lifespan_module.agent_service_lifespan(app):
            events.append("yield")
            assert app.state.services is not None
            assert app.state.grpc_runtime.running is True

    asyncio.run(run_lifespan())

    assert events == [
        "database.upgrade",
        "services.start",
        "grpc.start",
        "yield",
        "services.stop",
        "grpc.stop",
    ]
    assert app.state.services is None
    assert app.state.grpc_runtime is None
