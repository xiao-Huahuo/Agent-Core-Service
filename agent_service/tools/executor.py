"""
工具执行器模块。

功能说明:
本文件负责根据工具名称和参数执行工具。它依赖 `ToolRegistry` 查找工具定义,
但不负责工具函数书写和工具注册。

使用说明:
可以在业务代码中创建执行器:

registry = ToolRegistry.with_builtin_tools()
executor = ToolExecutor(registry=registry)
result = executor.execute("echo_text", {"text": "hello"})
"""

from __future__ import annotations

from typing import Any

from agent_service.tools.tool_registry import ToolRegistry


class ToolExecutor:
    """
    工具执行器。

    registry: 工具注册表,用于根据名称查找工具定义。
    """

    def __init__(self, *, registry: ToolRegistry) -> None:
        """保存工具注册表。"""

        self.registry = registry

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """
        执行指定工具并返回字符串结果。

        name: 工具名称。
        arguments: 工具参数字典。
        """

        definition = self.registry.get(name)
        if definition is None:
            raise ValueError(f"工具 {name} 未注册。")
        return definition.function(**(arguments or {}))
