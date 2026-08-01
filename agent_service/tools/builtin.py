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
from agent_service.services.todo_service import TodoService


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


def get_current_time(timezone_name: str = "UTC") -> str:
    """
    获取指定时区的当前时间。

    timezone_name: IANA 时区名称,例如 `UTC`、`Asia/Shanghai`、`America/New_York`。
    """

    normalized_timezone_name = timezone_name or "UTC"
    try:
        target_timezone = ZoneInfo(normalized_timezone_name)
    except ZoneInfoNotFoundError:
        return f"未知时区: {normalized_timezone_name}"
    return datetime.now(target_timezone).isoformat()


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
    from agent_service.services.settings_service import SettingsService
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


def get_long_term_memory(query: str, top_k: int = 3) -> str:
    """
    检索当前用户的长期摘要记忆。

    query: 检索查询文本。
    top_k: 最多返回多少条结果。
    """

    runtime = get_tool_runtime()
    results = runtime.retrieval_service.retrieve_long_term_memory(
        query=query,
        user_id=runtime.user_id,
        session_id=runtime.session_id,
        top_k=top_k,
    )
    if not results:
        return "未找到相关长期记忆。"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"{i}. {item.memory.content}")
    return "\n\n".join(lines)


def get_knowledge_context(query: str, top_k: int = 3) -> str:
    """
    检索知识库相关片段。

    query: 检索查询文本。
    top_k: 最多返回多少条结果。
    """

    runtime = get_tool_runtime()
    results = runtime.retrieval_service.retrieve_knowledge(
        query=query,
        user_id=runtime.user_id,
        top_k=top_k,
    )
    if not results:
        return "未找到相关知识库内容。"
    lines = []
    for i, item in enumerate(results, 1):
        source = item.memory.source_uri or "未知来源"
        citation_id = register_tool_citation(
            source_uri=source,
            content=item.memory.content,
            adopted_by_default=True,
        )
        lines.append(f"{i}. [{citation_id}] 来源: {source}\n   内容: {item.memory.content}")
    return "\n\n".join(lines)


def rebuild_knowledge_base(knowledge_dir: str = "") -> str:
    """
    主动重新扫描当前用户的知识库并灌入向量库。

    knowledge_dir: 可选新知识库目录;为空时使用当前用户设置中的目录。
    """

    if _is_readonly_access():
        return _deny_readonly_write("重建知识库")
    runtime = get_tool_runtime()
    from agent_service.services.knowledge_library_service import KnowledgeLibraryService
    from agent_service.services.settings_service import SettingsService

    if runtime.memory_service is None:
        return "知识库重建失败: 当前工具运行时缺少记忆写入服务。"
    settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
    knowledge_service = KnowledgeLibraryService(
        config=runtime.config,
        memory_service=runtime.memory_service,
        settings_service=settings_service,
        embedding_service=runtime.embedding_service,
    )
    try:
        result = knowledge_service.rebuild_user_knowledge(
            user_id=runtime.user_id,
            knowledge_dir=knowledge_dir.strip() or None,
        )
    except ValueError as exc:
        return f"知识库重建失败: {exc}"
    return (
        "知识库重建完成: "
        f"扫描 {result.frontmatter_files_seen} 个文件, "
        f"写入 {result.files_ingested} 个文档, "
        f"创建 {result.chunks_created} 个切片, "
        f"清理 {result.chunks_deleted} 个旧切片。"
    )


def search_knowledge(query: str, fulltext: bool = True, semantic: bool = False) -> str:
    """
    在用户知识库中联合搜索文件。

    query: 搜索关键词。
    fulltext: 是否对文件内容做全文匹配,默认开启。
    semantic: 是否启用语义搜索,默认关闭。
    """

    import os as _os

    runtime = get_tool_runtime()
    from agent_service.services.knowledge_library_service import KnowledgeLibraryService
    from agent_service.services.settings_service import SettingsService

    if runtime.memory_service is None:
        return "搜索失败: 当前工具运行时缺少记忆服务。"

    settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
    knowledge_service = KnowledgeLibraryService(
        config=runtime.config,
        memory_service=runtime.memory_service,
        settings_service=settings_service,
        embedding_service=runtime.embedding_service,
    )

    # ---- 文件名搜索 ----
    filename_results: list[str] = []
    try:
        tree = knowledge_service.list_files(user_id=runtime.user_id)

        def _search_nodes(nodes: list[dict], results: list[dict]) -> None:
            for node in nodes:
                name = str(node.get("name", "") or "")
                if query.lower() in name.lower():
                    results.append({"path": str(node.get("path", "") or ""), "name": name})
                children = node.get("children")
                if isinstance(children, list):
                    _search_nodes(children, results)

        _search_nodes(tree, filename_results)
    except ValueError:
        pass

    # ---- 全文内容搜索 ----
    fulltext_results: list[dict] = []
    library_root = str(knowledge_service.get_active_root_path(user_id=runtime.user_id))

    def _is_in_library(uri: str) -> bool:
        if not uri:
            return False
        try:
            nu = _os.path.normcase(_os.path.normpath(uri))
            nr = _os.path.normcase(_os.path.normpath(library_root))
            return nu.startswith(nr + _os.path.sep) or nu == nr
        except (ValueError, TypeError):
            return False

    if fulltext and runtime.memory_service is not None:
        try:
            raw = runtime.memory_service.search_knowledge_content(query=query, user_id=runtime.user_id)
            disk_matches = knowledge_service.search_file_contents(user_id=runtime.user_id, query=query)
            seen_paths: set[str] = set()
            for item in [*raw, *disk_matches]:
                uri = str(item.get("source_uri") or "")
                if not _is_in_library(uri):
                    continue
                normalized_uri = _os.path.normcase(_os.path.normpath(uri))
                if normalized_uri in seen_paths:
                    continue
                seen_paths.add(normalized_uri)
                fulltext_results.append(item)
        except Exception:
            pass

    # ---- 语义搜索 ----
    semantic_results: list[dict] = []
    if semantic:
        try:
            top_k = runtime.config.memory.knowledge_search_semantic_top_k
            items = runtime.retrieval_service.retrieve_knowledge(
                query=query, user_id=runtime.user_id, top_k=top_k,
            )
            seen_names: set[str] = set()
            for item in items:
                uri = item.memory.source_uri or ""
                if not _is_in_library(uri):
                    continue
                name = _os.path.basename(uri)
                if name in seen_names:
                    continue
                seen_names.add(name)
                semantic_results.append({
                    "source_uri": uri,
                    "content": item.memory.content,
                })
        except Exception:
            pass

    # ---- 格式化输出 ----
    lines: list[str] = []
    if filename_results:
        lines.append("=== 文件名匹配 ===")
        for r in filename_results:
            lines.append(f"  {r['name']}  ({r['path']})")
    if fulltext_results:
        lines.append("=== 内容匹配 ===")
        for r in fulltext_results:
            uri = str(r.get("source_uri") or "")
            snippet = str(r.get("snippet") or "")
            citation_id = register_tool_citation(source_uri=uri or "未知来源", content=snippet)
            lines.append(f"  [{citation_id}] {_os.path.basename(uri)}")
            if snippet:
                lines.append(f"    片段: {snippet}")
    if semantic_results:
        lines.append("=== 语义匹配 ===")
        for r in semantic_results:
            uri = str(r.get("source_uri") or "")
            content = str(r.get("content") or "")
            citation_id = register_tool_citation(source_uri=uri or "未知来源", content=content)
            lines.append(f"  [{citation_id}] {_os.path.basename(uri)}")
            if content:
                brief = content[:200] + ("..." if len(content) > 200 else "")
                lines.append(f"    摘要: {brief}")

    if not any([filename_results, fulltext_results, semantic_results]):
        return f"在用户 {runtime.user_id} 的知识库中未找到与 '{query}' 相关的文件。"

    return "\n".join(lines)


def _supersede_prior_entries(
    *,
    runtime: Any,
    user_id: str,
    memory_type: str,
) -> None:
    """
    将同一用户、同一 memory_type 的旧 active 记忆标记为 superseded。
    确保手动写入的类型中只有最新一条保持 active 状态。
    """

    from sqlmodel import Session, select

    from agent_service.models.longterm_memory_spec import LongTermMemorySpec

    if runtime.memory_service is None:
        return
    memory_service = runtime.memory_service
    with Session(memory_service.engine) as db_session:
        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == runtime.config.constants.memory_tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .where(LongTermMemorySpec.source_type == "manual_write")
        )
        records = db_session.exec(statement).all()
        for record in records:
            metadata = dict(record.metadata_json or {})
            if metadata.get("fact_status") != "active":
                continue
            metadata["fact_status"] = "superseded"
            record.metadata_json = metadata
            db_session.add(record)
        db_session.commit()


def write_long_term_memory(
    content: str,
    memory_type: str = "important_fact_summary",
    importance: float = 0.5,
    authority: float = 0.5,
) -> str:
    """
    向当前用户的长期记忆中写入一条记录,包含向量化后可被后续对话检索召回。

    content: 需要记忆的内容。
    memory_type: 记忆子类型,默认 important_fact_summary。可选值与检索优先级相关。
    importance: 重要性(0~1),默认 0.5。
    authority: 权威性(0~1),默认 0.5。
    """

    runtime = get_tool_runtime()
    _supersede_prior_entries(
        runtime=runtime,
        user_id=runtime.user_id,
        memory_type=memory_type,
    )
    embedding = runtime.embedding_service.embed_text(content) if runtime.embedding_service else []
    now = datetime.now(timezone.utc)
    create_dto = LongTermMemorySpecCreate(
        user_id=runtime.user_id,
        session_id=runtime.session_id,
        tag=runtime.config.constants.memory_tag,
        memory_type=memory_type,
        content=content,
        source_type="manual_write",
        source_id=None,
        source_uri="manual",
        confidence=1.0,
        importance=importance,
        authority=authority,
        embedding_model=runtime.config.model.embedding_model_name or None,
        embedding_vector_json=embedding,
        metadata_json={
            "fact_status": "active",
            "fact": {"namespace": "general", "key": memory_type, "value": content},
        },
    )

    memory = runtime.memory_service.create_memory(create_dto)
    return f"已记住: {content}"


def delete_long_term_memory(content: str) -> str:
    """
    删除当前用户的一条长期记忆。按内容文本匹配后删除。

    content: 需要删除的记忆内容关键词或完整句子。会尝试精确匹配和包含匹配。
    """

    if _is_readonly_access():
        return _deny_readonly_write("删除长期记忆")
    normalized_content = content.strip()
    if not normalized_content:
        return "删除失败: content 不能为空。"
    runtime = get_tool_runtime()
    memories = runtime.memory_service.list_user_memories(
        user_id=runtime.user_id, limit=200,
    )
    lower_content = normalized_content.lower()
    matched = None
    for m in memories:
        if m.content.strip().lower() == lower_content:
            matched = m
            break
    if not matched:
        for m in memories:
            if lower_content in m.content.strip().lower() or m.content.strip().lower() in lower_content:
                matched = m
                break
    if not matched:
        return f"未找到内容匹配的长期记忆: {normalized_content}"
    success = runtime.memory_service.delete_memory(memory_id=matched.memory_id)
    if success:
        return f"已删除长期记忆: {matched.content[:200]}"
    return f"删除长期记忆失败，可能已被删除。"


def delete_long_term_rule(content: str) -> str:
    """
    删除当前用户的一条长期系统规则。按内容文本匹配后删除。

    content: 需要删除的规则内容关键词或完整句子。会尝试精确匹配和包含匹配。
    """

    if _is_readonly_access():
        return _deny_readonly_write("删除长期规则")
    normalized_content = content.strip()
    if not normalized_content:
        return "删除失败: content 不能为空。"
    runtime = get_tool_runtime()
    if runtime.memory_service is None:
        return "删除长期规则失败: 当前工具运行时缺少设置存储服务。"
    from agent_service.services.settings_service import SettingsService

    settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
    entries = settings_service.list_system_prompt_entries(user_id=runtime.user_id)
    lower_content = normalized_content.lower()
    matched = None
    for entry in entries:
        if entry["content"].strip().lower() == lower_content:
            matched = entry
            break
    if not matched:
        for entry in entries:
            entry_content = entry["content"].strip().lower()
            if lower_content in entry_content or entry_content in lower_content:
                matched = entry
                break
    if not matched:
        return f"未找到内容匹配的长期规则: {normalized_content}"
    success = settings_service.delete_system_prompt_entry(prompt_id=matched["prompt_id"])
    if success:
        return f"已删除长期规则: {matched['content'][:200]}"
    return f"删除长期规则失败，可能已被删除。"


def write_long_term_rule(content: str) -> str:
    """
    追加一条当前用户的长期系统规则。

    content: 需要每轮 Agent 都必须读取并遵守的长期规则。该内容写入用户自定义系统提示词,
    与设置页手动追加系统提示词等效,不会作为 RAG 记忆按相关性召回。
    """

    normalized_content = content.strip()
    if not normalized_content:
        return "长期规则写入失败: content 不能为空。"
    runtime = get_tool_runtime()
    if runtime.memory_service is None:
        return "长期规则写入失败: 当前工具运行时缺少设置存储服务。"
    from agent_service.services.settings_service import SettingsService

    settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
    entry = settings_service.add_system_prompt_entry(
        user_id=runtime.user_id,
        content=normalized_content,
    )
    return f"已写入长期规则: {entry['prompt_id']}"


def _build_knowledge_service():
    """从当前工具运行时构建 KnowledgeLibraryService 实例。"""
    from agent_service.services.knowledge_library_service import KnowledgeLibraryService
    from agent_service.services.settings_service import SettingsService

    runtime = get_tool_runtime()
    if runtime.memory_service is None:
        raise RuntimeError("缺少 MemoryService,无法操作知识库文件系统。")
    settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
    return KnowledgeLibraryService(
        config=runtime.config,
        memory_service=runtime.memory_service,
        settings_service=settings_service,
        embedding_service=runtime.embedding_service,
    )


def _flatten_tree(nodes: list[dict], prefix: str = "") -> list[str]:
    """递归展开文件树为路径字符串列表。"""
    lines: list[str] = []
    for node in nodes:
        full = f"{prefix}/{node['name']}" if prefix else node["name"]
        kind = "[DIR]" if node.get("isDir") else "[FILE]"
        size = f" ({node.get('size', 0)} bytes)" if not node.get("isDir") and node.get("size") else ""
        lines.append(f"  {kind} {full}{size}")
        if node.get("isDir") and node.get("children"):
            lines.extend(_flatten_tree(node["children"], full))
    return lines


def list_knowledge_files() -> str:
    """
    列出当前用户知识库的完整文件树。

    返回值: 包含文件总数统计和完整路径列表的人类可读文本。
    """

    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        tree = service.list_files(user_id=runtime.user_id)
    except Exception as exc:
        return f"列出文件失败: {exc}"
    if not tree:
        return "知识库为空,暂无任何文件或文件夹。"
    flat = _flatten_tree(tree)
    file_count = sum(1 for line in flat if line.strip().startswith("[FILE]"))
    dir_count = sum(1 for line in flat if line.strip().startswith("[DIR]"))
    summary = f"共 {file_count} 个文件, {dir_count} 个文件夹:\n"
    return summary + "\n".join(flat)


def read_knowledge_file(path: str) -> str:
    """
    读取知识库中指定文件的内容。

    path: 文件相对于知识库根目录的路径,例如 `notes/readme.md`。
    """

    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        result = service.read_file(user_id=runtime.user_id, path=path)
    except Exception as exc:
        return f"读取文件失败: {exc}"
    content = str(result.get("content", ""))
    source_uri = str(result.get("path") or path)
    citation_id = register_tool_citation(
        source_uri=source_uri,
        content=content,
        adopted_by_default=True,
    )
    prefix = f"Citation ID: [{citation_id}]\nSource: {source_uri}\n\n"
    max_chars = 6000
    if len(content) <= max_chars:
        return prefix + content
    return (
        prefix
        + content[:max_chars]
        + f"\n\n[文件内容已截断: 已返回前 {max_chars} 字符, 原文共 {len(content)} 字符。"
        "如需后续部分,请更精确地说明要查看的章节或关键词。]"
    )


def read_multimodal_file_info(path: str) -> str:
    """
    Read structured metadata and section previews from an ingested multimodal file.

    path: File path relative to the active knowledge library root, for example `docs/report.pdf`.
    """

    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        result = service.read_multimodal_file_info(user_id=runtime.user_id, path=path)
    except Exception as exc:
        return f"读取多模态文件信息失败: {exc}"
    content = json.dumps(result, ensure_ascii=False, indent=2)
    source_uri = str(result.get("path") or path) if isinstance(result, dict) else path
    citation_id = register_tool_citation(
        source_uri=source_uri,
        content=content,
        adopted_by_default=True,
    )
    return f"Citation ID: [{citation_id}]\nSource: {source_uri}\n\n{content}"


def write_knowledge_file(path: str, content: str) -> str:
    """
    在知识库中创建或覆盖一个文本文件。

    path: 文件相对于知识库根目录的路径,例如 `notes/summary.md`。
    content: 要写入的完整文件内容。
    """

    if _is_readonly_access():
        return _deny_readonly_write("写入知识库文件")
    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        result = service.write_file(user_id=runtime.user_id, path=path, content=content)
    except Exception as exc:
        return f"写入文件失败: {exc}"
    return f"已保存文件: {result['path']} (大小: {result.get('size', 'N/A')} 字节)"


def show_markdown_html(title: str, html: str, source_path: str = "", filename: str = "") -> str:
    """
    Save generated document visualization HTML under runtime/visualizations and notify the front-end.

    title: Human-readable title shown by the front-end visualization panel.
    html: Complete HTML document or HTML fragment generated from the source document.
    source_path: Optional source document path relative to the active knowledge library root.
    filename: Optional preferred output filename; it is sanitized and timestamped.
    """

    if _is_readonly_access():
        return _deny_readonly_write("generate Markdown-HTML visualization")
    clean_html = _strip_markdown_html_fence(html)
    if not clean_html:
        return "Markdown-HTML visualization failed: html is empty."

    runtime = get_tool_runtime()
    output_dir = (runtime.config.storage.base_data_dir / "visualizations").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_visualization_filename(title, source_path, filename)
    output_path = (output_dir / safe_name).resolve()
    if output_dir not in output_path.parents and output_path != output_dir:
        return "Markdown-HTML visualization failed: output path escaped runtime directory."

    try:
        output_path.write_text(clean_html, encoding="utf-8")
    except Exception as exc:
        return f"Markdown-HTML visualization failed: {exc}"

    display_title = title.strip() or source_path.strip() or safe_name
    payload = {
        "title": display_title,
        "filename": safe_name,
        "path": str(output_path),
        "url": f"/visualizations/{safe_name}",
        "source_path": source_path,
        "created_at": datetime.now().isoformat(),
    }
    callback = get_markdown_html_visualization_callback()
    if callback is not None:
        callback(payload)
    return (
        f"Markdown-HTML visualization generated and mounted: {display_title}\n"
        f"URL: {payload['url']}\n"
        f"Local path: {output_path}"
    )


def delete_knowledge_file(path: str) -> str:
    """
    删除知识库中的文件或文件夹。

    path: 文件或文件夹相对于知识库根目录的路径。
    注意: 删除文件夹会递归删除其下所有内容。
    """

    if _is_readonly_access():
        return _deny_readonly_write("删除知识库文件")
    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        service.delete_path(user_id=runtime.user_id, path=path)
    except Exception as exc:
        return f"删除失败: {exc}"
    return f"已删除: {path}"


def rename_knowledge_file(source_path: str, target_path: str) -> str:
    """
    重命名或移动知识库中的文件/文件夹。

    source_path: 当前相对路径,例如 `old_name.md`。
    target_path: 新相对路径,例如 `new_name.md` 或 `archive/new_name.md`。
    """

    if _is_readonly_access():
        return _deny_readonly_write("重命名或移动知识库文件")
    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        result = service.rename_path(user_id=runtime.user_id, source_path=source_path, target_path=target_path)
    except Exception as exc:
        return f"重命名失败: {exc}"
    return f"已重命名: {source_path} -> {result['path']}"


def create_knowledge_folder(path: str) -> str:
    """
    在知识库中创建新文件夹。

    path: 文件夹相对于知识库根目录的路径,例如 `projects/new-project`。
    """

    if _is_readonly_access():
        return _deny_readonly_write("创建知识库文件夹")
    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        result = service.create_folder(user_id=runtime.user_id, path=path)
    except Exception as exc:
        return f"创建文件夹失败: {exc}"
    return f"已创建文件夹: {result['path']}"


def save_uploaded_attachment_to_knowledge(
    attachment: str = "",
    target_path: str = "",
    conflict_strategy: str = "rename",
    ingest: bool = True,
) -> str:
    """
    Promote one session-uploaded attachment into the active knowledge library.

    attachment: Optional attachment_id, exact filename, or filename keyword. Empty means the latest session attachment.
    target_path: Optional target relative path in the active knowledge library. Empty keeps the original filename at root.
    conflict_strategy: overwrite, skip, or rename. Defaults to rename.
    ingest: Whether to immediately ingest the copied file into the knowledge index.
    """

    from pathlib import Path

    from sqlalchemy import desc
    from sqlmodel import Session, create_engine, select

    from agent_service.models.attachment import SessionAttachmentRecord

    if _is_readonly_access():
        return _deny_readonly_write("保存上传附件到知识库")
    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    normalized_attachment = attachment.strip()
    engine = create_engine(f"sqlite:///{runtime.config.storage.sqlite_path}", pool_pre_ping=True)
    statement = (
        select(SessionAttachmentRecord)
        .where(SessionAttachmentRecord.user_id == runtime.user_id)
        .where(SessionAttachmentRecord.session_id == runtime.session_id)
        .order_by(desc(SessionAttachmentRecord.created_at))
    )
    with Session(engine) as db_session:
        attachments = list(db_session.exec(statement).all())
    if not attachments:
        return "No uploaded attachments were found in the current session."

    if normalized_attachment:
        lowered = normalized_attachment.casefold()
        matches = [
            item for item in attachments
            if item.attachment_id == normalized_attachment
            or item.filename.casefold() == lowered
            or lowered in item.filename.casefold()
        ]
    else:
        matches = [attachments[0]]

    if not matches:
        available = "\n".join(f"- {item.filename} ({item.attachment_id})" for item in attachments[:8])
        return f"Attachment not found in this session. Available attachments:\n{available}"
    if len(matches) > 1:
        available = "\n".join(f"- {item.filename} ({item.attachment_id})" for item in matches[:8])
        return f"Multiple uploaded attachments matched. Please specify one attachment_id:\n{available}"

    record = matches[0]
    source_path = Path(record.path).expanduser().resolve()
    if not source_path.is_file():
        return f"Attachment file is missing from runtime uploads: {record.filename}"

    normalized_strategy = conflict_strategy.strip().lower() or "rename"
    if normalized_strategy not in {"overwrite", "skip", "rename"}:
        return "Invalid conflict_strategy. Use overwrite, skip, or rename."

    raw_target = target_path.strip().replace("\\", "/").strip("/")
    if raw_target:
        target = Path(raw_target)
        if raw_target.endswith("/"):
            relative_dir = raw_target.rstrip("/")
            target_filename = record.filename
        else:
            relative_dir = target.parent.as_posix() if str(target.parent) != "." else ""
            target_filename = target.name or record.filename
    else:
        relative_dir = ""
        target_filename = record.filename

    try:
        copied_path = service.write_uploaded_file(
            user_id=runtime.user_id,
            filename=target_filename,
            content=source_path.read_bytes(),
            relative_dir=relative_dir,
            conflict_strategy=normalized_strategy,
        )
    except Exception as exc:
        return f"Failed to copy attachment into the knowledge library: {exc}"

    root = service.get_active_root_path(user_id=runtime.user_id)
    try:
        relative_path = copied_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return f"Copied file escaped the active knowledge library: {copied_path}"

    if not ingest:
        return f"Saved uploaded attachment to knowledge library: {relative_path}. It was not ingested."

    try:
        result = service.ingest_single_file(user_id=runtime.user_id, path=relative_path)
    except Exception as exc:
        return f"Saved uploaded attachment to knowledge library as {relative_path}, but ingestion failed: {exc}"

    status = result.status_message or "ingested"
    return (
        f"Saved uploaded attachment to knowledge library: {relative_path}\n"
        f"Ingestion status: {status}\n"
        f"Files ingested: {result.files_ingested}; chunks created: {result.chunks_created}; "
        f"files skipped: {result.files_skipped}; skip reason: {result.skip_reason or 'none'}."
    )


def get_current_viewing_document() -> str:
    """
    获取当前用户在 editor 前端正在观看的文档基本信息。

    返回值只包含路径、文件名、知识库、大小、修改时间和 dirty 状态等基本信息;
    不返回文件正文。若需要正文,应继续调用 read_knowledge_file(path)。
    """

    runtime = get_tool_runtime()
    from agent_service.services.editor_context_service import editor_context_service

    info = editor_context_service.get_current_document(runtime.user_id)
    if info is None:
        return "当前没有 editor 前端上报的正在观看文档。"
    if not info.path:
        return "当前用户没有正在观看的活动文件。"
    return json.dumps(
        {
            "path": info.path,
            "name": info.name,
            "knowledge_dir": info.knowledge_dir,
            "library_id": info.library_id,
            "library_name": info.library_name,
            "size": info.size,
            "mtime": info.mtime,
            "dirty": info.dirty,
            "open_tab_count": info.open_tab_count,
            "updated_at": info.updated_at,
            "next_step_hint": "如需读取正文,请调用 read_knowledge_file 并传入 path。",
        },
        ensure_ascii=False,
    )


def web_search(
    query: str,
    max_results: int | None = None,
    region: str = "cn-zh",
    time_range: str = "",
) -> str:
    """
    通过 DuckDuckGo 搜索互联网，返回格式化的搜索结果列表。

    query: 搜索关键词。
    max_results: 最大返回结果数，不传则使用用户的配置值。
    region: 搜索区域代码，默认 cn-zh（中国中文）。
    time_range: 时间范围。d=一天内, w=一周内, m=一个月内, y=一年内。留空不限时间。
    """
    try:
        runtime = get_tool_runtime()
    except RuntimeError:
        return "搜索失败：无法获取运行上下文。"

    try:
        from agent_service.api.rest.deps import _settings_service
        if _settings_service is None:
            return "搜索失败：设置服务未就绪。"
        config = _settings_service.get_web_search_config(user_id=runtime.user_id)
    except Exception:
        return "搜索失败：无法读取搜索配置。"

    if not config.get("web_search_enabled", False):
        return "联网搜索未启用，请在设置中开启。"

    proxy_url = config.get("proxy_url", "") or ""
    configured_max = config.get("web_search_max_results", 10) or 10
    effective_max = max(1, configured_max)

    if not proxy_url:
        return "搜索失败：未配置代理地址。国内访问 DuckDuckGo 需要代理，请在设置页面的「联网搜索」中填写代理地址（如 http://127.0.0.1:7890）。"

    try:
        from ddgs import DDGS
        import time
        raw_results = []
        for attempt in range(3):
            with DDGS(proxy=proxy_url, timeout=20) as ddgs:
                raw_results = list(ddgs.text(
                    query,
                    region=region,
                    max_results=effective_max * 2,
                    timelimit=time_range if time_range else None,
                ))
            if raw_results:
                break
            if attempt < 2:
                time.sleep(1)
    except Exception as exc:
        return f"搜索失败: {exc}"

    if not raw_results:
        return "未搜索到相关结果。"

    seen_hrefs: set[str] = set()
    filtered: list[dict] = []
    for item in raw_results:
        href = (item.get("href") or "").strip()
        title = (item.get("title") or "").strip()
        body = (item.get("body") or "").strip()
        if not href or not title or not body:
            continue
        if href in seen_hrefs:
            continue
        if len(body) < 10:
            continue
        seen_hrefs.add(href)
        filtered.append(item)
        if len(filtered) >= effective_max:
            break

    if not filtered:
        return "未搜索到相关结果。"

    # Try to fetch full page text for each result, fall back to DDGS snippet on failure
    import html as html_mod
    import re as re_mod
    import urllib.request as url_req

    def extract_page_text(url: str, fallback: str) -> str:
        """Fetch a URL and extract readable text. Returns fallback on any failure."""
        try:
            req = url_req.Request(url, headers={"User-Agent": "MetaWeave/1.0"})
            with url_req.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # Strip HTML tags
            text = re_mod.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re_mod.DOTALL | re_mod.IGNORECASE)
            text = re_mod.sub(r"<style[^>]*>.*?</style>", "", text, flags=re_mod.DOTALL | re_mod.IGNORECASE)
            text = re_mod.sub(r"<[^>]+>", " ", text)
            text = html_mod.unescape(text)
            # Collapse whitespace
            text = re_mod.sub(r"\s+", " ", text).strip()
            # Truncate to reasonable length
            if len(text) > 3000:
                text = text[:3000] + "..."
            if len(text) < 50:
                return fallback
            return text
        except Exception:
            return fallback

    lines: list[str] = []
    for i, item in enumerate(filtered, 1):
        title = item.get("title", "").strip()
        href = item.get("href", "").strip()
        body = item.get("body", "").strip()
        full_text = extract_page_text(href, body)
        citation_id = register_network_citation(
            source_uri=href,
            content=full_text,
            title=title,
            adopted_by_default=False,
        )
        lines.append(f"{i}. {title}")
        lines.append(f"   Citation ID: [{citation_id}]")
        lines.append(f"   URL: {href}")
        lines.append(f"   摘要: {full_text}")
        if i < len(filtered):
            lines.append("")
    lines.append("")
    lines.append("Citation rule: only cite a result with its exact [N#] id when facts from that result are used in the final answer.")
    return "\n".join(lines)


def web_image_search(
    query: str,
    max_results: int | None = None,
    region: str = "cn-zh",
) -> str:
    """
    通过 DuckDuckGo 搜索图片，返回图片结果列表（含图片 URL、标题、来源页面）。

    query: 搜索关键词。
    max_results: 最大返回结果数，不传则使用用户的配置值。
    region: 搜索区域代码，默认 cn-zh（中国中文）。
    """
    try:
        runtime = get_tool_runtime()
    except RuntimeError:
        return "搜索失败：无法获取运行上下文。"

    try:
        from agent_service.api.rest.deps import _settings_service
        if _settings_service is None:
            return "搜索失败：设置服务未就绪。"
        config = _settings_service.get_web_search_config(user_id=runtime.user_id)
    except Exception:
        return "搜索失败：无法读取搜索配置。"

    if not config.get("web_search_enabled", False):
        return "联网搜索未启用，请在设置中开启。"

    proxy_url = config.get("proxy_url", "") or ""
    configured_max = config.get("web_search_max_results", 10) or 10
    effective_max = max(1, configured_max)

    if not proxy_url:
        return "搜索失败：未配置代理地址。国内访问 DuckDuckGo 需要代理，请在设置页面的「联网搜索」中填写代理地址（如 http://127.0.0.1:7890）。"

    try:
        from ddgs import DDGS
        import time
        raw_results = []
        for attempt in range(3):
            with DDGS(proxy=proxy_url, timeout=20) as ddgs:
                raw_results = list(ddgs.images(
                    query,
                    region=region,
                    max_results=effective_max,
                ))
            if raw_results:
                break
            if attempt < 2:
                time.sleep(1)
    except Exception as exc:
        return f"图片搜索失败: {exc}"

    if not raw_results:
        return "未搜索到相关图片结果。"

    seen_image_urls: set[str] = set()
    filtered: list[dict] = []
    for item in raw_results:
        image_url = (item.get("image") or "").strip()
        title = (item.get("title") or "").strip()
        source_url = (item.get("url") or "").strip()
        if not image_url or not title:
            continue
        if image_url in seen_image_urls:
            continue
        seen_image_urls.add(image_url)
        filtered.append(item)
        if len(filtered) >= effective_max:
            break

    if not filtered:
        return "未搜索到相关图片结果。"

    lines: list[str] = []
    for i, item in enumerate(filtered, 1):
        title = item.get("title", "").strip()
        image_url = item.get("image", "").strip()
        source_url = item.get("url", "").strip()
        thumbnail_url = item.get("thumbnail", "").strip()

        citation_id = register_network_citation(
            source_uri=source_url,
            content=f"图片标题: {title}\n图片 URL: {image_url}",
            title=title,
            adopted_by_default=False,
        )
        lines.append(f"{i}. {title}")
        lines.append(f"   Citation ID: [{citation_id}]")
        lines.append(f"   图片地址: {image_url}")
        lines.append(f"   缩略图: {thumbnail_url}")
        lines.append(f"   来源页面: {source_url}")
        lines.append(f"   Markdown展示: ![{title}]({image_url})")
        if i < len(filtered):
            lines.append("")

    lines.append("")
    lines.append("Citation rule: only cite a result with its exact [N#] id when facts from that result are used in the final answer.")
    return "\n".join(lines)


def _get_task_list_service():
    """Return the current task list service."""

    runtime = get_tool_runtime()
    if runtime.task_list_service is not None:
        return runtime.task_list_service
    try:
        from agent_service.api.rest.deps import _task_list_service
        if _task_list_service is not None:
            return _task_list_service
    except Exception:
        pass
    raise RuntimeError("TaskListService is not initialized.")


def _emit_task_list_update(task_list: dict[str, Any] | None) -> None:
    """Notify the current Agent stream that task list state changed."""

    callback = get_task_list_callback()
    if callback is not None:
        callback(task_list)


def get_task_list_status() -> str:
    """
    Read the current session task list without changing its state.

    Use this when the Agent needs to confirm item ids, current progress, or
    completion summaries before continuing a long-running task list.
    """

    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.get_task_list(runtime.session_id)
    if task_list is None:
        return "No task list exists for this session."
    items = task_list.get("items", [])
    completed_count = len([item for item in items if isinstance(item, dict) and item.get("status") == "completed"])
    lines = [
        f"Task list: {task_list.get('title') or 'Task list'}",
        f"Status: {task_list.get('status') or 'active'}",
        f"Current item id: {task_list.get('current_item_id') or 'none'}",
        f"Progress: {completed_count}/{len(items) if isinstance(items, list) else 0}",
    ]
    if isinstance(items, list) and items:
        lines.append("Items:")
        for item in items:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('id')}: [{item.get('status') or 'pending'}] {item.get('title') or ''}"
            )
            summary = str(item.get("completion_summary") or "").strip()
            if summary:
                lines.append(f"  completion_summary: {summary}")
    final_summary = str(task_list.get("final_summary") or "").strip()
    if final_summary:
        lines.append(f"Final summary: {final_summary}")
    return "\n".join(lines)


def create_task_list(title: str = "", items: list[Any] | str | None = None) -> str:
    """
    Create a session-scoped task list for complex long-running work.

    title: short task list title.
    items: ordered task titles, or a newline-separated string.
    """

    if isinstance(items, str):
        parsed_items = [line.strip("- 	") for line in items.splitlines() if line.strip("- \t")]
    elif isinstance(items, list):
        parsed_items = [str(item).strip() for item in items if str(item).strip()]
    else:
        parsed_items = []
    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.create_task_list(
        session_id=runtime.session_id,
        title=title,
        items=parsed_items,
    )
    _emit_task_list_update(task_list)
    current = next((item for item in task_list["items"] if item.get("id") == task_list.get("current_item_id")), None)
    current_title = current.get("title") if current else "none"
    return f"Task list created with {len(task_list['items'])} items. Current item: {current_title}"


def complete_task_list_item(item_id: str, completion_summary: str, next_item_id: str | None = None) -> str:
    """
    Mark a task list item complete and record the completion summary.

    item_id: task list item id.
    completion_summary: concrete summary of what was completed.
    next_item_id: optional next item to make current.
    """

    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.complete_task_list_item(
        session_id=runtime.session_id,
        item_id=item_id,
        completion_summary=completion_summary,
        next_item_id=next_item_id,
    )
    _emit_task_list_update(task_list)
    remaining = len([item for item in task_list.get("items", []) if item.get("status") != "completed"])
    return f"Task list item completed. Remaining items: {remaining}"


def finish_task_list(final_summary: str = "") -> str:
    """
    Finish the active session task list after all useful work is complete.

    final_summary: optional overall completion summary.
    """

    service = _get_task_list_service()
    runtime = get_tool_runtime()
    task_list = service.finish_task_list(session_id=runtime.session_id, final_summary=final_summary)
    _emit_task_list_update(task_list)
    return "Task list finished."


def _get_todo_service() -> TodoService:
    """获取 TodoService 实例。"""
    runtime = get_tool_runtime()
    if not runtime.config:
        raise RuntimeError("ToolRuntime.config 未初始化，无法创建 TodoService")
    data_dir = str(runtime.config.storage.base_data_dir)
    return TodoService(data_dir=data_dir)


def list_todos() -> str:
    """
    列出当前用户的所有待办事项。返回格式化的待办列表,每行包含编号、ID、完成状态和截止日期。
    Agent 应当从输出中提取每个待办的 ID(格式为 todo_xxx)来调用 toggle_todo/edit_todo/delete_todo。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    items = service.list_todos(user_id=runtime.user_id)
    if not items:
        return "当前没有待办事项。"
    lines = []
    for i, item in enumerate(items, 1):
        status = "✅" if item.get("done") else "⬜"
        tid = item["id"]
        due = f" [截止: {item['dueDate']}]" if item.get("dueDate") else ""
        lines.append(f"{i}. [{tid}] {status} {item['text']}{due}")
    return "\n".join(lines)


def add_todo(text: str, due_date: str | None = None) -> str:
    """
    新增一条待办事项。

    text: 待办事项的文字描述。
    due_date: 可选截止日期,格式 YYYY-MM-DD。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    item = service.add_todo(user_id=runtime.user_id, text=text, due_date=due_date)
    due = f", 截止日期: {item['dueDate']}" if item.get("dueDate") else ""
    return f"已创建待办 [{item['id']}]: {item['text']}{due}"


def toggle_todo(todo_id: str) -> str:
    """
    切换待办事项的完成状态(已完成↔未完成)。

    todo_id: 待办的唯一 ID,可通过 list_todos 获取。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    item = service.toggle_todo(user_id=runtime.user_id, todo_id=todo_id)
    if item is None:
        return f"未找到 ID 为 {todo_id} 的待办事项。"
    status = "已完成" if item.get("done") else "未完成"
    return f"已切换待办 [{item['id']}] 状态为: {status} — {item['text']}"


def edit_todo(todo_id: str, text: str | None = None, due_date: str | None = None) -> str:
    """
    编辑待办事项的文本或截止日期。

    todo_id: 待办的唯一 ID,可通过 list_todos 获取。
    text: 新的待办文本。留空则不修改。
    due_date: 新的截止日期(YYYY-MM-DD),传入空字符串可清除截止日期,不传则不修改。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    # 先获取当前项
    items = service.list_todos(user_id=runtime.user_id)
    current = next((item for item in items if item.get("id") == todo_id), None)
    if current is None:
        return f"未找到 ID 为 {todo_id} 的待办事项。"
    final_text = current["text"]
    if text:
        stripped = text.strip()
        if stripped:
            final_text = stripped
    final_due = current.get("dueDate")
    if due_date is not None:
        final_due = due_date
    item = service.edit_todo(user_id=runtime.user_id, todo_id=todo_id, text=final_text, due_date=final_due)
    if item is None:
        return f"编辑待办失败。"
    parts = [f"已更新待办: {item['text']}"]
    if item.get("dueDate"):
        parts.append(f"截止日期: {item['dueDate']}")
    return " | ".join(parts)


def delete_todo(todo_id: str) -> str:
    """
    删除指定的待办事项。

    todo_id: 待办的唯一 ID,可通过 list_todos 获取。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    if service.delete_todo(user_id=runtime.user_id, todo_id=todo_id):
        return f"已删除待办: {todo_id}"
    return f"未找到 ID 为 {todo_id} 的待办事项。"


def get_knowledge_file_url(path: str) -> str:
    """
    获取知识库中本地文件的浏览器可访问 URL。用于在回复中以 Markdown 图片或链接形式引用知识库文件。

    path: 文件相对于知识库根目录的路径。
    """

    runtime = get_tool_runtime()
    return f"/knowledge/files/raw?user_id={runtime.user_id}&path={path}"


def _get_git_service():
    """返回应用启动阶段注入的统一 GitService。"""

    from agent_service.api.rest.deps import _git_service

    if _git_service is None:
        raise RuntimeError("GitService 尚未初始化。")
    return _git_service


def _require_git_write_access() -> Any:
    """校验当前 Agent 不是只读模式并返回运行时上下文。"""

    from agent_service.tools.runtime_context import AGENT_ACCESS_READONLY

    runtime = get_tool_runtime()
    if runtime.agent_access_mode == AGENT_ACCESS_READONLY:
        raise PermissionError("当前 Agent 处于只读模式,不能执行 Git 写操作。")
    return runtime


def git_status() -> str:
    """读取当前知识库的结构化 Git 状态。"""

    import json

    runtime = get_tool_runtime()
    payload = _get_git_service().get_status(user_id=runtime.user_id)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_diff(path: str = "", staged: bool = False) -> str:
    """
    读取当前知识库的 Git diff。

    path: 可选知识库相对路径,为空时返回全部差异。
    staged: 是否读取暂存区差异。
    """

    runtime = get_tool_runtime()
    payload = _get_git_service().get_diff(
        user_id=runtime.user_id,
        path=path,
        staged=staged,
    )
    return str(payload.get("diff") or "没有差异。")


def git_history(limit: int = 30) -> str:
    """读取提交历史、未推送提交和文件。"""

    import json

    runtime = get_tool_runtime()
    payload = _get_git_service().get_history(user_id=runtime.user_id, limit=limit)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_init_repository(initial_branch: str = "main") -> str:
    """在当前知识库根目录初始化 Git 仓库。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().initialize_repository(
        user_id=runtime.user_id,
        initial_branch=initial_branch,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_restore_files(paths: list[str]) -> str:
    """
    回滚已跟踪文件并将未跟踪文件移入 MetaWeave 最近删除。

    paths: 需要回滚的知识库相对路径列表。
    """

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().restore_paths(user_id=runtime.user_id, paths=paths)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_commit_files(paths: list[str], message: str) -> str:
    """暂存选中文件并创建本地提交。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().commit(
        user_id=runtime.user_id,
        paths=paths,
        message=message,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_push_branch(
    local_branch: str,
    remote: str,
    remote_branch: str,
    confirm: bool = False,
    force_with_lease: bool = False,
    confirm_force: bool = False,
    all_branches: bool = False,
) -> str:
    """
    推送分支到远程。

    confirm: 用户是否明确确认普通推送。
    force_with_lease: 是否使用带租约的安全强推。
    confirm_force: 用户是否明确确认高风险覆盖远端历史。
    all_branches: 是否忽略单分支映射并推送全部本地分支。
    """

    import json

    runtime = _require_git_write_access()
    if not confirm:
        raise PermissionError("推送会修改远程仓库,必须先获得用户明确确认并传入 confirm=true。")
    if force_with_lease and not confirm_force:
        raise PermissionError("force-with-lease 需要单独确认并传入 confirm_force=true。")
    payload = _get_git_service().push(
        user_id=runtime.user_id,
        local_branch=local_branch,
        remote=remote,
        remote_branch=remote_branch,
        force_with_lease=force_with_lease,
        all_branches=all_branches,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_create_branch(name: str, checkout: bool = True) -> str:
    """创建本地分支,可选择立即切换。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().create_branch(
        user_id=runtime.user_id,
        name=name,
        checkout=checkout,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_add_remote(name: str, url: str) -> str:
    """
    为当前知识库 Git 仓库新增命名远程。

    name: 远程名称,例如 origin。
    url: HTTPS、SSH 或本地 Git 仓库地址。
    """

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().add_remote(
        user_id=runtime.user_id,
        name=name,
        url=url,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_switch_branch(name: str) -> str:
    """切换本地分支并清理受影响知识文件的旧索引。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().switch_branch(user_id=runtime.user_id, name=name)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def git_pull_branch(remote: str, branch: str) -> str:
    """获取并快进合并远程分支,拒绝隐式合并提交。"""

    import json

    runtime = _require_git_write_access()
    payload = _get_git_service().pull_fast_forward(
        user_id=runtime.user_id,
        remote=remote,
        branch=branch,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def download_file(url: str, save_to_knowledge: bool = False) -> str:
    """
    从网络下载文件并存储到本地。可选的 save_to_knowledge=True 可将下载的文件复制到知识库并灌库。

    url: 需要下载的文件的完整 URL。
    save_to_knowledge: 是否将下载后的文件复制到知识库并灌库。默认 False。
    """

    import uuid
    import urllib.request

    runtime = get_tool_runtime()
    downloads_dir = runtime.config.storage.assets_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetaWeave/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type", "")
    except Exception as exc:
        return f"下载失败: {exc}"

    ext = _infer_extension(content_type, url)
    filename = f"{uuid.uuid4().hex}{ext}"
    local_path = downloads_dir / filename
    local_path.write_bytes(content)
    local_url = f"/downloads/{filename}"

    if not save_to_knowledge:
        return (
            f"文件已下载到本地。预览: ![]({local_url})\n\n"
            f"本地 URL: {local_url}\n"
            f"文件名: {filename}\n"
            f"类型: {content_type}\n"
            f"大小: {len(content)} 字节"
        )

    # Copy to knowledge library and ingest
    try:
        from agent_service.services.knowledge_library_service import KnowledgeLibraryService
        from agent_service.services.settings_service import SettingsService

        if runtime.memory_service is None:
            return "下载成功,但无法保存到知识库: 当前工具运行时缺少记忆写入服务。"

        settings_service = SettingsService(config=runtime.config, memory_service=runtime.memory_service)
        knowledge_service = KnowledgeLibraryService(
            config=runtime.config,
            memory_service=runtime.memory_service,
            settings_service=settings_service,
            embedding_service=runtime.embedding_service,
        )

        uploaded_path = knowledge_service.write_uploaded_file(
            user_id=runtime.user_id,
            filename=filename,
            content=content,
            relative_dir="",
            conflict_strategy="rename",
        )
        root = knowledge_service.get_active_root_path(user_id=runtime.user_id)
        relative_path = uploaded_path.resolve().relative_to(root.resolve()).as_posix()
        result = knowledge_service.ingest_single_file(user_id=runtime.user_id, path=relative_path)
        status = result.status_message or "ingested"

        return (
            f"文件已下载并存入知识库。预览: ![]({local_url})\n\n"
            f"本地 URL: {local_url}\n"
            f"知识库路径: {relative_path}\n"
            f"灌库状态: {status}\n"
            f"类型: {content_type}\n"
            f"大小: {len(content)} 字节"
        )
    except Exception as exc:
        return (
            f"文件已下载到本地,但存入知识库失败: {exc}\n"
            f"本地 URL: {local_url}\n"
            f"大小: {len(content)} 字节"
        )


def _infer_extension(content_type: str, url: str) -> str:
    """从 Content-Type 或 URL 后缀推断文件扩展名。"""

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "image/bmp": ".bmp",
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/html": ".html",
        "text/csv": ".csv",
        "application/json": ".json",
        "application/zip": ".zip",
    }
    for ct, ext in ext_map.items():
        if content_type.startswith(ct):
            return ext
    # Fallback: extract from URL
    import pathlib
    url_ext = pathlib.Path(url.split("?")[0].split("#")[0]).suffix
    if url_ext and len(url_ext) <= 6:
        return url_ext
    return ".bin"


from agent_service.tools.definitions import (  # noqa: E402
    BUILTIN_TOOL_DEFINITIONS,
    FILE_TOOL_DEFINITIONS,
    KNOWLEDGE_TOOL_DEFINITIONS,
    MEMORY_TOOL_DEFINITIONS,
    TODO_TOOL_DEFINITIONS,
    UTILITY_TOOL_DEFINITIONS,
    WEB_SEARCH_TOOL_DEFINITIONS,
)
