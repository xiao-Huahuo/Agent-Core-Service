"""Embedded-browser settings gRPC parity test."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from tests.db_test_utils import create_test_engine as create_engine
from sqlalchemy.pool import StaticPool

from agent_service.api.grpc.agent_service_pb2_grpc import (
    AgentServiceStub,
    add_AgentServiceServicer_to_server,
)
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings.service import SettingsService


class _StubAgent:
    def close(self) -> None:
        """Release no resources in this transport test."""


class _StubSessionService:
    """Stand in for unrelated session methods."""


class _MemoryServiceStub:
    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )


def _struct(payload: dict[str, object]) -> Struct:
    return ParseDict(payload, Struct())


def test_browser_settings_grpc_matches_rest_shaped_fields() -> None:
    config = AgentConfig.load_config({}, load_env=False, ensure_directories=False, ensure_models=False)
    settings = SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]
    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_StubAgent(),  # type: ignore[arg-type]
            session_service=_StubSessionService(),  # type: ignore[arg-type]
            settings_service=settings,
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    assert port > 0
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        stub = AgentServiceStub(channel)
        saved = MessageToDict(stub.SaveWebSearchConfig(_struct({
            "user_id": "u1",
            "proxy_url": "http://127.0.0.1:7890",
            "browser_proxy_url": "socks5://127.0.0.1:1080",
            "browser_home_url": "https://example.com/start",
        }), timeout=5))
        loaded = MessageToDict(stub.GetWebSearchConfig(_struct({"user_id": "u1"}), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert saved["browser_proxy_url"] == "socks5://127.0.0.1:1080"
    assert loaded["proxy_url"] == "http://127.0.0.1:7890"
    assert loaded["browser_home_url"] == "https://example.com/start"
