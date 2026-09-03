"""知识灌库、图谱、文件状态和回收站 Agent 工具。

使用说明:
本模块只负责把 Agent 参数适配到现有知识库与图谱服务。长任务统一交给
``tool_job_manager``，调用方使用返回的 job_id 查询、取消或重试失败文件。
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.services.editor_context.service import editor_context_service
from agent_service.services.knowledge_graph import (
    _run_graph_extraction,
    get_graph_extraction_progress,
)
from agent_service.tools.builtin.jobs import ToolJobCancelled, tool_job_manager
from agent_service.tools.runtime_context import AGENT_ACCESS_READONLY, get_tool_runtime, get_tool_service


def _knowledge_service() -> Any:
    """读取 Agent 工具运行时显式注入的知识库服务。"""

    return get_tool_service("knowledge_library")


def _graph_service() -> Any:
    """读取 Agent 工具运行时显式注入的图谱服务。"""

    return get_tool_service("knowledge_graph")


def _settings_service() -> Any:
    """从当前 Agent 工具运行时读取用户设置服务。"""

    service = get_tool_runtime().settings_service
    if service is None:
        raise RuntimeError("当前工具调用缺少 SettingsService。")
    return service


def _json(payload: Any) -> str:
    """按 UTF-8 友好的格式返回工具结构化结果。"""

    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _require_write_access(action: str) -> None:
    """拒绝只读 Agent 执行会修改持久化数据的操作。"""

    if get_tool_runtime().agent_access_mode == AGENT_ACCESS_READONLY:
        raise PermissionError(f"当前 Agent 为只读模式，不能{action}")


def _normalized_paths(paths: list[str]) -> list[str]:
    """规范化并去重用户提供的知识库相对路径。"""

    normalized = list(dict.fromkeys(str(path or "").replace("\\", "/").strip("/") for path in paths))
    normalized = [path for path in normalized if path]
    if not normalized:
        raise ValueError("paths must contain at least one knowledge file")
    return normalized


def get_selected_knowledge_files() -> str:
    """返回编辑器最近上报的多选文件；没有多选时回退到当前文档。"""

    runtime = get_tool_runtime()
    info = editor_context_service.get_current_document(runtime.user_id)
    if info is None:
        return _json({"paths": [], "count": 0})
    selected_paths = list(info.selected_paths)
    if not selected_paths and info.path:
        selected_paths = [info.path]
    return _json({"paths": selected_paths, "count": len(selected_paths)})


def _start_ingestion_job(*, paths: list[str] | None, all_files: bool) -> str:
    """启动选定文件或全库灌库任务。"""

    _require_write_access("执行知识灌库")
    runtime = get_tool_runtime()
    user_id = runtime.user_id
    service = _knowledge_service()
    selected_paths = _normalized_paths(paths or []) if not all_files else []

    def runner(update: Any, cancel_event: Any) -> dict[str, Any]:
        """在后台执行灌库并收集逐文件失败信息。"""

        if all_files:
            def progress(payload: dict[str, Any]) -> None:
                """桥接现有全库灌库进度并响应取消。"""

                if cancel_event.is_set():
                    raise ToolJobCancelled("任务已取消")
                update(
                    total=int(payload.get("total") or 0),
                    current=int(payload.get("current") or 0),
                    message=str(payload.get("message") or "正在灌库"),
                )

            result = service.rebuild_user_knowledge(user_id=user_id, progress_callback=progress)
            return result.to_dict()

        failures: list[dict[str, str]] = []
        results: list[dict[str, Any]] = []
        update(total=len(selected_paths), current=0, message="正在灌入选定文件")
        for index, path in enumerate(selected_paths, 1):
            if cancel_event.is_set():
                raise ToolJobCancelled("任务已取消")
            try:
                result = service.ingest_single_file(user_id=user_id, path=path)
                results.append({"path": path, "result": result.to_dict()})
            except Exception as exc:  # noqa: BLE001 - failures are returned per selected file.
                failures.append({"path": path, "error": str(exc)})
            update(
                current=index,
                message=f"已处理 {index}/{len(selected_paths)}",
                failed_items=failures,
            )
        return {"processed": len(results), "failed": len(failures), "items": results, "failed_items": failures}

    job = tool_job_manager.start(
        user_id=user_id,
        kind="ingestion_all" if all_files else "ingestion_selected",
        runner=runner,
    )
    return _json(job)


def ingest_selected_knowledge_files(paths: list[str]) -> str:
    """后台灌入指定的多个知识库源文件。"""

    return _start_ingestion_job(paths=paths, all_files=False)


def ingest_all_knowledge_files() -> str:
    """后台扫描并灌入当前 active 知识库的全部支持文件。"""

    return _start_ingestion_job(paths=None, all_files=True)


def get_knowledge_job_status(job_id: str) -> str:
    """查询当前用户发起的灌库或图谱后台任务。"""

    return _json(tool_job_manager.get(user_id=get_tool_runtime().user_id, job_id=job_id))


def cancel_knowledge_job(job_id: str) -> str:
    """请求灌库或图谱任务在下一个安全检查点取消。"""

    _require_write_access("取消知识处理任务")
    return _json(tool_job_manager.cancel(user_id=get_tool_runtime().user_id, job_id=job_id))


def retry_failed_knowledge_files(job_id: str) -> str:
    """重新灌入指定历史任务中失败的文件。"""

    job = tool_job_manager.get(user_id=get_tool_runtime().user_id, job_id=job_id)
    if not str(job.get("kind") or "").startswith("ingestion"):
        raise ValueError("job is not an ingestion job")
    paths = [str(item.get("path") or "") for item in job.get("failed_items") or []]
    return _start_ingestion_job(paths=paths, all_files=False)


def _find_file_node(nodes: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    """在递归文件树中查找指定相对路径节点。"""

    for node in nodes:
        if str(node.get("path") or "") == path:
            return node
        children = node.get("children")
        if isinstance(children, list):
            found = _find_file_node(children, path)
            if found is not None:
                return found
    return None


def get_knowledge_file_status(path: str) -> str:
    """返回源文件、Markdown 投影、索引和图谱的完整管线状态。"""

    runtime = get_tool_runtime()
    service = _knowledge_service()
    relative_path = str(path or "").replace("\\", "/").strip("/")
    node = _find_file_node(service.list_files(user_id=runtime.user_id), relative_path)
    if node is None or node.get("isDir"):
        raise ValueError("knowledge file not found")
    profile = _settings_service().ensure_user_profile(user_id=runtime.user_id)
    library = dict(profile["active_knowledge_library"])
    root = Path(str(library["knowledge_dir"])).resolve()
    projection = (root / ".mw" / "md" / relative_path).with_suffix(".md")
    frontmatter = (root / ".mw" / "frontmatter" / relative_path).with_suffix(".json")
    return _json({
        "path": relative_path,
        "index_status": node.get("indexStatus"),
        "graph_status": node.get("graphStatus"),
        "ingested_at": node.get("ingestedAt"),
        "size": node.get("size"),
        "mtime": node.get("mtime"),
        "markdown_projection": projection.relative_to(root).as_posix(),
        "markdown_projection_exists": projection.is_file(),
        "frontmatter": frontmatter.relative_to(root).as_posix(),
        "frontmatter_exists": frontmatter.is_file(),
    })


def list_knowledge_trash() -> str:
    """列出当前 active 知识库最近删除中的所有条目。"""

    return _json(_knowledge_service().list_deleted_paths(user_id=get_tool_runtime().user_id))


def restore_knowledge_file(trash_id: str) -> str:
    """按 trash_id 从最近删除恢复文件或文件夹。"""

    _require_write_access("恢复知识库文件")
    return _json(
        _knowledge_service().restore_deleted_path(
            user_id=get_tool_runtime().user_id,
            trash_id=trash_id,
        )
    )


def permanently_delete_knowledge_trash(trash_id: str, confirm: bool = False) -> str:
    """永久删除最近删除条目；必须由用户明确确认。"""

    _require_write_access("永久删除最近删除条目")
    if not confirm:
        raise PermissionError("永久删除不可恢复，必须取得用户明确确认并传 confirm=true")
    return _json(
        _knowledge_service().delete_trash_entry(
            user_id=get_tool_runtime().user_id,
            trash_id=trash_id,
        )
    )


def _graph_context() -> tuple[str, str, Path, dict[str, Any], Any]:
    """解析当前用户 active 图谱抽取所需上下文。"""

    runtime = get_tool_runtime()
    settings = _settings_service()
    profile = settings.ensure_user_profile(user_id=runtime.user_id)
    library = dict(profile["active_knowledge_library"])
    normalized_user_id = str(profile["user_id"])
    library_id = str(library["library_id"])
    root = Path(str(library["knowledge_dir"])).expanduser().resolve()
    return normalized_user_id, library_id, root, settings.get_llm_config(user_id=normalized_user_id), runtime.config


def _start_graph_job(*, paths: list[str] | None, all_files: bool) -> str:
    """启动选定文件或全库图谱抽取任务。"""

    _require_write_access("执行图谱抽取")
    user_id, library_id, root, llm_config, config = _graph_context()
    selected_paths = _normalized_paths(paths or []) if not all_files else []
    knowledge_service = _knowledge_service()

    def runner(update: Any, cancel_event: Any) -> dict[str, Any]:
        """复用现有图谱抽取器并聚合逐文件结果。"""

        targets: list[str | None] = [None] if all_files else list(selected_paths)
        failures: list[dict[str, str]] = []
        completed: list[str] = []
        update(total=len(targets), current=0, message="正在抽取知识图谱")
        for index, target in enumerate(targets, 1):
            if cancel_event.is_set():
                raise ToolJobCancelled("任务已取消")
            try:
                target_path: Path | None = None
                if target is not None:
                    knowledge_service.ingest_single_file(user_id=user_id, path=target)
                    target_path = (root / target).resolve()
                    if not target_path.is_file():
                        raise ValueError("knowledge file not found")
                _run_graph_extraction(
                    config=config,
                    user_id=user_id,
                    library_id=library_id,
                    frontmatter_dir=root / ".mw" / "frontmatter",
                    user_llm_config=llm_config,
                    target_source_path=target_path,
                    target_is_dir=False,
                    cancel_event=cancel_event,
                )
                progress = get_graph_extraction_progress(user_id, library_id)
                if progress.get("status") == "failed":
                    failures.append({"path": target or "*", "error": str(progress.get("message") or "graph extraction failed")})
                else:
                    completed.append(target or "*")
            except ToolJobCancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - graph failures are reported per selected file.
                failures.append({"path": target or "*", "error": str(exc) or "knowledge file not found"})
            update(
                current=index,
                message=f"已处理 {index}/{len(targets)}",
                failed_items=failures,
            )
        return {"completed_paths": completed, "failed_items": failures}

    job = tool_job_manager.start(
        user_id=user_id,
        kind="graph_all" if all_files else "graph_selected",
        runner=runner,
    )
    return _json(job)


def extract_selected_file_graphs(paths: list[str]) -> str:
    """为指定多个源文件自动灌库并后台抽取语义图谱。"""

    return _start_graph_job(paths=paths, all_files=False)


def extract_all_file_graphs() -> str:
    """为当前 active 知识库全部已支持文件后台抽取语义图谱。"""

    return _start_graph_job(paths=None, all_files=True)


def _current_graph(limit: int | None = None) -> dict[str, Any]:
    """读取当前 active 知识库图谱点边数据。"""

    user_id, library_id, _root, _llm_config, config = _graph_context()
    return _graph_service().get_graph(
        user_id=user_id,
        library_id=library_id,
        limit=limit or config.limits.api_internal_scan_limit,
    )


def search_knowledge_graph_nodes(query: str, limit: int | None = None) -> str:
    """按标签、类型和元数据搜索图谱节点，并返回每个命中的邻接节点。"""

    graph = _current_graph()
    nodes = [node for node in graph.get("nodes") or [] if isinstance(node, dict)]
    links = [link for link in graph.get("links") or [] if isinstance(link, dict)]
    normalized = query.strip().casefold()
    try:
        limits = get_tool_runtime().config.limits
    except RuntimeError:
        limits = DEFAULT_BUSINESS_LIMITS
    matches = [node for node in nodes if normalized in _json(node).casefold()][
        :max(
            limits.nonempty_min_length,
            min(limit or limits.graph_search_default_limit, limits.graph_search_max_limit),
        )
    ]
    by_id = {str(node.get("id") or ""): node for node in nodes}
    results: list[dict[str, Any]] = []
    for node in matches:
        node_id = str(node.get("id") or "")
        adjacent: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for link in links:
            source = str(link.get("source") or "")
            target = str(link.get("target") or "")
            if node_id not in {source, target}:
                continue
            neighbor_id = target if source == node_id else source
            if neighbor_id in by_id:
                adjacent.append(by_id[neighbor_id])
            edges.append(link)
        results.append({"node": node, "adjacent_nodes": adjacent, "edges": edges})
    return _json({"query": query, "count": len(results), "results": results})


def find_knowledge_graph_paths(
    source_node_id: str,
    target_node_id: str,
    max_depth: int | None = None,
) -> str:
    """使用无向 BFS 查找两个图谱节点间的最短关系路径。"""

    graph = _current_graph()
    nodes = {str(node.get("id") or ""): node for node in graph.get("nodes") or [] if isinstance(node, dict)}
    links = [link for link in graph.get("links") or [] if isinstance(link, dict)]
    if source_node_id not in nodes or target_node_id not in nodes:
        raise ValueError("source or target graph node not found")
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for link in links:
        source = str(link.get("source") or "")
        target = str(link.get("target") or "")
        adjacency.setdefault(source, []).append((target, link))
        adjacency.setdefault(target, []).append((source, link))
    queue: deque[tuple[str, list[str], list[dict[str, Any]]]] = deque([(source_node_id, [source_node_id], [])])
    visited = {source_node_id}
    while queue:
        current, path, edges = queue.popleft()
        if current == target_node_id:
            return _json({"nodes": [nodes[node_id] for node_id in path], "edges": edges, "depth": len(edges)})
        try:
            limits = get_tool_runtime().config.limits
        except RuntimeError:
            limits = DEFAULT_BUSINESS_LIMITS
        if len(edges) >= max(
            limits.nonempty_min_length,
            min(max_depth or limits.graph_path_default_depth, limits.graph_path_max_depth),
        ):
            continue
        for neighbor, edge in adjacency.get(current, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, [*path, neighbor], [*edges, edge]))
    return _json({"nodes": [], "edges": [], "depth": None, "message": "未找到限定深度内的关系路径"})


def delete_file_graph(path: str) -> str:
    """删除指定源文件对应的文档节点、实体关系及抽取状态。"""

    _require_write_access("删除文件图谱")
    runtime = get_tool_runtime()
    payload = _knowledge_service().read_frontmatter_payload_for_file(
        user_id=runtime.user_id,
        path=path,
    )
    document_id = str(payload.get("document_id") or "")
    if not document_id:
        raise ValueError("frontmatter document_id not found")
    user_id, library_id, _root, _llm_config, _config = _graph_context()
    deleted = _graph_service().delete_document_graph(
        user_id=user_id,
        library_id=library_id,
        document_id=document_id,
    )
    return _json({"path": path, "document_id": document_id, "deleted": deleted})


def retry_failed_graph_extraction(job_id: str) -> str:
    """重新抽取指定历史图谱任务中失败的源文件。"""

    job = tool_job_manager.get(user_id=get_tool_runtime().user_id, job_id=job_id)
    if not str(job.get("kind") or "").startswith("graph"):
        raise ValueError("job is not a graph job")
    failures = list(job.get("failed_items") or [])
    if any(item.get("path") == "*" for item in failures):
        return _start_graph_job(paths=None, all_files=True)
    paths = [str(item.get("path") or "") for item in failures]
    return _start_graph_job(paths=paths, all_files=False)
