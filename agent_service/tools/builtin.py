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

import ast
import json
import operator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_service.tools.runtime_context import get_plan_state, get_tool_runtime, set_plan_state
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate


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
        result = _evaluate_math_expression(ast.parse(expression, mode="eval").body)
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
        lines.append(f"{i}. (来源: {source}) {item.memory.content}")
    return "\n\n".join(lines)


def rebuild_knowledge_base(knowledge_dir: str = "") -> str:
    """
    主动重新扫描当前用户的知识库并灌入向量库。

    knowledge_dir: 可选新知识库目录;为空时使用当前用户设置中的目录。
    """

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
            lines.append(f"  {_os.path.basename(uri)}")
            if snippet:
                lines.append(f"    片段: {snippet}")
    if semantic_results:
        lines.append("=== 语义匹配 ===")
        for r in semantic_results:
            uri = str(r.get("source_uri") or "")
            content = str(r.get("content") or "")
            lines.append(f"  {_os.path.basename(uri)}")
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


def _evaluate_math_expression(node: ast.AST) -> int | float:
    """
    递归计算经过 AST 白名单校验的数学表达式。

    node: `ast.parse(..., mode="eval").body` 返回的表达式节点。
    """

    binary_operators: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    unary_operators: dict[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in binary_operators:
        left_value = _evaluate_math_expression(node.left)
        right_value = _evaluate_math_expression(node.right)
        return binary_operators[type(node.op)](left_value, right_value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in unary_operators:
        return unary_operators[type(node.op)](_evaluate_math_expression(node.operand))
    raise ValueError("表达式包含不允许的内容。")


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
    return result["content"]


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
    return json.dumps(result, ensure_ascii=False, indent=2)


def write_knowledge_file(path: str, content: str) -> str:
    """
    在知识库中创建或覆盖一个文本文件。

    path: 文件相对于知识库根目录的路径,例如 `notes/summary.md`。
    content: 要写入的完整文件内容。
    """

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

    runtime = get_tool_runtime()
    service = _build_knowledge_service()
    try:
        result = service.create_folder(user_id=runtime.user_id, path=path)
    except Exception as exc:
        return f"创建文件夹失败: {exc}"
    return f"已创建文件夹: {result['path']}"


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


# ------------------------------------------------------------------
# 通用工具
# ------------------------------------------------------------------
UTILITY_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_current_utc_time",
        description="获取当前 UTC 时间。当用户询问当前时间或需要时间戳时使用。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=get_current_utc_time,
        display_name="获取UTC时间",
    ),
    BuiltinToolDefinition(
        name="get_current_time",
        description="获取指定 IANA 时区的当前时间。默认使用 UTC。",
        args_schema={
            "type": "object",
            "properties": {
                "timezone_name": {
                    "type": "string",
                    "description": "IANA 时区名称,例如 UTC、Asia/Shanghai。",
                }
            },
            "required": [],
        },
        function=get_current_time,
        display_name="获取当前时间",
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
        display_name="回显文本",
    ),
    BuiltinToolDefinition(
        name="generate_uuid",
        description="生成随机 UUID4 字符串,用于临时标识或调试标识。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=generate_uuid,
        display_name="生成UUID",
    ),
    BuiltinToolDefinition(
        name="calculate",
        description="安全计算基础数学表达式,只支持数字和基础算术运算。",
        args_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式,例如 (1 + 2) * 3。",
                }
            },
            "required": ["expression"],
        },
        function=calculate,
        display_name="数学计算",
    ),
    BuiltinToolDefinition(
        name="json_parse",
        description="解析 JSON 字符串,返回结构化描述(字段列表/元素数量等),不返回原始 JSON。",
        args_schema={
            "type": "object",
            "properties": {
                "json_text": {
                    "type": "string",
                    "description": "需要解析的 JSON 字符串。",
                }
            },
            "required": ["json_text"],
        },
        function=json_parse,
        display_name="解析JSON",
    ),
    BuiltinToolDefinition(
        name="json_pick",
        description="从 JSON 字符串中按点分路径读取字段值,返回人类可读的值描述。",
        args_schema={
            "type": "object",
            "properties": {
                "json_text": {
                    "type": "string",
                    "description": "需要读取的 JSON 字符串。",
                },
                "path": {
                    "type": "string",
                    "description": "点分路径,例如 user.name 或 items.0.title。",
                },
            },
            "required": ["json_text", "path"],
        },
        function=json_pick,
        display_name="提取JSON字段",
    ),
    BuiltinToolDefinition(
        name="text_stats",
        description="统计文本字符数、非空白字符数、行数、词数和粗略 token 数,返回人类可读的统计结果。",
        args_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "需要统计的文本。",
                }
            },
            "required": ["text"],
        },
        function=text_stats,
        display_name="文本统计",
    ),
    BuiltinToolDefinition(
        name="list_builtin_tools",
        description="列出当前注册的全部内置工具名称和描述。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=list_builtin_tools,
        display_name="列出工具",
    ),
]

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
        lines.append(f"{i}. {title}")
        lines.append(f"   URL: {href}")
        lines.append(f"   摘要: {body}")
        if i < len(filtered):
            lines.append("")
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


# ------------------------------------------------------------------
# 长期记忆工具
# ------------------------------------------------------------------
MEMORY_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_long_term_memory",
        description="检索当前用户在长期记忆中的相关摘要信息,用于跨轮对话回忆项目目标、约束、偏好和历史事实。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要检索的记忆查询文本。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "最多返回多少条结果,默认 3。",
                },
            },
            "required": ["query"],
        },
        function=get_long_term_memory,
        display_name="检索记忆",
    ),
    BuiltinToolDefinition(
        name="write_long_term_memory",
        description="向当前用户的长期记忆中写入一条记录,包含向量化后可被后续对话检索召回。可用于手动存储重要信息、项目代号、用户偏好等需要跨会话持久化的内容。",
        args_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "需要记忆的内容,建议简洁完整,以便后续检索。",
                },
                "memory_type": {
                    "type": "string",
                    "description": "记忆子类型,默认 important_fact_summary。一般无需修改。",
                },
                "importance": {
                    "type": "number",
                    "description": "重要性(0~1),默认 0.5。0~0.3 为低,0.4~0.6 为中,0.7~1.0 为高。",
                },
                "authority": {
                    "type": "number",
                    "description": "权威性(0~1),默认 0.5。",
                },
            },
            "required": ["content"],
        },
        function=write_long_term_memory,
        display_name="写入记忆",
    ),
    BuiltinToolDefinition(
        name="write_long_term_rule",
        description="向当前用户的长期系统规则中追加一条必须遵守的指令,效果等同于用户在设置页手动添加系统提示词。该规则每轮都会注入系统提示词,不依赖 RAG 召回。仅用于用户明确要求长期遵守的规则、偏好、约束或工作规范。",
        args_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "需要长期遵守的规则内容。应写成明确、可执行的系统指令,例如“以后回答默认使用中文”。",
                }
            },
            "required": ["content"],
        },
        function=write_long_term_rule,
        display_name="写入长期规则",
    ),
]

# ------------------------------------------------------------------
# 知识库工具
# ------------------------------------------------------------------
KNOWLEDGE_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_knowledge_context",
        description="检索知识库中的相关片段,用于回答事实性、说明性和文档型问题。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "需要检索的知识查询文本。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "最多返回多少条结果,默认 3。",
                },
            },
            "required": ["query"],
        },
        function=get_knowledge_context,
        display_name="检索知识",
    ),
    BuiltinToolDefinition(
        name="rebuild_knowledge_base",
        description="主动重新扫描当前用户的本地知识库并灌入向量库。用户要求刷新、重建、重新灌库或切换知识库目录后使用。",
        args_schema={
            "type": "object",
            "properties": {
                "knowledge_dir": {
                    "type": "string",
                    "description": "可选的新知识库目录。为空时使用当前用户设置里的知识库目录。",
                }
            },
            "required": [],
        },
        function=rebuild_knowledge_base,
        display_name="重建知识库",
    ),
    BuiltinToolDefinition(
        name="search_knowledge",
        description="在用户知识库中联合搜索文件,支持文件名匹配、全文内容匹配和语义搜索。当用户需要根据关键词或语义描述在知识库中查找特定文件时使用。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或语义描述文本。",
                },
                "fulltext": {
                    "type": "boolean",
                    "description": "是否启用全文内容搜索,默认 true。",
                },
                "semantic": {
                    "type": "boolean",
                    "description": "是否启用语义搜索,默认 false。当文件名和全文都找不到时可开启。",
                },
            },
            "required": ["query"],
        },
        function=search_knowledge,
        display_name="搜索知识库",
    ),
]

# ------------------------------------------------------------------
# 文件管理工具
# ------------------------------------------------------------------
FILE_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_current_viewing_document",
        description="获取当前用户在 editor 前端正在观看的文档基本信息,只返回路径、文件名、知识库、大小、修改时间和未保存状态;如需正文请继续调用 read_knowledge_file。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=get_current_viewing_document,
        display_name="获取当前文档",
    ),
    BuiltinToolDefinition(
        name="list_knowledge_files",
        description="列出当前用户知识库的完整文件树,返回所有文件和文件夹的路径、类型和修改时间。用于了解知识库中有哪些文件。",
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=list_knowledge_files,
        display_name="列出文件",
    ),
    BuiltinToolDefinition(
        name="read_knowledge_file",
        description="读取知识库中指定文本文件的内容。先调用 list_knowledge_files 查看文件列表,再读取感兴趣的文件。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对于知识库根目录的路径,例如 notes/readme.md。",
                }
            },
            "required": ["path"],
        },
        function=read_knowledge_file,
        display_name="阅读文件",
    ),
    BuiltinToolDefinition(
        name="read_multimodal_file_info",
        description="读取已灌库的多模态文件结构化信息。不会重新解析原文件,而是定位该文件对应的 frontmatter JSON,返回标题、模态、元数据、章节列表和内容预览。适用于 PDF、DOCX、XLSX、PPTX、CSV、图片等已入库文件。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对于当前知识库根目录的路径,例如 docs/report.pdf 或 tables/demo.xlsx。",
                }
            },
            "required": ["path"],
        },
        function=read_multimodal_file_info,
        display_name="读取多模态文件信息",
    ),
    BuiltinToolDefinition(
        name="write_knowledge_file",
        description="在知识库中创建新文件或覆盖已有文件。用于生成文档、笔记、代码等文本文件。修改已有文件前建议先 read_knowledge_file 获取当前内容。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对于知识库根目录的路径,例如 notes/summary.md。",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的完整文件内容,支持 Markdown、代码、文本等。",
                },
            },
            "required": ["path", "content"],
        },
        function=write_knowledge_file,
        display_name="创作文件",
    ),
    BuiltinToolDefinition(
        name="delete_knowledge_file",
        description="删除知识库中的文件或文件夹。删除文件夹会递归删除其下所有内容,请谨慎使用。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件或文件夹相对于知识库根目录的路径。",
                }
            },
            "required": ["path"],
        },
        function=delete_knowledge_file,
        display_name="删除文件",
    ),
    BuiltinToolDefinition(
        name="rename_knowledge_file",
        description="重命名或移动知识库中的文件/文件夹。可以只改文件名,也可以移动到其他目录。",
        args_schema={
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "文件/文件夹的当前相对路径。",
                },
                "target_path": {
                    "type": "string",
                    "description": "新的相对路径,例如 new_name.md 或 archive/new_name.md。",
                },
            },
            "required": ["source_path", "target_path"],
        },
        function=rename_knowledge_file,
        display_name="重命名文件",
    ),
    BuiltinToolDefinition(
        name="create_knowledge_folder",
        description="在知识库中创建新文件夹(目录)。用于组织文件结构。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件夹相对于知识库根目录的路径,例如 projects/new-project。",
                }
            },
            "required": ["path"],
        },
        function=create_knowledge_folder,
        display_name="创建文件夹",
    ),
]

# ------------------------------------------------------------------
# 状态管理工具
# ------------------------------------------------------------------
STATE_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="update_exploration_state",
        description="更新 Agent 自身的知识探索状态,记录已覆盖的主题、建议方向和是否信息充足,用于跨轮次追踪探索进度。",
        args_schema={
            "type": "object",
            "properties": {
                "covered": {
                    "type": "string",
                    "description": "逗号分隔的新增已覆盖主题,例如 '海洋物理,大气科学'。已存在的主题不会重复添加。",
                },
                "suggested": {
                    "type": "string",
                    "description": "逗号分隔的建议继续探索方向,会替换之前的建议,例如 '海洋酸化,生态系统'。",
                },
                "sufficient": {
                    "type": "string",
                    "description": "当前信息是否足够回答用户问题,ture 或 false。",
                },
                "hint": {
                    "type": "string",
                    "description": "给下一轮的一两句策略提示。",
                },
            },
            "required": [],
        },
        function=update_exploration_state,
        display_name="更新探索状态",
    ),
]

# ------------------------------------------------------------------
# 联网搜索工具
# ------------------------------------------------------------------
WEB_SEARCH_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="web_search",
        description="通过 DuckDuckGo 搜索互联网,返回格式化搜索结果列表。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词。",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数,默认 5。",
                },
                "region": {
                    "type": "string",
                    "description": "搜索区域代码,默认 cn-zh (中国中文)。",
                },
                "time_range": {
                    "type": "string",
                    "description": "时间范围筛选。d=一天内,w=一周内,m=一个月内,y=一年内。留空表示不限时间。",
                },
            },
            "required": ["query"],
        },
        function=web_search,
        display_name="联网搜索",
    ),
]

# ------------------------------------------------------------------
# 合并全部内置工具 (保持向后兼容)
# ------------------------------------------------------------------
BUILTIN_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = (
    UTILITY_TOOL_DEFINITIONS + MEMORY_TOOL_DEFINITIONS + KNOWLEDGE_TOOL_DEFINITIONS + FILE_TOOL_DEFINITIONS + STATE_TOOL_DEFINITIONS + WEB_SEARCH_TOOL_DEFINITIONS
)
