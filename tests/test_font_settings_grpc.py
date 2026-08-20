"""Independent font-size settings gRPC parity test."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from agent_service.api.grpc.agent_service_pb2_grpc import (
    AgentServiceStub,
    add_AgentServiceServicer_to_server,
)
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings_service import SettingsService


class _StubAgent:
    """Stand in for unrelated Agent methods."""

    def close(self) -> None:
        """Release no resources in this transport test."""


class _StubSessionService:
    """Stand in for unrelated session methods."""


class _MemoryServiceStub:
    """Provide a thread-safe in-memory SQLite database."""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )


def _struct(payload: dict[str, object]) -> Struct:
    """Convert a REST-shaped mapping to a protobuf Struct."""

    return ParseDict(payload, Struct())


def test_font_settings_grpc_persists_independent_sizes() -> None:
    """The gRPC panel contract must expose both font-size fields."""

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
        saved = MessageToDict(stub.SaveFontConfig(_struct({
            "user_id": "u1",
            "ui_font_size_percent": 90,
            "text_font_size_percent": 125,
        }), timeout=5))
        loaded = MessageToDict(stub.GetFontConfig(_struct({"user_id": "u1"}), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert saved["ui_font_size_percent"] == 90
    assert saved["text_font_size_percent"] == 125
    assert loaded["ui_font_size_percent"] == 90
    assert loaded["text_font_size_percent"] == 125
