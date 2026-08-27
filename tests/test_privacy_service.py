"""Privacy service persistence tests.

Usage:
Run with pytest to verify that privacy flags are user/library scoped, idempotent,
and limited to knowledge files and library items.
"""

from __future__ import annotations

import pytest
from sqlmodel import create_engine

from agent_service.schemas.privacy import PrivacyCreate
from agent_service.services.privacy_service import PrivacyService


def test_privacy_service_persists_scoped_flags(tmp_path) -> None:
    """A privacy flag remains isolated by user, library, type, and target ID."""

    service = PrivacyService(engine=create_engine(f"sqlite:///{tmp_path / 'privacy.db'}"))
    payload = PrivacyCreate(
        user_id="user-1",
        library_id="library-1",
        target_type="knowledge_path",
        target_id="docs/private.pdf",
    )

    first = service.add_privacy(payload)
    duplicate = service.add_privacy(payload)

    assert duplicate.privacy_id == first.privacy_id
    assert [item.target_id for item in service.list_privacy(user_id="user-1", library_id="library-1")] == [
        "docs/private.pdf",
    ]
    assert service.list_privacy(user_id="user-1", library_id="library-2") == []
    assert service.delete_privacy(
        user_id="user-1",
        library_id="library-1",
        target_type="knowledge_path",
        target_id="docs/private.pdf",
    ) is True
    assert service.list_privacy(user_id="user-1", library_id="library-1") == []


def test_privacy_service_rejects_unsupported_target_types(tmp_path) -> None:
    """Privacy cannot be applied to component or Agent-session targets."""

    service = PrivacyService(engine=create_engine(f"sqlite:///{tmp_path / 'privacy.db'}"))

    with pytest.raises(ValueError, match="smart_form_row"):
        service.add_privacy(
            PrivacyCreate.model_construct(
                user_id="user-1",
                library_id="library-1",
                target_type="session",
                target_id="session-1",
            )
        )
