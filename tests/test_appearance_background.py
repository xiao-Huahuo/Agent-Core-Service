"""Appearance background persistence, migration, REST, and gRPC parity tests."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from agent_service.api.grpc.agent_service_pb2_grpc import AgentServiceStub, add_AgentServiceServicer_to_server
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.api.rest import settings as settings_rest
from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings_service import SettingsService


class _MemoryServiceStub:
    """Provide one shared in-memory engine for SettingsService tests."""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )


class _StubAgent:
    """Minimal AgentServiceServicer dependency."""

    def close(self) -> None:
        """Match the runtime shutdown contract."""


class _StubSessionService:
    """Minimal session dependency for appearance RPC tests."""


def _service() -> SettingsService:
    """Create an isolated settings service with schema migration enabled."""

    config = AgentConfig.load_config({}, load_env=False, ensure_directories=False, ensure_models=False)
    return SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]


def _struct(payload: dict[str, object]) -> Struct:
    """Convert a dict into the generic settings RPC payload."""

    return ParseDict(payload, Struct())


def test_background_cover_column_and_profile_persistence() -> None:
    """Persist an uploaded asset URL and clear it through the same setting."""

    service = _service()
    assert "background_cover_url" in {column["name"] for column in inspect(service.engine).get_columns("user_settings")}

    saved = service.save_appearance_config(
        user_id="u1",
        background_cover_url="/library/assets/u1/cover.png",
    )
    assert saved["background_cover_url"] == "/library/assets/u1/cover.png"
    assert service.ensure_user_profile(user_id="u1")["background_cover_url"] == saved["background_cover_url"]

    reset = service.save_appearance_config(user_id="u1", background_cover_url="")
    assert reset["background_cover_url"] == ""


def test_background_cover_rest_and_grpc_contracts() -> None:
    """Keep REST and generic Struct RPC responses equivalent."""

    service = _service()
    original_dependency = settings_rest._require_settings_service
    settings_rest._require_settings_service = lambda: service
    try:
        rest_saved = asyncio.run(settings_rest.save_appearance_config({
            "user_id": "u1",
            "background_cover_url": "/library/assets/u1/rest.png",
        }))
    finally:
        settings_rest._require_settings_service = original_dependency
    assert rest_saved["background_cover_url"] == "/library/assets/u1/rest.png"

    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_StubAgent(),  # type: ignore[arg-type]
            session_service=_StubSessionService(),  # type: ignore[arg-type]
            settings_service=service,
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        stub = AgentServiceStub(channel)
        saved = MessageToDict(stub.SaveAppearanceConfig(_struct({
            "user_id": "u1",
            "background_cover_url": "/library/assets/u1/grpc.png",
        }), timeout=5))
        loaded = MessageToDict(stub.GetAppearanceConfig(_struct({"user_id": "u1"}), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert saved["background_cover_url"] == "/library/assets/u1/grpc.png"
    assert loaded["background_cover_url"] == saved["background_cover_url"]
