"""
内置工具定义模块。

功能说明:
本文件只负责书写项目自带的小工具函数,不负责工具注册和工具执行。工具注册由
`tool_registry.py` 完成,工具执行由 `executor.py` 完成。

工具分为多个类别,分别存放在独立的分组列表中:
- UTILITY_TOOL_DEFINITIONS  通用工具 (当前时间、终端命令、下载等)
- MEMORY_TOOL_DEFINITIONS   长期记忆工具 (检索与写入用户跨会话记忆)
- KNOWLEDGE_TOOL_DEFINITIONS 知识库工具 (检索系统知识库文档切片)
- FILE_TOOL_DEFINITIONS     文件管理工具 (浏览、读写、创建、删除、重命名文件/文件夹)
- BUILTIN_TOOL_DEFINITIONS  合并全部内置工具,保持向后兼容

使用说明:
新增内置工具时,在本文件中书写普通 Python 函数,并在对应的分组列表中
登记工具名称、描述、参数说明和函数对象。
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


ToolFunction = Callable[..., str]






def _is_readonly_access() -> bool:
    """判断当前工具运行时是否处于只读权限模式。"""

    return get_tool_runtime().agent_access_mode == AGENT_ACCESS_READONLY


def _deny_readonly_write(action: str) -> str:
    """返回 Agent 只读权限下统一的写操作拒绝信息。"""

    return f"权限不足: 当前 Agent 权限为只读,已禁止{action}。请切换到沙盒或完全访问后重试。"


def _strip_markdown_html_fence(content: str) -> str:
    """Remove one surrounding Markdown code fence from generated HTML."""

    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 2 or lines[-1].strip() != "```":
        return stripped
    opener = lines[0].strip().lower()
    if opener in {"```", "```html", "```htm"}:
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _safe_visualization_filename(title: str, source_path: str, filename: str) -> str:
    """Create a safe timestamped HTML filename for runtime visualizations."""

    import re
    from pathlib import Path

    seed = filename.strip() or title.strip() or Path(source_path).stem or "visualization"
    seed = seed.replace("\\", "/").split("/")[-1]
    seed = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", seed, flags=re.UNICODE).strip("._")
    if not seed:
        seed = "visualization"
    stem = Path(seed).stem or "visualization"
    return f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"


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
    display_name: str = ""








































































































































