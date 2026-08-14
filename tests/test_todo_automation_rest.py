"""TODO 删除接口与自动化生命周期的一致性测试。"""

from __future__ import annotations

import asyncio
from typing import Any

from agent_service.api.rest import todo as todo_rest


class FakeTodoService:
    """记录普通 TODO 删除回退。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def delete_todo(self, **kwargs: str) -> bool:
        """模拟普通 TODO 删除成功。"""

        self.calls.append(kwargs)
        return True


def test_todo_delete_uses_shared_cascading_service(monkeypatch: Any) -> None:
    """TODO 删除接口统一调用具备自动化级联能力的共享服务。"""

    todos = FakeTodoService()
    monkeypatch.setattr(todo_rest, "_require_todo_service", lambda: todos)

    result = asyncio.run(todo_rest.api_delete_todo({"user_id": "u1", "todo_id": "todo_1"}))

    assert result == {"deleted": True}
    assert todos.calls == [{"user_id": "u1", "todo_id": "todo_1"}]


def test_todo_delete_keeps_regular_todo_behavior(monkeypatch: Any) -> None:
    """普通 TODO 继续使用同一个删除服务。"""

    todos = FakeTodoService()
    monkeypatch.setattr(todo_rest, "_require_todo_service", lambda: todos)

    result = asyncio.run(todo_rest.api_delete_todo({"user_id": "u1", "todo_id": "todo_2"}))

    assert result == {"deleted": True}
    assert todos.calls == [{"user_id": "u1", "todo_id": "todo_2"}]
