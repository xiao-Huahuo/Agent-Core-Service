"""library 类内置工具实现。

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

def _get_library_service() -> Any:
    """返回启动阶段注入的图书馆虚拟编目服务,未就绪时抛出 RuntimeError。"""

    from agent_service.api.rest.deps import _require_library_service

    try:
        return _require_library_service()
    except Exception as exc:
        raise RuntimeError(f"图书馆服务未就绪: {exc}")
def _format_library_item(item: dict[str, Any], index: int = 0) -> str:
    """将单个图书馆条目序列化为一行或多行可读文本,便于 Agent 提取 item_id。"""

    item_type = "集锦" if item.get("item_type") == "collection" else "图书"
    title = item.get("display_title") or item.get("title") or "(未命名)"
    item_id = str(item.get("item_id") or "")
    prefix = f"{index}. " if index else ""
    lines = [f"{prefix}[{item_type}] {title} ({item_id})"]
    if item.get("source_path"):
        lines.append(f"    路径: {item['source_path']}")
    if item.get("source_url"):
        lines.append(f"    URL: {item['source_url']}")
    status_parts: list[str] = []
    if item.get("source_exists") is False:
        status_parts.append("源文件缺失")
    if item.get("index_status"):
        status_parts.append(f"入库: {item['index_status']}")
    if item.get("graph_status"):
        status_parts.append(f"图谱: {item['graph_status']}")
    if status_parts:
        lines.append(f"    状态: {' | '.join(status_parts)}")
    if item.get("child_count"):
        lines.append(f"    子项: {item['child_count']}")
    tags = item.get("tags") or []
    if tags:
        lines.append(f"    标签: {', '.join(str(tag) for tag in tags)}")
    return "\n".join(lines)
def list_library_items(
    parent_id: str = "",
    query: str = "",
    tag: str = "",
    content_type: str = "",
    sort: str = "updated_at",
    direction: str = "desc",
) -> str:
    """
    列出当前用户知识库的图书馆条目(图书与集锦),返回条目标题、item_id、路径、状态与标签。

    parent_id: 集锦 item_id;为空表示图书馆根层。
    query: 按标题、描述或真实文件名关键词过滤。
    tag: 按标签名过滤。
    content_type: knowledge_file/web_url/external_file/collection 过滤。
    sort: title/source_mtime/updated_at/created_at/sort_order。
    direction: asc 或 desc。
    """

    runtime = get_tool_runtime()
    try:
        service = _get_library_service()
        payload = service.list_items(
            user_id=runtime.user_id,
            parent_id=parent_id,
            query=query,
            tag=tag,
            content_type=content_type,
            sort=sort,
            direction=direction,
        )
    except Exception as exc:
        return f"列出图书馆失败: {exc}"
    items = payload.get("items") or []
    if not items:
        return "当前图书馆没有匹配的条目。"
    lines: list[str] = []
    crumbs = payload.get("breadcrumbs") or []
    if crumbs:
        lines.append("当前位置: " + " > ".join(str(c.get("title") or "") for c in crumbs))
    lines.append(f"共 {len(items)} 个条目:")
    for i, item in enumerate(items, 1):
        lines.append(_format_library_item(item, index=i))
    return "\n".join(lines)
def list_library_tags() -> str:
    """列出当前用户知识库的图书馆标签,供新增条目时复用已有标签。"""

    runtime = get_tool_runtime()
    try:
        service = _get_library_service()
        payload = service.list_tags(user_id=runtime.user_id)
    except Exception as exc:
        return f"列出图书馆标签失败: {exc}"
    tags = payload.get("tags") or []
    if not tags:
        return "当前知识库还没有图书馆标签。"
    return "\n".join(f"- {tag['name']} ({tag['tag_id']})" for tag in tags)
def add_library_book(
    content_type: str = "knowledge_file",
    source_path: str = "",
    source_url: str = "",
    parent_id: str = "",
    title: str = "",
    description: str = "",
    tags: list[str] | None = None,
) -> str:
    """
    将一份资料加入图书馆成为图书卡片。

    content_type: knowledge_file(知识库文件,需 source_path)/web_url(网页,需 source_url)/external_file(外部本地文件路径)。
    source_path: knowledge_file 时相对知识库根目录的路径,如 notes/a.md。
    source_url: web_url 时的网页地址。
    parent_id: 目标集锦 item_id;为空表示放入图书馆根层。
    title: 图书标题;为空时自动用源文件名。
    description: 图书描述。
    tags: 标签名列表。
    """

    if _is_readonly_access():
        return _deny_readonly_write("新增图书馆图书")
    runtime = get_tool_runtime()
    try:
        service = _get_library_service()
        result = service.create_item(
            user_id=runtime.user_id,
            parent_id=parent_id,
            content_type=content_type,
            source_path=source_path,
            source_url=source_url,
            title=title,
            description=description,
            tags=list(tags) if tags else [],
        )
    except Exception as exc:
        return f"新增图书馆图书失败: {exc}"
    item = result.get("item") or {}
    return f"已加入图书馆: {item.get('display_title') or title}(item_id: {item.get('item_id')})"
def add_library_collection(
    title: str,
    description: str = "",
    parent_id: str = "",
    tags: list[str] | None = None,
) -> str:
    """
    在图书馆中新增一个集锦(资料分组),可嵌套到其他集锦。

    title: 集锦名称,会自动转换成可用文件夹名。
    description: 集锦描述。
    parent_id: 父集锦 item_id;为空表示放在图书馆根层。
    tags: 标签名列表。
    """

    if _is_readonly_access():
        return _deny_readonly_write("新增图书馆集锦")
    runtime = get_tool_runtime()
    try:
        service = _get_library_service()
        result = service.create_collection(
            user_id=runtime.user_id,
            parent_id=parent_id,
            title=title,
            description=description,
            tags=list(tags) if tags else [],
        )
    except Exception as exc:
        return f"新增图书馆集锦失败: {exc}"
    item = result.get("item") or {}
    return f"已创建集锦: {item.get('display_title') or title}(item_id: {item.get('item_id')})"
def update_library_item(
    item_id: str,
    title: str | None = None,
    parent_id: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    更新图书馆条目的虚拟元数据(改名、移动集锦、改描述、换标签)。

    item_id: 目标条目 ID,由 list_library_items 返回。
    title: 新标题;不传则保留原标题。
    parent_id: 新所在集锦 ID;传空字符串移回根层;不传不移动。
    description: 新描述。
    tags: 新的标签列表;传空数组清空标签;不传不修改。
    """

    if _is_readonly_access():
        return _deny_readonly_write("更新图书馆条目")
    runtime = get_tool_runtime()
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if parent_id is not None:
        payload["parent_id"] = parent_id
    if description is not None:
        payload["description"] = description
    if tags is not None:
        payload["tags"] = list(tags)
    try:
        service = _get_library_service()
        result = service.update_item(user_id=runtime.user_id, item_id=item_id, payload=payload)
    except Exception as exc:
        return f"更新图书馆条目失败: {exc}"
    item = result.get("item") or {}
    return f"已更新图书馆条目: {item.get('display_title') or item_id}({item_id})"
def remove_library_item(item_id: str) -> str:
    """
    将条目移出图书馆,不删除真实文件。

    item_id: 目标条目 ID;集锦会连带移除其嵌套子项。
    """

    if _is_readonly_access():
        return _deny_readonly_write("移出图书馆")
    runtime = get_tool_runtime()
    try:
        service = _get_library_service()
        result = service.delete_item(user_id=runtime.user_id, item_id=item_id)
    except Exception as exc:
        return f"移出图书馆失败: {exc}"
    deleted_ids = result.get("deleted_item_ids") or []
    nested = len(deleted_ids) - 1 if deleted_ids else 0
    suffix = f", 连带移除 {nested} 个嵌套子项" if nested else ""
    return f"已移出图书馆: {item_id}{suffix}(真实文件未删除)"
