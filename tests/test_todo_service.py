"""
TODO 数据库服务测试。

覆盖旧 JSON 一次性迁移、提醒字段持久化和循环 TODO 推进逻辑。
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import create_engine

from agent_service.services.todo_service import TodoService


def test_legacy_json_is_imported_once(tmp_path: Path) -> None:
    """旧 JSON 应被导入数据库,之后 JSON 修改不应影响读取结果。"""

    legacy_dir = tmp_path / "todos"
    legacy_dir.mkdir()
    (legacy_dir / "u1.json").write_text(
        json.dumps([{"id": "old-1", "text": "旧任务", "done": False}], ensure_ascii=False),
        encoding="utf-8",
    )
    service = TodoService(engine=create_engine("sqlite://"), legacy_data_dir=str(tmp_path))

    assert service.list_todos("u1")[0]["id"] == "old-1"
    (legacy_dir / "u1.json").write_text("[]", encoding="utf-8")
    assert service.list_todos("u1")[0]["text"] == "旧任务"


def test_repeating_todo_advances_due_and_reminder(tmp_path: Path) -> None:
    """完成每日循环 TODO 后应推进截止时间和提醒时间,而不是永久完成。"""

    service = TodoService(engine=create_engine("sqlite://"), legacy_data_dir=str(tmp_path))
    item = service.add_todo(
        "u1",
        "每日备份",
        due_date="2026-08-02T21:00:00+00:00",
        reminder_at="2026-08-02T20:30:00+00:00",
        recurrence={"frequency": "daily", "interval": 1},
    )

    updated = service.toggle_todo("u1", item["id"])

    assert updated is not None
    assert updated["done"] is False
    assert updated["lastCompletedAt"]
    assert updated["dueDate"] == "2026-08-03T21:00:00+00:00"
    assert updated["reminderAt"] == "2026-08-03T20:30:00+00:00"
