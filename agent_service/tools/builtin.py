"""
内置工具定义模块。

功能说明:
本文件只负责书写项目自带的小工具函数,不负责工具注册和工具执行。工具注册由
`tool_registry.py` 完成,工具执行由 `executor.py` 完成。

工具分为多个类别,分别存放在独立的分组列表中:
- UTILITY_TOOL_DEFINITIONS  通用工具 (时间、UUID、计算、JSON、文本统计等)
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
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_service.tools.runtime_context import (
    AGENT_ACCESS_READONLY,
    get_plan_state,
    get_tool_runtime,
    register_network_citation,
    register_tool_citation,
    set_plan_state,
)
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.todo_service import TodoService
from agent_service.tools.tool_math import evaluate_math_expression


ToolFunction = Callable[..., str]


def _is_readonly_access() -> bool:
    """判断当前工具运行时是否处于只读权限模式。"""

    return get_tool_runtime().agent_access_mode == AGENT_ACCESS_READONLY


def _deny_readonly_write(action: str) -> str:
    """返回 Agent 只读权限下统一的写操作拒绝信息。"""

    return f"权限不足: 当前 Agent 权限为只读,已禁止{action}。请切换到沙盒或完全访问后重试。"


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


def get_current_utc_time() -> str:
    """
    获取当前 UTC 时间。

    返回值: ISO 8601 格式 UTC 时间字符串。
    """

    return datetime.now(timezone.utc).isoformat()


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


def echo_text(text: str) -> str:
    """
    原样返回输入文本。

    text: 需要回显的文本。
    """

    return text


def generate_uuid() -> str:
    """
    生成随机 UUID。

    返回值: UUID4 字符串,可用于临时任务 ID、调试 ID 或幂等标识。
    """

    return str(uuid4())


def calculate(expression: str) -> str:
    """
    安全计算基础数学表达式。

    expression: 只允许数字、括号、加减乘除、取模、幂和一元正负号。
    """

    try:
        result = evaluate_math_expression(expression)
    except Exception as exc:
        return f"计算失败: {exc}"
    return str(result)


def json_parse(json_text: str) -> str:
    """
    解析 JSON 字符串并返回结构化描述。

    json_text: 需要解析的 JSON 字符串。
    """

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return f"JSON 解析失败: 第 {exc.lineno} 行第 {exc.colno} 列: {exc.msg}"
    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        summary = f"JSON 解析成功,这是一个包含 {len(keys)} 个字段的对象"
        if len(keys) <= 10:
            summary += f",字段: {', '.join(keys)}"
        else:
            summary += f",主要字段: {', '.join(keys[:10])} 等"
        return summary + "。"
    if isinstance(parsed, list):
        summary = f"JSON 解析成功,这是一个包含 {len(parsed)} 个元素的数组"
        if parsed and isinstance(parsed[0], dict):
            summary += f",每个元素是包含 {len(parsed[0])} 个字段的对象"
        return summary + "。"
    return f"JSON 解析成功,值为: {parsed}"


def json_pick(json_text: str, path: str) -> str:
    """
    从 JSON 字符串中按简单路径取值,返回人类可读的描述。

    json_text: 需要读取的 JSON 字符串。
    path: 点分路径,例如 `user.name` 或 `items.0.title`。
    """

    try:
        current_value: Any = json.loads(json_text)
        for segment in path.split("."):
            if isinstance(current_value, list):
                current_value = current_value[int(segment)]
            elif isinstance(current_value, dict):
                current_value = current_value[segment]
            else:
                return f"路径 {path} 在 {segment} 处无法继续读取。"
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
        return f"JSON 取值失败: {exc}"
    if isinstance(current_value, (dict, list)):
        kind = "对象" if isinstance(current_value, dict) else "数组"
        return f"路径 {path} 的值是一个{kind},包含 {len(current_value)} 个元素。"
    if isinstance(current_value, str) and len(str(current_value)) > 200:
        return f"路径 {path} 的值是一段文本,共 {len(current_value)} 个字符。"
    return f"路径 {path} 的值为: {current_value}"


def text_stats(text: str) -> str:
    """
    统计文本基础信息,返回人类可读的统计结果。

    text: 需要统计的文本。
    """

    chars = len(text)
    non_ws = len("".join(text.split()))
    lines = 0 if text == "" else text.count("\n") + 1
    words = len(text.split())
    tokens = max(1, len(text) // 4) if text else 0
    return f"文本统计: {chars} 个字符, {non_ws} 个非空白字符, {lines} 行, {words} 个词, 约 {tokens} 个 token。"


def list_builtin_tools() -> str:
    """
    列出当前注册的内置工具,返回人类可读的编号列表。

    返回值: 工具名称和描述的格式化文本。
    """

    lines = [f"当前可用工具共 {len(BUILTIN_TOOL_DEFINITIONS)} 个:"]
    for i, definition in enumerate(BUILTIN_TOOL_DEFINITIONS, 1):
        lines.append(f"{i}. {definition.name} — {definition.description}")
    return "\n".join(lines)


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
    max_results: int = 5,
    region: str = "cn-zh",
    time_range: str = "",
) -> str:
    """
    通过 DuckDuckGo 搜索互联网，返回格式化的搜索结果列表。

    query: 搜索关键词。
    max_results: 最大返回结果数，默认 5。
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
                    max_results=max_results * 2,
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
        if len(filtered) >= max_results:
            break

    if not filtered:
        return "未搜索到相关结果。"

    lines: list[str] = []
    for i, item in enumerate(filtered, 1):
        title = item.get("title", "").strip()
        href = item.get("href", "").strip()
        body = item.get("body", "").strip()
        citation_id = register_network_citation(
            source_uri=href,
            content=body,
            title=title,
            adopted_by_default=False,
        )
        lines.append(f"{i}. {title}")
        lines.append(f"   Citation ID: [{citation_id}]")
        lines.append(f"   URL: {href}")
        lines.append(f"   摘要: {body}")
        if i < len(filtered):
            lines.append("")
    lines.append("")
    lines.append("Citation rule: only cite a result with its exact [N#] id when facts from that result are used in the final answer.")
    return "\n".join(lines)


def update_exploration_state(
    covered: str = "",
    suggested: str = "",
    sufficient: str = "",
    hint: str = "",
) -> str:
    """
    更新 Agent 自身的知识探索状态,供跨轮持续追踪探索进度。

    covered: 逗号分隔的已覆盖主题。
    suggested: 逗号分隔的建议继续探索方向。
    sufficient: 当前信息是否足够回答用户问题,true/false。
    hint: 给后续轮次的一两句策略提示。
    """

    state = get_plan_state() or {"covered": [], "suggested": [], "sufficient": False, "hint": ""}
    if covered:
        new_covered = [c.strip() for c in covered.split(",") if c.strip()]
        existing = state.get("covered", [])
        for c in new_covered:
            if c not in existing:
                existing.append(c)
        state["covered"] = existing
    if suggested:
        state["suggested"] = [s.strip() for s in suggested.split(",") if s.strip()]
    if sufficient:
        state["sufficient"] = sufficient.strip().lower() == "true"
    if hint:
        state["hint"] = hint.strip()
    set_plan_state(state)
    covered_count = len(state.get("covered", []))
    return (
        f"探索状态已更新。已覆盖 {covered_count} 个主题"
        + (f", 信息充足" if state.get("sufficient") else "")
        + "。"
    )


def _get_todo_service() -> TodoService:
    """获取 TodoService 实例。"""
    runtime = get_tool_runtime()
    data_dir = runtime.config.project_root if runtime.config else None
    return TodoService(data_dir=data_dir)


def list_todos() -> str:
    """
    列出当前用户的所有待办事项。返回格式化的待办列表,包含编号、完成状态、截止日期。
    """

    runtime = get_tool_runtime()
    service = _get_todo_service()
    items = service.list_todos(user_id=runtime.user_id)
    if not items:
        return "当前没有待办事项。"
    lines = []
    for i, item in enumerate(items, 1):
        status = "✅" if item.get("done") else "⬜"
        due = f" [截止: {item['dueDate']}]" if item.get("dueDate") else ""
        lines.append(f"{i}. {status} {item['text']}{due}")
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
    return f"已创建待办: {item['text']}{due}"


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
    final_text = text if text is not None else current["text"]
    final_due = current.get("dueDate")
    if due_date is not None:
        final_due = due_date if due_date else None
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


from agent_service.tools.definitions import (  # noqa: E402
    BUILTIN_TOOL_DEFINITIONS,
    FILE_TOOL_DEFINITIONS,
    KNOWLEDGE_TOOL_DEFINITIONS,
    MEMORY_TOOL_DEFINITIONS,
    STATE_TOOL_DEFINITIONS,
    TODO_TOOL_DEFINITIONS,
    UTILITY_TOOL_DEFINITIONS,
    WEB_SEARCH_TOOL_DEFINITIONS,
)
