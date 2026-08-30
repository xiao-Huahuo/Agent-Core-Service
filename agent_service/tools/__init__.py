"""
工具层导出模块。
功能说明:
本文文件集中导出原生工具定义、工具注册表、执行器和工具运行时上下文。
MCP 适配仍位于 `agent_service.tools.mcp` 子包中,但通过 `ToolRegistry.with_builtin_tools(config=...)`
会自动与原生工具一起注册到 Agent。

工具定义按类别分为五组:
- UTILITY_TOOL_DEFINITIONS  通用工具
- MEMORY_TOOL_DEFINITIONS   长期记忆工具
- KNOWLEDGE_TOOL_DEFINITIONS 知识库工具
- FILE_TOOL_DEFINITIONS     文件管理工具
- BUILTIN_TOOL_DEFINITIONS  合并全部,保持向后兼容
"""

from agent_service.tools.builtin import business_ops as builtin_business_ops
from agent_service.tools.builtin import knowledge_ops as builtin_knowledge_ops
from agent_service.tools.builtin import smart_forms as builtin_smart_forms

from agent_service.tools.builtin import (
    BUILTIN_TOOL_DEFINITIONS,
    FILE_TOOL_DEFINITIONS,
    KNOWLEDGE_TOOL_DEFINITIONS,
    MEMORY_TOOL_DEFINITIONS,
    TODO_TOOL_DEFINITIONS,
    UTILITY_TOOL_DEFINITIONS,
    BuiltinToolDefinition,
)
from agent_service.tools.executor import ToolExecutor
from agent_service.tools.runtime_context import (
    AGENT_ACCESS_FULL,
    AGENT_ACCESS_MODES,
    AGENT_ACCESS_READONLY,
    AGENT_ACCESS_SANDBOX,
    clear_agent_token_callback,
    clear_agent_thinking_callback,
    clear_context_mirror_callback,
    clear_context_compression_callback,
    clear_plan_state,
    clear_planner_content_callback,
    clear_observation_content_callback,
    clear_markdown_html_visualization_callback,
    clear_tool_runtime,
    clear_tool_trace_callback,
    clear_task_list_callback,
    get_agent_token_callback,
    get_agent_thinking_callback,
    get_markdown_html_visualization_callback,
    get_plan_state,
    get_task_list_callback,
    normalize_agent_access_mode,
    set_agent_token_callback,
    set_agent_thinking_callback,
    set_context_mirror_callback,
    set_context_compression_callback,
    set_markdown_html_visualization_callback,
    set_plan_state,
    set_planner_content_callback,
    set_observation_content_callback,
    set_task_list_callback,
    set_tool_runtime,
    set_tool_trace_callback,
)
from agent_service.tools.tool_registry import ToolRegistry

__all__ = [
    "BUILTIN_TOOL_DEFINITIONS",
    "UTILITY_TOOL_DEFINITIONS",
    "MEMORY_TOOL_DEFINITIONS",
    "KNOWLEDGE_TOOL_DEFINITIONS",
    "FILE_TOOL_DEFINITIONS",
    "BuiltinToolDefinition",
    "ToolExecutor",
    "ToolRegistry",
    "AGENT_ACCESS_FULL",
    "AGENT_ACCESS_MODES",
    "AGENT_ACCESS_READONLY",
    "AGENT_ACCESS_SANDBOX",
    "clear_agent_token_callback",
    "clear_agent_thinking_callback",
    "clear_context_mirror_callback",
    "clear_context_compression_callback",
    "clear_plan_state",
    "clear_planner_content_callback",
    "clear_observation_content_callback",
    "clear_markdown_html_visualization_callback",
    "clear_tool_runtime",
    "clear_tool_trace_callback",
    "clear_task_list_callback",
    "get_agent_token_callback",
    "get_agent_thinking_callback",
    "get_markdown_html_visualization_callback",
    "get_plan_state",
    "get_task_list_callback",
    "normalize_agent_access_mode",
    "set_agent_token_callback",
    "set_agent_thinking_callback",
    "set_context_mirror_callback",
    "set_context_compression_callback",
    "set_markdown_html_visualization_callback",
    "set_plan_state",
    "set_planner_content_callback",
    "set_observation_content_callback",
    "set_task_list_callback",
    "set_tool_runtime",
    "set_tool_trace_callback",
]
