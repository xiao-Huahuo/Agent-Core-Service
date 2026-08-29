"""
Component library gRPC transport integration test.

Usage:
Starts a temporary local gRPC server and verifies list/upload semantics match
the REST component-library endpoints. The context manager closes its port.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

import grpc
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from agent_service.api.grpc.agent_service_pb2_grpc import (
    AgentServiceStub,
    add_AgentServiceServicer_to_server,
)
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.services.component_library.service import ComponentLibraryService


class _StubAgent:
    """Provide the minimal close method required by the shared servicer."""

    def close(self) -> None:
        """Release no resources in this isolated transport test."""


class _StubSessionService:
    """Stand in for session APIs that this transport test never calls."""


class _StubSettingsService:
    """Resolve the temporary active knowledge directory used by gRPC."""

    def __init__(self, root) -> None:
        """Retain the isolated root supplied by pytest."""

        self.root = root

    def ensure_user_profile(self, *, user_id: str) -> dict[str, object]:
        """Return the active-library profile shape consumed by the service."""

        return {
            "user_id": user_id,
            "active_knowledge_library": {"library_id": "grpc-test", "knowledge_dir": str(self.root)},
        }


def _struct(payload: dict[str, object]) -> Struct:
    """Convert a REST-shaped dictionary to one protobuf Struct request."""

    return ParseDict(payload, Struct())


@contextmanager
def _running_component_stub(tmp_path: Path) -> Iterator[AgentServiceStub]:
    """Start and fully close an isolated component-library gRPC endpoint."""

    service = ComponentLibraryService(settings_service=_StubSettingsService(tmp_path))
    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    add_AgentServiceServicer_to_server(
        AgentServiceServicer(
            agent=_StubAgent(),  # type: ignore[arg-type]
            session_service=_StubSessionService(),  # type: ignore[arg-type]
            component_library_service=service,
        ),
        server,
    )
    port = server.add_insecure_port("127.0.0.1:0")
    assert port > 0
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        grpc.channel_ready_future(channel).result(timeout=5)
        yield AgentServiceStub(channel)
    finally:
        channel.close()
        server.stop(0).wait(timeout=5)


def test_component_library_grpc_upload_and_list_match_rest_fields(tmp_path: Path) -> None:
    """The two component RPCs should preserve single-tag source records."""

    with _running_component_stub(tmp_path) as stub:
        created = MessageToDict(
            stub.CreateComponentLibraryComponent(
                _struct({
                    "user_id": "u1",
                    "source": "<template><button>OK</button></template>",
                    "tag": "buttons",
                    "filename": "grpc-button.vue",
                }),
                timeout=5,
            )
        )["component"]
        renamed = MessageToDict(
            stub.RenameComponentLibraryComponent(
                _struct({
                    "user_id": "u1",
                    "component_id": created["component_id"],
                    "title": "renamed-button",
                }),
                timeout=5,
            )
        )["component"]
        updated = MessageToDict(
            stub.RenameComponentLibraryComponent(
                _struct({
                    "user_id": "u1",
                    "component_id": renamed["component_id"],
                    "source": "<template><button>UPDATED</button></template>",
                }),
                timeout=5,
            )
        )["component"]
        listed = MessageToDict(
            stub.ListComponentLibraryComponents(
                _struct({"user_id": "u1", "tag": "buttons"}),
                timeout=5,
            )
        )
        deleted = MessageToDict(
            stub.DeleteComponentLibraryComponent(
                _struct({"user_id": "u1", "component_id": renamed["component_id"]}),
                timeout=5,
            )
        )
        listed_after_delete = MessageToDict(
            stub.ListComponentLibraryComponents(
                _struct({"user_id": "u1", "tag": "buttons"}),
                timeout=5,
            )
        )

        assert created["tag"] == "buttons"
        assert renamed["component_id"] == "buttons/renamed-button.vue"
        assert updated["source"] == "<template><button>UPDATED</button></template>"
        assert listed["components"] == [updated]
        assert deleted == {"component_id": renamed["component_id"], "deleted": True}
        assert listed_after_delete.get("components", []) == []
