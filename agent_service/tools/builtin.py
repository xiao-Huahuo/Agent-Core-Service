"""
内置工具定义模块。

功能说明:
本文件只负责书写项目自带的小工具函数,不负责工具注册和工具执行。工具注册由
`tool_registry.py` 完成,工具执行由 `executor.py` 完成。

使用说明:
新增内置工具时,在本文件中书写普通 Python 函数,并在 `BUILTIN_TOOL_DEFINITIONS`
中登记工具名称、描述、参数说明和函数对象。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


ToolFunction = Callable[..., str]


@dataclass(frozen=True, slots=True)
class BuiltinToolDefinition:
    """
    内置工具定义。

    name: 工具名称,需要和 LLM tool_call 中的 name 匹配。
    description: 工具用途说明,会暴露给 LLM 作为工具选择依据。
    args_schema: 工具参数 JSON Schema,用于生成 LangChain StructuredTool。
    function: 实际执行的 Python 函数。
    """

    name: str
    description: str
    args_schema: dict[str, Any]
    function: ToolFunction


def get_current_utc_time() -> str:
    """
    获取当前 UTC 时间。

    返回值: ISO 8601 格式 UTC 时间字符串。
    """

    return datetime.now(timezone.utc).isoformat()


def echo_text(text: str) -> str:
    """
    原样返回输入文本。

    text: 需要回显的文本。
    """

    return text


BUILTIN_TOOL_DEFINITIONS = [
    BuiltinToolDefinition(
        name="get_current_utc_time",
        description="获取当前 UTC 时间。当用户询问当前时间或需要时间戳时使用。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=get_current_utc_time,
    ),
    BuiltinToolDefinition(
        name="echo_text",
        description="原样返回输入文本。用于测试工具调用链路是否正常。",
        args_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "需要原样返回的文本。",
                }
            },
            "required": ["text"],
        },
        function=echo_text,
    ),
]
