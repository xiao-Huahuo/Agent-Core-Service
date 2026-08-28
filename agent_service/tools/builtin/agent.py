"""agent 类内置工具实现。

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

def spawn_child_agent(
    goal: str,
    mode: str = "background",
    allowed_tools: list[str] | None = None,
    access_mode: str = "sandbox",
    input_refs: list[str] | None = None,
    output_contract: dict[str, Any] | None = None,
    category: str = "",
    name: str = "",
) -> str:
    """由主 Agent 创建一个前台或后台子 Agent,返回子任务运行信息。

    category: 子 Agent 能力模板 key(agent/explore/plan)或自定义角色描述,可留空。
    name: 子 Agent 名字;留空时自动用角色模板名(plan1/agent1/...)。
    """

    runtime = get_tool_runtime()
    if runtime.child_agent_spawner is None:
        return "当前 Agent 运行时未启用子 Agent 能力。"
    return runtime.child_agent_spawner(
        goal=goal,
        mode=mode,
        allowed_tools=allowed_tools,
        access_mode=access_mode,
        input_refs=input_refs or [],
        output_contract=output_contract or {},
        category=category or None,
        name=name or None,
    )
def wait_for_child_agents(
    run_ids: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> str:
    """由主 Agent 等待一个后台子 Agent 结果,返回结果和当前子任务快照。"""

    runtime = get_tool_runtime()
    if runtime.child_agent_waiter is None:
        return "当前 Agent 运行时未启用等待子 Agent 的能力。"
    return runtime.child_agent_waiter(
        run_ids=run_ids or [],
        timeout_seconds=timeout_seconds,
    )
