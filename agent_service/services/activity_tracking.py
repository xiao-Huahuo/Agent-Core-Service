"""
Central HTTP mutation-to-activity classifier.

Usage:
The application middleware calls `classify_activity` only after a successful
response, then persists the returned privacy-safe event through ActivityService.
"""

from __future__ import annotations

from typing import Any


def should_inspect_activity_request(method: str, path: str) -> bool:
    """Limit JSON parsing to known activity routes, excluding passwords and prompts."""

    normalized_method = method.upper()
    normalized_path = path.rstrip("/") or "/"
    if normalized_method == "PATCH":
        return normalized_path.startswith("/library/items/") or normalized_path.startswith("/vault/items/")
    if normalized_method != "POST":
        return False
    return (
        normalized_path in {
            "/knowledge/files/file",
            "/knowledge/files/content",
            "/knowledge/files/folder",
            "/knowledge/files/copy",
            "/knowledge/files/rename",
            "/knowledge/files/ingest",
            "/knowledge/files/ingest-path",
            "/knowledge/rebuild",
            "/smart-forms/save",
            "/git/commit",
        }
        or normalized_path.endswith("/task-list/complete-item")
    )


def classify_activity(method: str, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
    """Map one meaningful successful mutation to its score, or ignore it."""

    normalized_method = method.upper()
    normalized_path = path.rstrip("/") or "/"
    if normalized_method == "DELETE":
        return None

    # Creates with durable model timestamps are backfilled by ActivityService;
    # request tracking is reserved for edits that would otherwise be overwritten.
    if normalized_method == "PATCH" and normalized_path.startswith("/library/items/"):
        return _event(
            "library",
            "metadata_updated",
            1,
            "完善图书馆项目",
            normalized_path.rsplit("/", 1)[-1],
            30,
        )
    if normalized_method == "POST" and normalized_path == "/knowledge/files/file":
        return _event("documents", "document_created", 2, "新建文档", str(body.get("path") or ""))
    if normalized_method == "POST" and normalized_path == "/knowledge/files/content":
        return _event("documents", "content_edited", 2, "编辑文档", str(body.get("path") or ""), 30)
    if normalized_method == "POST" and normalized_path in {
        "/knowledge/files/folder",
        "/knowledge/files/copy",
        "/knowledge/files/rename",
    }:
        object_id = str(body.get("target_path") or body.get("path") or "")
        return _event("documents", "file_organized", 1, "整理文件", object_id, 30)
    if normalized_method == "POST" and normalized_path in {
        "/knowledge/files/ingest",
        "/knowledge/files/ingest-path",
        "/knowledge/rebuild",
    }:
        return _event("knowledge", "knowledge_ingested", 1, "完成知识入库", str(body.get("path") or ""), 30)

    if normalized_method == "POST" and normalized_path.endswith("/task-list/complete-item"):
        return _event("tasks", "task_completed", 3, "完成任务", str(body.get("item_id") or ""))

    if normalized_method == "POST" and normalized_path == "/smart-forms/save":
        return _event("other", "smart_form_saved", 2, "保存智能表格", str(body.get("form_id") or ""), 30)
    if normalized_method == "PATCH" and normalized_path.startswith("/vault/items/"):
        if normalized_path in {"/vault/items/trash", "/vault/items/restore", "/vault/items/purge"}:
            return None
        object_id = normalized_path.removeprefix("/vault/items/")
        return _event("other", "vault_item_changed", 1, "更新密码库条目", object_id, 30)
    if normalized_method == "POST" and normalized_path == "/git/commit":
        return _event("other", "backup_completed", 1, "提交知识库版本")
    if normalized_method == "POST" and normalized_path == "/vault/export":
        return _event("other", "backup_completed", 1, "导出密码库备份")
    return None


def _event(
    module: str,
    action: str,
    score: int,
    title: str,
    object_id: str = "",
    dedupe_minutes: int = 0,
) -> dict[str, Any]:
    """Build the stable event contract consumed by the middleware."""

    return {
        "module": module,
        "action": action,
        "score": score,
        "object_id": object_id,
        "title": title,
        "dedupe_minutes": dedupe_minutes,
    }
