"""
TODO 服务模块。

功能说明:
以 JSON 文件为用户粒度持久化待办事项。每用户一个文件，
存储在服务端 data/todos/ 目录下。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class TodoService:
    """用户待办事项持久化服务。"""

    def __init__(self, data_dir: str | None = None) -> None:
        """初始化 TODO 存储目录。"""
        base = data_dir or os.environ.get("AGENT_DATA_DIR", os.path.join(os.getcwd(), "data"))
        self._storage_dir = os.path.join(base, "todos")
        os.makedirs(self._storage_dir, exist_ok=True)

    def _user_path(self, user_id: str) -> str:
        """返回指定用户的 TODO JSON 文件路径。"""
        safe = user_id.replace("/", "_").replace("\\", "_")
        return os.path.join(self._storage_dir, f"{safe}.json")

    def _load(self, user_id: str) -> list[dict[str, Any]]:
        """加载指定用户的 TODO 列表。"""
        path = self._user_path(user_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("加载 TODO 数据失败 user=%s: %s", user_id, exc)
            return []

    def _save(self, user_id: str, todos: list[dict[str, Any]]) -> None:
        """持久化指定用户的 TODO 列表。"""
        path = self._user_path(user_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(todos, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("保存 TODO 数据失败 user=%s: %s", user_id, exc)

    def list_todos(self, user_id: str) -> list[dict[str, Any]]:
        """列出用户所有待办。"""
        return self._load(user_id)

    def add_todo(self, user_id: str, text: str, due_date: str | None = None) -> dict[str, Any]:
        """新增待办,返回创建的待办项。"""
        todos = self._load(user_id)
        item = {
            "id": f"todo_{uuid4().hex[:12]}",
            "text": text.strip(),
            "done": False,
            "createdAt": datetime.utcnow().isoformat(),
            "dueDate": due_date if due_date else None,
        }
        todos.insert(0, item)
        self._save(user_id, todos)
        return item

    def toggle_todo(self, user_id: str, todo_id: str) -> dict[str, Any] | None:
        """切换待办完成状态,返回更新后的项或 None。"""
        todos = self._load(user_id)
        for item in todos:
            if item.get("id") == todo_id:
                item["done"] = not item.get("done", False)
                self._save(user_id, todos)
                return item
        return None

    def edit_todo(self, user_id: str, todo_id: str, text: str, due_date: str | None = None) -> dict[str, Any] | None:
        """编辑待办文本和截止日期,返回更新后的项或 None。"""
        todos = self._load(user_id)
        stripped = text.strip()
        if not stripped:
            return None
        for item in todos:
            if item.get("id") == todo_id:
                item["text"] = stripped
                if due_date is not None:
                    item["dueDate"] = due_date if due_date else None
                self._save(user_id, todos)
                return item
        return None

    def delete_todo(self, user_id: str, todo_id: str) -> bool:
        """删除指定待办,返回是否成功删除。"""
        todos = self._load(user_id)
        before = len(todos)
        todos = [item for item in todos if item.get("id") != todo_id]
        if len(todos) == before:
            return False
        self._save(user_id, todos)
        return True
