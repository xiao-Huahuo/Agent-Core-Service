"""
HTTP activity classification tests.

Usage:
Protects the centralized mutation tracker from counting destructive or passive
requests and verifies that meaningful operations map to the agreed modules.
"""

from agent_service.services.activity_tracking import classify_activity, should_inspect_activity_request


def test_document_edit_is_scored_and_deduplicated_by_path() -> None:
    """A successful content save should become one mergeable document edit event."""

    event = classify_activity(
        method="POST",
        path="/knowledge/files/content",
        body={"user_id": "u1", "path": "notes/research.md", "content": "changed"},
    )

    assert event == {
        "module": "documents",
        "action": "content_edited",
        "score": 2,
        "object_id": "notes/research.md",
        "title": "编辑文档",
        "dedupe_minutes": 30,
    }


def test_filters_cover_distinct_modules_without_counting_deletion() -> None:
    """Library, task, form, and vault writes should map independently; deletes score zero."""

    assert classify_activity("PATCH", "/library/items/book-1", {})["module"] == "library"
    assert classify_activity("POST", "/sessions/session-1/task-list/complete-item", {"item_id": "item-1"})["action"] == "task_completed"
    assert classify_activity("POST", "/smart-forms/save", {"form_id": "form-1"})["module"] == "other"
    assert classify_activity("PATCH", "/vault/items/vault-1", {}) == {
        "module": "other",
        "action": "vault_item_changed",
        "score": 1,
        "object_id": "vault-1",
        "title": "更新密码库条目",
        "dedupe_minutes": 30,
    }
    assert classify_activity("DELETE", "/library/items/book-1", {}) is None
    assert classify_activity("POST", "/vault/unlock", {}) is None
    assert should_inspect_activity_request("POST", "/vault/unlock") is False
    assert should_inspect_activity_request("POST", "/agent/stream") is False
    assert should_inspect_activity_request("PATCH", "/vault/items/vault-1") is True
