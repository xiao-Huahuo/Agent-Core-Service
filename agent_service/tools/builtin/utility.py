"""utility 类内置工具实现。

函数体由原 builtin.py 机械迁移，工具行为不变。
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Callable
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

def list_available_tools() -> str:
    """
    列出当前可用的全部工具名称与用途。

    返回格式为每行一个工具:`- 中文名(工具名): 一句话用途`。
    当本轮只预绑定了部分工具时,可调用本工具查看完整清单,
    再在回复中说出所需工具名,下一轮即可放开绑定。
    """

    from agent_service.tools.tool_registry import ToolRegistry

    runtime = get_tool_runtime()
    registry = ToolRegistry.with_builtin_tools(config=runtime.config)
    if not registry.definitions:
        return "当前没有可用工具。"
    lines = []
    for definition in sorted(
        registry.definitions.values(),
        key=lambda d: (d.display_name or d.name),
    ):
        from agent_service.tools.definitions import MEMORY_TOOL_NAMES
        if definition.name in MEMORY_TOOL_NAMES and not runtime.long_term_memory_enabled:
            continue
        name = definition.name
        display = definition.display_name or name
        description = (definition.description or "").strip()
        first_line = next(
            (line.strip() for line in description.split("\n") if line.strip()),
            "",
        )
        if len(first_line) > 100:
            first_line = first_line[:100].rstrip() + "…"
        lines.append(f"- {display}({name}): {first_line}")
    return "\n".join(lines)
def list_skills() -> str:
    """
    List all skills visible to the current user.

    Return value: human-readable skill index with source and enabled state.
    """

    runtime = get_tool_runtime()
    if runtime.skill_service is None:
        return "Skill service is not available."
    skills = runtime.skill_service.list_skills(user_id=runtime.user_id)
    if not skills:
        return "No skills found."
    lines = [f"Skills found: {len(skills)}"]
    for index, skill in enumerate(skills, 1):
        enabled = "enabled" if skill.get("enabled") else "disabled"
        lines.append(
            f"{index}. {skill.get('name')} [{skill.get('skill_id')}, {skill.get('source')}, {enabled}] "
            f"- {skill.get('description') or ''}"
        )
    return "\n".join(lines)
def use_skill(skill_ref: str) -> str:
    """
    Load one enabled Skill's SKILL.md body for the current Agent turn.

    skill_ref: Skill id, Skill name, or skill directory name returned by list_skills.
    """

    runtime = get_tool_runtime()
    if runtime.skill_service is None:
        return "Skill service is not available."
    skill = runtime.skill_service.read_skill_body(user_id=runtime.user_id, skill_ref=skill_ref)
    if skill is None:
        return f"Skill not found: {skill_ref}. Call list_skills to inspect available skill ids and names."
    if skill.get("disabled"):
        return f"Skill is disabled: {skill.get('skill_id') or skill_ref}."
    return (
        f"Skill loaded: {skill.get('name')} [{skill.get('skill_id')}]\n"
        f"Source: {skill.get('source')}\n"
        f"Path: {skill.get('path')}\n\n"
        "[SKILL.md]\n"
        f"{skill.get('body') or ''}"
    )
