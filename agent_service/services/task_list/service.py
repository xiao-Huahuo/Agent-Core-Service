"""
Session task list service.

The task list is an Agent-owned long-running execution state. It is scoped to a
single session and stored inside SessionRecord.state_json through SessionService.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS

if TYPE_CHECKING:
    from agent_service.services.session.service import SessionService


TASK_LIST_STATE_KEY = "task_list"
PLAN_STATE_KEY = "plan"
MODERN_STATE_KEYS = {
    PLAN_STATE_KEY,
    TASK_LIST_STATE_KEY,
    "child_agents",
    "change_snapshot",
    "compression_state",
    "environment",
}


def utc_iso() -> str:
    """Return an ISO formatted UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def normalize_session_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize old and new session state shapes.

    Older sessions persisted the planner state directly. New state stores
    {"plan": ..., "task_list": ...}.
    """

    if not isinstance(raw, dict):
        return {}
    if MODERN_STATE_KEYS.intersection(raw):
        return copy.deepcopy(raw)
    return {PLAN_STATE_KEY: copy.deepcopy(raw)}


def extract_plan_state(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract planner state from a normalized or legacy session state."""

    state = normalize_session_state(raw)
    plan = state.get(PLAN_STATE_KEY)
    return copy.deepcopy(plan) if isinstance(plan, dict) else None


def merge_plan_state(raw: dict[str, Any] | None, plan: dict[str, Any] | None) -> dict[str, Any] | None:
    """Merge planner state while preserving the task list."""

    state = normalize_session_state(raw)
    if plan is None:
        state.pop(PLAN_STATE_KEY, None)
    else:
        state[PLAN_STATE_KEY] = copy.deepcopy(plan)
    return state or None


class TaskListService:
    """Manage the active task list for one Agent session."""

    def __init__(self, *, session_service: SessionService) -> None:
        self.session_service = session_service

    def get_task_list(self, session_id: str) -> dict[str, Any] | None:
        """Return the session task list, if present."""

        state = self._load_state(session_id)
        task_list = state.get(TASK_LIST_STATE_KEY)
        return copy.deepcopy(task_list) if isinstance(task_list, dict) else None

    def create_task_list(
        self,
        *,
        session_id: str,
        title: str,
        items: list[str],
        current_item_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or replace the session task list."""

        cleaned_items = [item.strip() for item in items if str(item).strip()]
        if not cleaned_items:
            raise ValueError("items must contain at least one non-empty task")
        now = utc_iso()
        task_items = [
            {
                "id": f"task_item_{uuid4().hex[:DEFAULT_BUSINESS_LIMITS.generated_id_suffix_chars]}",
                "title": item,
                "status": "pending",
                "completion_summary": "",
                "completed_at": None,
            }
            for item in cleaned_items
        ]
        selected_id = current_item_id if current_item_id in {item["id"] for item in task_items} else task_items[0]["id"]
        for item in task_items:
            if item["id"] == selected_id:
                item["status"] = "in_progress"
                break
        task_list = {
            "task_list_id": f"task_list_{uuid4().hex[:DEFAULT_BUSINESS_LIMITS.generated_id_suffix_chars]}",
            "session_id": session_id,
            "title": title.strip() or "Task list",
            "status": "active",
            "current_item_id": selected_id,
            "items": task_items,
            "final_summary": "",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        self._save_task_list(session_id, task_list)
        return copy.deepcopy(task_list)

    def complete_task_list_item(
        self,
        *,
        session_id: str,
        item_id: str,
        completion_summary: str,
        next_item_id: str | None = None,
    ) -> dict[str, Any]:
        """Mark one item complete and optionally select the next current item."""

        task_list = self.get_task_list(session_id)
        if task_list is None:
            raise ValueError("no task list exists for this session")
        if task_list.get("status") != "active":
            raise ValueError("task list is already completed")
        items = task_list.get("items")
        if not isinstance(items, list):
            raise ValueError("task list is malformed")
        target = self._find_item(items, item_id)
        if target is None:
            raise ValueError(f"task list item not found: {item_id}")
        summary = completion_summary.strip()
        if not summary:
            raise ValueError("completion_summary is required")
        now = utc_iso()
        target["status"] = "completed"
        target["completion_summary"] = summary
        target["completed_at"] = now

        pending_items = [item for item in items if item.get("status") != "completed"]
        selected = self._find_item(items, next_item_id or "") if next_item_id else None
        if selected is None or selected.get("status") == "completed":
            selected = pending_items[0] if pending_items else None
        for item in pending_items:
            item["status"] = "pending"
        if selected is not None:
            selected["status"] = "in_progress"
            task_list["current_item_id"] = selected.get("id")
        else:
            task_list["current_item_id"] = None
        task_list["updated_at"] = now
        self._save_task_list(session_id, task_list)
        return copy.deepcopy(task_list)

    def finish_task_list(self, *, session_id: str, final_summary: str = "") -> dict[str, Any]:
        """Mark the task list completed."""

        task_list = self.get_task_list(session_id)
        if task_list is None:
            raise ValueError("no task list exists for this session")
        now = utc_iso()
        task_list["status"] = "completed"
        task_list["current_item_id"] = None
        task_list["final_summary"] = final_summary.strip()
        task_list["updated_at"] = now
        task_list["completed_at"] = now
        self._save_task_list(session_id, task_list)
        return copy.deepcopy(task_list)

    def _load_state(self, session_id: str) -> dict[str, Any]:
        import json

        state_json = self.session_service.get_session_state(session_id)
        if not state_json:
            return {}
        try:
            parsed = json.loads(state_json)
        except (json.JSONDecodeError, TypeError):
            return {}
        return normalize_session_state(parsed)

    def _save_task_list(self, session_id: str, task_list: dict[str, Any]) -> None:
        import json

        state = self._load_state(session_id)
        state[TASK_LIST_STATE_KEY] = copy.deepcopy(task_list)
        self.session_service.update_session_state(session_id, json.dumps(state, ensure_ascii=False))

    @staticmethod
    def _find_item(items: list[Any], item_id: str) -> dict[str, Any] | None:
        for item in items:
            if isinstance(item, dict) and item.get("id") == item_id:
                return item
        return None
