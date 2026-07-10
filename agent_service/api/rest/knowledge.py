"""用户知识库 REST 端点。"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - fallback only used when optional dependency is absent.
    FileSystemEvent = Any  # type: ignore[misc, assignment]
    FileSystemEventHandler = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]

from agent_service.api.rest.deps import _require_knowledge_library_service, _require_retrieval_service

router = APIRouter()


class _KnowledgeFileEventHandler(FileSystemEventHandler):
    """
    watchdog 文件事件桥接器。

    root: 当前监听的知识库根目录。
    loop: FastAPI 当前事件循环。
    queue: 跨线程投递给 SSE 生成器的事件队列。
    """

    def __init__(self, *, root: Path, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[str]) -> None:
        """保存 watcher 事件投递所需上下文。"""

        self.root = root
        self.loop = loop
        self.queue = queue

    def on_any_event(self, event: FileSystemEvent) -> None:
        """将 watchdog 线程中的文件变化投递到 asyncio 队列。"""

        if event.event_type in {"opened", "closed_no_write"}:
            return
        event_path = Path(str(getattr(event, "dest_path", "") or event.src_path)).resolve()
        relative_path = ""
        with contextlib.suppress(ValueError):
            relative_path = event_path.relative_to(self.root).as_posix()
        self.loop.call_soon_threadsafe(self.queue.put_nowait, relative_path)


@router.get("/knowledge/files")
async def list_knowledge_files(user_id: str = Query(..., min_length=1, description="用户 ID")) -> dict[str, Any]:
    """列出当前 active 知识库的递归文件树。"""

    svc = _require_knowledge_library_service()
    try:
        tree = await run_in_threadpool(svc.list_files, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"tree": tree}


@router.get("/knowledge/files/content")
async def read_knowledge_file(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    path: str = Query(..., min_length=1, description="知识库内相对路径"),
) -> dict[str, Any]:
    """读取当前 active 知识库中的文本文件。"""

    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(svc.read_file, user_id=user_id, path=path)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=415, detail="file is not valid UTF-8 text") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge/files/content")
async def write_knowledge_file(body: dict[str, Any]) -> dict[str, Any]:
    """
    保存当前 active 知识库中的文本文件。

    保存只写入磁盘并触发文件树刷新;不会执行灌库。
    """

    user_id = str(body.get("user_id") or "").strip()
    path = str(body.get("path") or "").strip()
    content = str(body.get("content") or "")
    if not user_id or not path:
        raise HTTPException(status_code=422, detail="user_id and path are required")
    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(svc.write_file, user_id=user_id, path=path, content=content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge/files/file")
async def create_knowledge_file(body: dict[str, Any]) -> dict[str, Any]:
    """在当前 active 知识库中新建文本文件。"""

    user_id = str(body.get("user_id") or "").strip()
    path = str(body.get("path") or "").strip()
    content = str(body.get("content") or "")
    if not user_id or not path:
        raise HTTPException(status_code=422, detail="user_id and path are required")
    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(svc.create_file, user_id=user_id, path=path, content=content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge/files/folder")
async def create_knowledge_folder(body: dict[str, Any]) -> dict[str, Any]:
    """在当前 active 知识库中新建文件夹。"""

    user_id = str(body.get("user_id") or "").strip()
    path = str(body.get("path") or "").strip()
    if not user_id or not path:
        raise HTTPException(status_code=422, detail="user_id and path are required")
    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(svc.create_folder, user_id=user_id, path=path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/knowledge/files")
async def delete_knowledge_path(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    path: str = Query(..., min_length=1, description="知识库内相对路径"),
) -> dict[str, Any]:
    """删除当前 active 知识库中的文件或文件夹。"""

    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(svc.delete_path, user_id=user_id, path=path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge/files/copy")
async def copy_knowledge_path(body: dict[str, Any]) -> dict[str, Any]:
    """复制当前 active 知识库中的文件/文件夹。"""

    user_id = str(body.get("user_id") or "").strip()
    source_path = str(body.get("source_path") or "").strip()
    target_path = str(body.get("target_path") or "").strip()
    if not user_id or not source_path or not target_path:
        raise HTTPException(status_code=422, detail="user_id, source_path and target_path are required")
    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(
            svc.copy_path,
            user_id=user_id,
            source_path=source_path,
            target_path=target_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge/files/rename")
async def rename_knowledge_path(body: dict[str, Any]) -> dict[str, Any]:
    """移动或重命名当前 active 知识库中的文件/文件夹。"""

    user_id = str(body.get("user_id") or "").strip()
    source_path = str(body.get("source_path") or "").strip()
    target_path = str(body.get("target_path") or "").strip()
    if not user_id or not source_path or not target_path:
        raise HTTPException(status_code=422, detail="user_id, source_path and target_path are required")
    svc = _require_knowledge_library_service()
    try:
        return await run_in_threadpool(
            svc.rename_path,
            user_id=user_id,
            source_path=source_path,
            target_path=target_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/knowledge/rebuild")
async def rebuild_knowledge(body: dict[str, Any]) -> dict[str, Any]:
    """
    重新扫描用户知识库并灌入向量库。

    body: user_id 必填,knowledge_dir 可选;传入 knowledge_dir 时会同步更新用户设置。
    """

    user_id = str(body.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id is required")
    knowledge_dir = body.get("knowledge_dir")
    svc = _require_knowledge_library_service()
    try:
        result = await run_in_threadpool(
            svc.rebuild_user_knowledge,
            user_id=user_id,
            knowledge_dir=str(knowledge_dir) if knowledge_dir else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


@router.post("/knowledge/files/upload")
async def upload_knowledge_file(
    user_id: Annotated[str, Form(min_length=1, description="用户 ID")],
    file: Annotated[UploadFile, File(description="知识库文件,当前支持 .md/.txt")],
    relative_dir: Annotated[str, Form(description="知识库内目标子目录")] = "",
) -> dict[str, Any]:
    """
    上传文件到用户知识库目录并重新灌库。

    user_id: 用户 ID。
    file: 上传文件,当前沿用现有 Markdown/TXT 解析链路。
    relative_dir: 可选目标子目录,必须位于用户知识库根目录内。
    """

    svc = _require_knowledge_library_service()
    content = await file.read()
    try:
        uploaded_path = await run_in_threadpool(
            svc.write_uploaded_file,
            user_id=user_id,
            filename=file.filename or "",
            content=content,
            relative_dir=relative_dir,
        )
        result = await run_in_threadpool(
            svc.rebuild_user_knowledge,
            user_id=user_id,
            uploaded_path=str(uploaded_path),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()


@router.get("/knowledge/search")
async def search_knowledge(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
    query: str = Query(..., min_length=1, description="搜索关键词"),
    fulltext: bool = Query(default=True, description="是否启用全文内容搜索"),
    semantic: bool = Query(default=False, description="是否启用语义搜索"),
) -> dict[str, Any]:
    """
    知识库联合搜索：文件名匹配 + (可选)全文内容匹配 + (可选)语义搜索。
    """

    lib_svc = _require_knowledge_library_service()
    retrieval_svc = _require_retrieval_service()
    top_k = retrieval_svc.config.memory.knowledge_search_semantic_top_k
    from os import path as _os_path
    library_root = str(await run_in_threadpool(lib_svc.get_active_root_path, user_id=user_id))

    def _is_in_library(uri: str) -> bool:
        """检查 source_uri 是否属于当前 active 知识库,防止串库。"""
        if not uri:
            return False
        try:
            normalized_uri = _os_path.normcase(_os_path.normpath(uri))
            normalized_root = _os_path.normcase(_os_path.normpath(library_root))
            return normalized_uri.startswith(normalized_root + _os_path.sep) or normalized_uri == normalized_root
        except (ValueError, TypeError):
            return False

    async def _filename_search() -> list[dict[str, str]]:
        tree = await run_in_threadpool(lib_svc.list_files, user_id=user_id)

        def _search_nodes(nodes: list[dict], results: list[dict]) -> None:
            for node in nodes:
                name = str(node.get("name", "") or "")
                if query.lower() in name.lower():
                    results.append({"path": str(node.get("path", "") or ""), "name": name})
                children = node.get("children")
                if isinstance(children, list):
                    _search_nodes(children, results)

        results: list[dict] = []
        _search_nodes(tree, results)
        return results

    async def _fulltext_search() -> list[dict[str, Any]]:
        indexed = await run_in_threadpool(
            retrieval_svc.memory_service.search_knowledge_content,
            query=query,
            user_id=user_id,
        )
        disk_matches = await run_in_threadpool(
            lib_svc.search_file_contents,
            user_id=user_id,
            query=query,
        )
        seen_paths: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in [*indexed, *disk_matches]:
            uri = str(item.get("source_uri") or "")
            if not _is_in_library(uri):
                continue
            normalized_uri = _os_path.normcase(_os_path.normpath(uri))
            if normalized_uri in seen_paths:
                continue
            seen_paths.add(normalized_uri)
            deduped.append(item)
        return deduped

    async def _semantic_search() -> list[dict[str, Any]]:
        items = await run_in_threadpool(
            retrieval_svc.retrieve_knowledge,
            query=query,
            user_id=user_id,
            top_k=top_k,
        )
        from agent_service.services.memory.retrieval_service import MemoryRetrievalService
        seen_names: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in items:
            uri = str(item.memory.source_uri or "")
            if not _is_in_library(uri):
                continue
            name = _os_path.basename(uri)
            if name in seen_names:
                continue
            seen_names.add(name)
            deduped.append(MemoryRetrievalService.serialize_retrieved_memory(item))
        return deduped

    filename_task = _filename_search()
    fulltext_task = _fulltext_search() if fulltext else None
    semantic_task = _semantic_search() if semantic else None

    filename_results = await filename_task
    fulltext_results = await fulltext_task if fulltext_task else []
    semantic_results = await semantic_task if semantic_task else []
    return {
        "filename_results": filename_results,
        "fulltext_results": fulltext_results,
        "semantic_results": semantic_results,
    }


@router.get("/knowledge/files/events")
async def stream_knowledge_file_events(
    user_id: str = Query(..., min_length=1, description="用户 ID"),
) -> StreamingResponse:
    """
    推送当前 active 知识库文件变化事件。

    事件只用于前端刷新文件树;不会触发向量灌库。
    """

    svc = _require_knowledge_library_service()

    async def event_stream():
        if Observer is not None:
            async for event in _watchdog_event_stream(svc=svc, user_id=user_id):
                yield event
            return
        async for event in _polling_event_stream(svc=svc, user_id=user_id):
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _watchdog_event_stream(*, svc: Any, user_id: str):
    """
    使用 watchdog 监听知识库文件变化并生成 SSE。

    user_id: 用户 ID。
    """

    root = await run_in_threadpool(svc.get_active_root_path, user_id=user_id)
    queue: asyncio.Queue[str] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    observer = Observer()
    observer.schedule(
        _KnowledgeFileEventHandler(root=root, loop=loop, queue=queue),
        str(root),
        recursive=True,
    )
    observer.start()
    yield _sse("ready", {"type": "ready"})
    try:
        while True:
            try:
                path = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield _sse("heartbeat", {"type": "heartbeat"})
                continue
            await asyncio.sleep(0.15)
            while not queue.empty():
                path = queue.get_nowait()
            yield _sse("tree_dirty", {"type": "tree_dirty", "path": path})
    finally:
        observer.stop()
        await run_in_threadpool(observer.join, 2)


async def _polling_event_stream(*, svc: Any, user_id: str):
    """
    watchdog 不可用时的签名轮询 fallback。

    user_id: 用户 ID。
    """

    previous_signature = await run_in_threadpool(svc.build_tree_signature, user_id=user_id)
    yield _sse("ready", {"type": "ready"})
    while True:
        await asyncio.sleep(1.5)
        current_signature = await run_in_threadpool(svc.build_tree_signature, user_id=user_id)
        if current_signature == previous_signature:
            continue
        previous_signature = current_signature
        yield _sse("tree_dirty", {"type": "tree_dirty", "path": ""})


def _sse(event: str, payload: dict[str, Any]) -> str:
    """序列化 Server-Sent Events 消息。"""

    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
