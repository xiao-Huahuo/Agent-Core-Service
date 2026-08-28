"""terminal 类内置工具实现。

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

def run_terminal_command(
    shell: str,
    segments: list[dict[str, Any]],
    cwd: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    """
    在 Agent 终端沙盒中执行结构化指令段。

    shell: 终端策略名,可选 cmd、powershell、bash。
    segments: 指令段数组,每段格式为 {"program": "python", "args": ["-m", "pytest"]}。
    cwd: 相对工作区根目录的执行目录,必须保持在终端沙盒工作区内。
    timeout_seconds: 可选单段超时时间,超过用户配置上限时自动收紧。
    """

    runtime = get_tool_runtime()
    from agent_service.services.settings.service import SettingsService
    from agent_service.services.terminal.command_sandbox import (
        TerminalSandbox,
        TerminalSandboxSettings,
        dumps_terminal_result,
    )

    if runtime.memory_service is None:
        return "终端执行失败: 当前工具运行时缺少设置服务依赖。"
    settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
    payload = settings_service.get_terminal_sandbox_config(user_id=runtime.user_id)["config"]
    settings = TerminalSandboxSettings.from_config_payload(config=runtime.config, payload=payload)
    sandbox = TerminalSandbox(settings=settings, access_mode=runtime.agent_access_mode)
    try:
        result = sandbox.run(
            shell=shell,
            cwd=cwd,
            segments=segments,
            timeout_seconds=timeout_seconds,
        )
    except ValueError as exc:
        return f"终端执行被沙盒拦截: {exc}"
    return dumps_terminal_result(result)
