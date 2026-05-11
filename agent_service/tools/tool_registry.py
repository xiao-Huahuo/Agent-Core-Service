"""
工具注册表模块。

功能说明:
本文件负责维护工具名称到工具定义的映射,并提供 LangChain 工具对象转换能力。
它不直接书写工具函数,也不直接执行工具。

使用说明:
调用 `ToolRegistry.with_builtin_tools()` 可以创建包含当前全部内置工具的注册表。
AgentCore 默认会使用该注册表生成 LangChain 工具列表并绑定到模型。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from agent_service.tools.builtin import BUILTIN_TOOL_DEFINITIONS, BuiltinToolDefinition


class ToolRegistry:
    """
    工具注册表。

    definitions: 工具名称到工具定义的映射。
    """

    def __init__(self) -> None:
        """创建空工具注册表。"""

        self.definitions: dict[str, BuiltinToolDefinition] = {}

    @classmethod
    def with_builtin_tools(cls) -> "ToolRegistry":
        """创建并返回已注册所有内置工具的注册表。"""

        registry = cls()
        for definition in BUILTIN_TOOL_DEFINITIONS:
            registry.register(definition)
        return registry

    def register(self, definition: BuiltinToolDefinition) -> None:
        """
        注册单个工具定义。

        definition: 需要注册的内置工具定义。
        """

        if definition.name in self.definitions:
            raise ValueError(f"工具 {definition.name} 已注册。")
        self.definitions[definition.name] = definition

    def get(self, name: str) -> BuiltinToolDefinition | None:
        """
        根据工具名称获取工具定义。

        name: 工具名称。
        """

        return self.definitions.get(name)

    def to_langchain_tools(self) -> list[StructuredTool]:
        """将全部已注册工具转换为 LangChain StructuredTool 列表。"""

        return [self._to_langchain_tool(definition) for definition in self.definitions.values()]

    def _to_langchain_tool(self, definition: BuiltinToolDefinition) -> StructuredTool:
        """
        将单个工具定义转换为 LangChain StructuredTool。

        definition: 需要转换的内置工具定义。
        """

        return StructuredTool.from_function(
            func=definition.function,
            name=definition.name,
            description=definition.description,
            args_schema=self._build_args_model(definition),
        )

    @staticmethod
    def _build_args_model(definition: BuiltinToolDefinition) -> type[BaseModel]:
        """
        根据工具 JSON Schema 创建 Pydantic 参数模型。

        definition: 需要生成参数模型的内置工具定义。
        """

        fields: dict[str, tuple[type[Any], Any]] = {}
        properties = definition.args_schema.get("properties", {})
        required = set(definition.args_schema.get("required", []))
        for field_name, field_schema in properties.items():
            field_type = ToolRegistry._json_schema_type_to_python(field_schema.get("type", "string"))
            default = ... if field_name in required else None
            description = field_schema.get("description", "")
            fields[field_name] = (field_type, Field(default=default, description=description))
        return create_model(f"{definition.name.title().replace('_', '')}Args", **fields)

    @staticmethod
    def _json_schema_type_to_python(schema_type: str) -> type[Any]:
        """
        将简单 JSON Schema 类型转换为 Python 类型。

        schema_type: JSON Schema 的 type 字段。
        """

        mapping: dict[str, type[Any]] = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
        }
        return mapping.get(schema_type, str)
