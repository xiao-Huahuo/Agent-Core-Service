"""tasks 类内置工具实现。

函数体由原 builtin.py 机械迁移，工具行为不变。
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from agent_service.tools.runtime_context import (
    AGENT_ACCESS_READONLY,
    get_markdown_html_visualization_callback,
    get_task_list_callback,
    get_tool_runtime,
    register_network_citation,
    register_tool_citation,
)
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.todo.service import TodoService
from agent_service.services.automation.service import AutomationService
from agent_service.tools.builtin.builtin import (
    BuiltinToolDefinition, _deny_readonly_write, _is_readonly_access,
    _safe_visualization_filename, _strip_markdown_html_fence,
)

def _get_task_list_service():
    """Return the current task list service."""

    runtime = get_tool_runtime()
    if runtime.task_list_service is not None:
        return runtime.task_list_service
    try:
        from agent_service.api.rest.deps import _task_list_service
        if _task_list_service is not None:
            return _task_list_service
    except Exception:
        pass
    raise RuntimeError("TaskListService is not initialized.")
def _emit_task_list_update(task_list: dict[str, Any] | None) -> None:
    """Notify the current Agent stream that task list state changed."""

    callback = get_task_list_callback()
    if callback is not None:
        callback(task_list)
def get_task_list_status() -> str:
    """
    Read the current session task list without changing its state.

    Use this when the Agent needs to confirm item ids, current progress, or
    completion summaries before continuing a long-running task list.
    """

    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.get_task_list(runtime.session_id)
    if task_list is None:
        return "No task list exists for this session."
    items = task_list.get("items", [])
    completed_count = len([item for item in items if isinstance(item, dict) and item.get("status") == "completed"])
    lines = [
        f"Task list: {task_list.get('title') or 'Task list'}",
        f"Status: {task_list.get('status') or 'active'}",
        f"Current item id: {task_list.get('current_item_id') or 'none'}",
        f"Progress: {completed_count}/{len(items) if isinstance(items, list) else 0}",
    ]
    if isinstance(items, list) and items:
        lines.append("Items:")
        for item in items:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('id')}: [{item.get('status') or 'pending'}] {item.get('title') or ''}"
            )
            summary = str(item.get("completion_summary") or "").strip()
            if summary:
                lines.append(f"  completion_summary: {summary}")
    final_summary = str(task_list.get("final_summary") or "").strip()
    if final_summary:
        lines.append(f"Final summary: {final_summary}")
    return "\n".join(lines)
def create_task_list(title: str = "", items: list[Any] | str | None = None) -> str:
    """
    Create a session-scoped task list for complex long-running work.

    title: short task list title.
    items: ordered task titles, or a newline-separated string.
    """

    if isinstance(items, str):
        parsed_items = [line.strip("- 	") for line in items.splitlines() if line.strip("- \t")]
    elif isinstance(items, list):
        parsed_items = [str(item).strip() for item in items if str(item).strip()]
    else:
        parsed_items = []
    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.create_task_list(
        session_id=runtime.session_id,
        title=title,
        items=parsed_items,
    )
    _emit_task_list_update(task_list)
    current = next((item for item in task_list["items"] if item.get("id") == task_list.get("current_item_id")), None)
    current_title = current.get("title") if current else "none"
    return f"Task list created with {len(task_list['items'])} items. Current item: {current_title}"
def complete_task_list_item(item_id: str, completion_summary: str, next_item_id: str | None = None) -> str:
    """
    Mark a task list item complete and record the completion summary.

    item_id: task list item id.
    completion_summary: concrete summary of what was completed.
    next_item_id: optional next item to make current.
    """

    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.complete_task_list_item(
        session_id=runtime.session_id,
        item_id=item_id,
        completion_summary=completion_summary,
        next_item_id=next_item_id,
    )
    _emit_task_list_update(task_list)
    remaining = len([item for item in task_list.get("items", []) if item.get("status") != "completed"])
    return f"Task list item completed. Remaining items: {remaining}"
def finish_task_list(final_summary: str = "") -> str:
    """
    Finish the active session task list after all useful work is complete.

    final_summary: optional overall completion summary.
    """

    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.finish_task_list(session_id=runtime.session_id, final_summary=final_summary)
    _emit_task_list_update(task_list)
    return "Task list finished."
def _get_todo_service() -> TodoService:
    """获取 TodoService 实例。"""
    runtime = get_tool_runtime()
    if not runtime.config:
        raise RuntimeError("ToolRuntime.config 未初始化，无法创建 TodoService")
    memory_service = runtime.memory_service
    if memory_service is None:
        raise RuntimeError("ToolRuntime.memory_service 未初始化，无法创建 TodoService")
    return TodoService(
        engine=memory_service.engine,
        legacy_data_dir=str(runtime.config.storage.base_data_dir),
    )
def _get_automation_service() -> AutomationService:
    """获取当前运行时使用的自动化任务服务。"""

    runtime = get_tool_runtime()
    if not runtime.config:
        raise RuntimeError("ToolRuntime.config 未初始化，无法创建 AutomationService")
    memory_service = runtime.memory_service
    if memory_service is None:
        raise RuntimeError("ToolRuntime.memory_service 未初始化，无法创建 AutomationService")
    return AutomationService(
        engine=memory_service.engine,
        todo_service=TodoService(
            engine=memory_service.engine,
            legacy_data_dir=str(runtime.config.storage.base_data_dir),
        ),
    )
def list_todos() -> str:
    """
    列出当前用户的所有待办事项。返回格式化的待办列表,每行包含编号、ID、完成状态和截止日期。
    Agent 应当从输出中提取每个待办的 ID(格式为 todo_xxx)来调用 toggle_todo/edit_todo/delete_todo。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    items = service.list_todos(user_id=runtime.user_id)
    if not items:
        return "当前没有待办事项。"
    lines = []
    for i, item in enumerate(items, 1):
        status = "✅" if item.get("done") else "⬜"
        tid = item["id"]
        due = f" [截止: {item['dueDate']}]" if item.get("dueDate") else ""
        lines.append(f"{i}. [{tid}] {status} {item['text']}{due}")
    return "\n".join(lines)
def add_todo(text: str, due_date: str | None = None) -> str:
    """
    新增一条待办事项。

    text: 待办事项的文字描述。
    due_date: 可选截止日期,格式 YYYY-MM-DD。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    item = service.add_todo(user_id=runtime.user_id, text=text, due_date=due_date)
    due = f", 截止日期: {item['dueDate']}" if item.get("dueDate") else ""
    return f"已创建待办 [{item['id']}]: {item['text']}{due}"
def add_automation(
    text: str,
    prompt: str,
    next_run_at: str,
    timezone_name: str = "Asia/Shanghai",
    recurrence_frequency: str = "none",
    recurrence_interval: int | None = None,
    access_mode: str = "sandbox",
) -> str:
    """创建一个定时唤醒 Agent 的自动化任务。"""

    runtime = get_tool_runtime()
    service = _get_automation_service()
    try:
        item = service.create_task(
            user_id=runtime.user_id,
            text=text,
            prompt=prompt,
            next_run_at=next_run_at,
            timezone_name=timezone_name,
            recurrence={
                "frequency": recurrence_frequency,
                "interval": recurrence_interval or runtime.config.limits.nonempty_min_length,
            },
            access_mode=access_mode,
        )
    except ValueError as exc:
        return f"创建自动化任务失败: {exc}"
    return f"已创建自动化任务 [{item['id']}], 下一次执行时间: {item['nextRunAt']}"
def toggle_todo(todo_id: str) -> str:
    """
    切换待办事项的完成状态(已完成↔未完成)。

    todo_id: 待办的唯一 ID,可通过 list_todos 获取。
    """

    runtime = get_tool_runtime()
    automation_service = _get_automation_service()
    automation = automation_service.get_task_by_todo_id(user_id=runtime.user_id, todo_id=todo_id)
    if automation is not None:
        updated = automation_service.set_enabled(
            user_id=runtime.user_id,
            automation_id=str(automation["id"]),
            enabled=not bool(automation["enabled"]),
        )
        status = "已启用" if updated and updated["enabled"] else "已暂停"
        return f"自动化任务 [{automation['id']}] {status}"
    service = _get_todo_service()
    item = service.toggle_todo(user_id=runtime.user_id, todo_id=todo_id)
    if item is None:
        return f"未找到 ID 为 {todo_id} 的待办事项。"
    status = "已完成" if item.get("done") else "未完成"
    return f"已切换待办 [{item['id']}] 状态为: {status} — {item['text']}"
def edit_todo(todo_id: str, text: str | None = None, due_date: str | None = None) -> str:
    """
    编辑待办事项的文本或截止日期。

    todo_id: 待办的唯一 ID,可通过 list_todos 获取。
    text: 新的待办文本。留空则不修改。
    due_date: 新的截止日期(YYYY-MM-DD),传入空字符串可清除截止日期,不传则不修改。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    # 先获取当前项
    items = service.list_todos(user_id=runtime.user_id)
    current = next((item for item in items if item.get("id") == todo_id), None)
    if current is None:
        return f"未找到 ID 为 {todo_id} 的待办事项。"
    final_text = current["text"]
    if text:
        stripped = text.strip()
        if stripped:
            final_text = stripped
    final_due = current.get("dueDate")
    if due_date is not None:
        final_due = due_date
    item = service.edit_todo(user_id=runtime.user_id, todo_id=todo_id, text=final_text, due_date=final_due)
    if item is None:
        return f"编辑待办失败。"
    parts = [f"已更新待办: {item['text']}"]
    if item.get("dueDate"):
        parts.append(f"截止日期: {item['dueDate']}")
    return " | ".join(parts)
def delete_todo(todo_id: str) -> str:
    """
    删除指定的待办事项。

    todo_id: 待办的唯一 ID,可通过 list_todos 获取。
    """

    runtime = get_tool_runtime()
    automation_service = _get_automation_service()
    if automation_service.delete_task_by_todo_id(user_id=runtime.user_id, todo_id=todo_id):
        return f"已取消并删除自动化任务: {todo_id}"
    service = _get_todo_service()
    if service.delete_todo(user_id=runtime.user_id, todo_id=todo_id):
        return f"已删除待办: {todo_id}"
    return f"未找到 ID 为 {todo_id} 的待办事项。"
