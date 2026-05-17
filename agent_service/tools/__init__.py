"""
工具层导出模块。
功能说明:
本文文件集中导出原生工具定义、工具注册表、执行器和工具运行时上下文。
MCP 适配仍位于 `agent_service.tools.mcp` 子包中,但通过 `ToolRegistry.with_builtin_tools(config=...)`
会自动与原生工具一起注册到 Agent。

工具定义按类别分为三组:
- UTILITY_TOOL_DEFINITIONS  通用工具
- MEMORY_TOOL_DEFINITIONS   长期记忆工具
- KNOWLEDGE_TOOL_DEFINITIONS 知识库工具
- BUILTIN_TOOL_DEFINITIONS  合并全部,保持向后兼容
"""

from agent_service.tools.builtin import (
    BUILTIN_TOOL_DEFINITIONS,
    KNOWLEDGE_TOOL_DEFINITIONS,
    MEMORY_TOOL_DEFINITIONS,
    UTILITY_TOOL_DEFINITIONS,
    BuiltinToolDefinition,
)
from agent_service.tools.executor import ToolExecutor
from agent_service.tools.runtime_context import (
    clear_agent_token_callback,
    clear_tool_runtime,
    clear_tool_trace_callback,
    get_agent_token_callback,
    set_agent_token_callback,
    set_tool_runtime,
    set_tool_trace_callback,
    set_planner_content_callback,
    clear_planner_content_callback,
    set_reflection_content_callback,
    clear_reflection_content_callback,
)
from agent_service.tools.tool_registry import ToolRegistry

__all__ = [
    "BUILTIN_TOOL_DEFINITIONS",
    "UTILITY_TOOL_DEFINITIONS",
    "MEMORY_TOOL_DEFINITIONS",
    "KNOWLEDGE_TOOL_DEFINITIONS",
    "BuiltinToolDefinition",
    "ToolExecutor",
    "ToolRegistry",
    "clear_agent_token_callback",
    "clear_tool_runtime",
    "clear_tool_trace_callback",
    "get_agent_token_callback",
    "set_agent_token_callback",
    "set_tool_runtime",
    "set_tool_trace_callback",
    "set_planner_content_callback",
    "clear_planner_content_callback",
    "set_reflection_content_callback",
    "clear_reflection_content_callback",
]
