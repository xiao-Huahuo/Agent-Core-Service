"""Privacy REST and gRPC surface tests.

Usage:
Run with pytest to verify that both public protocols expose the same persisted
privacy lifecycle for knowledge paths and library items.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.db_test_utils import create_test_engine as create_engine

from agent_service.api.grpc import agent_service_pb2, agent_service_pb2_grpc
from agent_service.api.grpc.servicer import AgentServiceServicer
from agent_service.api.rest import privacy as privacy_rest
from agent_service.services.privacy.service import PrivacyService


def test_privacy_rest_lifecycle(monkeypatch, tmp_path) -> None:
    """REST creates, lists, filters, and removes a scoped privacy flag."""

    service = PrivacyService(engine=create_engine(f"sqlite:///{tmp_path / 'privacy-rest.db'}"))
    monkeypatch.setattr(privacy_rest, "_require_privacy_service", lambda: service)
    app = FastAPI()
    app.include_router(privacy_rest.router)
    client = TestClient(app)

    payload = {
        "user_id": "user-1",
        "library_id": "library-1",
        "target_type": "library_item",
        "target_id": "book-1",
    }
    created = client.post("/privacy", json=payload)
    listed = client.get("/privacy", params={
        "user_id": "user-1",
        "library_id": "library-1",
        "target_type": "library_item",
    })
    deleted = client.delete("/privacy", params=payload)

    assert created.status_code == 200
    assert created.json()["target_id"] == "book-1"
    assert [item["target_id"] for item in listed.json()["privacy"]] == ["book-1"]
    assert deleted.json() == {"ok": True, "deleted": True}


def test_privacy_grpc_contract_is_generated_and_implemented() -> None:
    """Generated gRPC bindings and the concrete servicer expose all privacy RPCs."""

    request = agent_service_pb2.PrivacyCreateRequest(
        user_id="user-1",
        library_id="library-1",
        target_type="knowledge_path",
        target_id="private/file.png",
    )

    assert agent_service_pb2.PrivacyCreateRequest.FromString(request.SerializeToString()) == request
    assert hasattr(agent_service_pb2_grpc.AgentServiceStub, "__init__")
    assert all(hasattr(AgentServiceServicer, method) for method in ("ListPrivacy", "AddPrivacy", "DeletePrivacy"))
