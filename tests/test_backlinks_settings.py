"""Backlinks visibility persistence and gRPC parity tests."""

from __future__ import annotations

import asyncio
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
from agent_service.api.rest import settings as settings_rest
from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings.service import SettingsService


class _MemoryServiceStub:
    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )


class _StubAgent:
    def close(self) -> None:
        pass


class _StubSessionService:
    pass


def _service() -> SettingsService:
    config = AgentConfig.load_config({}, load_env=False, ensure_directories=False, ensure_models=False)
    return SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]


def _struct(payload: dict[str, object]) -> Struct:
    return ParseDict(payload, Struct())


def test_show_backlinks_persists_in_user_profile() -> None:
    service = _service()

    service.save_appearance_config(user_id="u1", show_backlinks=True)

    assert service.ensure_user_profile(user_id="u1")["show_backlinks"] is True
    assert service.get_appearance_config(user_id="u1")["show_backlinks"] is True


def test_show_backlinks_rest_handler_uses_appearance_persistence(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(settings_rest, "_require_settings_service", lambda: service)

    saved = asyncio.run(settings_rest.save_appearance_config({
        "user_id": "u1",
        "show_backlinks": True,
    }))

    assert saved["show_backlinks"] is True
    assert service.ensure_user_profile(user_id="u1")["show_backlinks"] is True


def test_show_backlinks_has_rest_equivalent_grpc_contract() -> None:
    settings = _service()
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
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        stub = AgentServiceStub(channel)
        saved = MessageToDict(stub.SaveAppearanceConfig(_struct({
            "user_id": "u1",
            "show_backlinks": True,
        }), timeout=5))
        loaded = MessageToDict(stub.GetAppearanceConfig(_struct({"user_id": "u1"}), timeout=5))
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)

    assert saved["show_backlinks"] is True
    assert loaded["show_backlinks"] is True
