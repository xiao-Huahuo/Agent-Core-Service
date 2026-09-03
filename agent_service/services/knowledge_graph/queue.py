"""知识图谱逐文件异步队列。

使用说明:
REST 层把已经完成灌库的文件追加到 ``submit``；每个知识库启动固定数量的
worker，运行中的同一路径自动去重，进度在入队、处理和出队时统一聚合。
应用关闭时必须调用 ``stop`` 等待 worker 退出。
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent_service.services.knowledge_graph.service import _run_graph_extraction, _update_graph_progress


GraphRunner = Callable[..., None]
ProgressWriter = Callable[..., None]
_TERMINAL_DOC_STATUSES = {"done", "skipped", "failed"}


@dataclass(slots=True)
class _GraphQueueTask:
    """保存一个文件或目录图谱请求及其运行参数。"""

    identity: str
    display_path: str
    display_name: str
    runner_kwargs: dict[str, Any]
    doc_paths: set[str] = field(default_factory=set)
    last_status: str = "running"


@dataclass(slots=True)
class _GraphQueueState:
    """保存单个用户知识库的等待、在途和聚合进度。"""

    pending: deque[_GraphQueueTask] = field(default_factory=deque)
    active: dict[str, _GraphQueueTask] = field(default_factory=dict)
    in_flight: set[str] = field(default_factory=set)
    docs: dict[str, dict[str, Any]] = field(default_factory=dict)
    threads: set[threading.Thread] = field(default_factory=set)
    message: str = ""
    result_json: str = ""


class KnowledgeGraphQueueService:
    """按知识库串行消费图谱任务，并允许请求在运行时继续追加。"""

    def __init__(
        self,
        *,
        runner: GraphRunner = _run_graph_extraction,
        progress_writer: ProgressWriter = _update_graph_progress,
        max_concurrency: int = 2,
    ) -> None:
        """保存执行器、单知识库并发上限，并初始化线程安全状态。"""

        self._runner = runner
        self._progress_writer = progress_writer
        self._max_concurrency = max(1, int(max_concurrency))
        self._states: dict[tuple[str, str], _GraphQueueState] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()

    def submit(
        self,
        *,
        config: Any,
        user_id: str,
        library_id: str,
        frontmatter_dir: Path,
        user_llm_config: dict[str, Any] | None,
        target_source_path: Path | None,
        target_is_dir: bool,
        target_display_path: str,
        force: bool,
    ) -> dict[str, Any]:
        """追加一个图谱任务；同一路径仍在等待或运行时直接复用。"""

        if self._stop_event.is_set():
            raise RuntimeError("图谱队列正在关闭")
        key = (user_id, library_id)
        identity = target_display_path or "__all__"
        with self._lock:
            if self._stop_event.is_set():
                raise RuntimeError("图谱队列正在关闭")
            state = self._states.setdefault(key, _GraphQueueState())
            if identity in state.in_flight:
                return {"status": "deduplicated", "message": "该图谱任务已在队列中"}
            if not state.active and not state.pending and not state.threads:
                state.docs.clear()
                state.message = ""
                state.result_json = ""
            task = _GraphQueueTask(
                identity=identity,
                display_path=target_display_path,
                display_name=Path(target_display_path).name if target_display_path else "全部文件",
                runner_kwargs={
                    "config": config,
                    "user_id": user_id,
                    "library_id": library_id,
                    "frontmatter_dir": frontmatter_dir,
                    "user_llm_config": user_llm_config,
                    "target_source_path": target_source_path,
                    "target_is_dir": target_is_dir,
                    "force": force,
                    "cancel_event": self._stop_event,
                },
            )
            state.pending.append(task)
            state.in_flight.add(identity)
            state.docs[identity] = self._pending_doc(task)
            state.message = f"已加入图谱队列：{task.display_name}"
            self._publish_locked(key, state, status="running")
            while state.pending and len(state.threads) < self._max_concurrency:
                thread = threading.Thread(
                    target=self._worker,
                    args=(key,),
                    daemon=True,
                    name=f"knowledge-graph-queue-{library_id}-{len(state.threads)}",
                )
                state.threads.add(thread)
                try:
                    thread.start()
                except Exception:
                    state.threads.discard(thread)
                    raise
        return {"status": "queued", "message": "图谱任务已加入队列"}

    def stop(self) -> None:
        """通知当前抽取安全停止，并等待所有队列 worker 退出。"""

        self._stop_event.set()
        with self._lock:
            threads = [thread for state in self._states.values() for thread in state.threads]
        for thread in threads:
            thread.join(timeout=5)

    def _worker(self, key: tuple[str, str]) -> None:
        """持续领取同一知识库的新任务，直到等待队列真正为空。"""

        current_thread = threading.current_thread()
        while True:
            with self._lock:
                state = self._states[key]
                if self._stop_event.is_set() or not state.pending:
                    state.threads.discard(current_thread)
                    status = "running" if state.active or state.pending else self._final_status(state)
                    self._publish_locked(key, state, status=status)
                    return
                task = state.pending.popleft()
                state.active[task.identity] = task
                state.docs[task.identity] = {
                    **state.docs[task.identity],
                    "status": "processing",
                    "stage": "preparing",
                    "stage_label": "正在准备文档",
                    "progress": 1,
                }
                self._publish_locked(key, state, status="running")

            def report_progress(**payload: Any) -> None:
                """把单次执行器进度合并到动态总队列。"""

                self._merge_progress(key=key, task=task, payload=payload)

            try:
                self._runner(**task.runner_kwargs, progress_callback=report_progress)
            except Exception as exc:
                report_progress(status="failed", message=f"抽取失败: {exc}")

            with self._lock:
                state = self._states[key]
                self._finish_task_docs(state, task)
                state.in_flight.discard(task.identity)
                state.active.pop(task.identity, None)
                self._publish_locked(
                    key,
                    state,
                    status="running" if state.pending or state.active else self._final_status(state),
                )

    def _merge_progress(self, *, key: tuple[str, str], task: _GraphQueueTask, payload: dict[str, Any]) -> None:
        """以路径合并执行器文档状态，同时保留后来追加的等待项。"""

        with self._lock:
            state = self._states[key]
            task.last_status = str(payload.get("status") or task.last_status)
            docs = payload.get("docs")
            if isinstance(docs, list) and docs:
                state.docs.pop(task.identity, None)
                for raw_doc in docs:
                    doc = dict(raw_doc)
                    path = str(doc.get("path") or task.identity)
                    task.doc_paths.add(path)
                    state.docs[path] = doc
            state.message = str(payload.get("message") or state.message)
            state.result_json = str(payload.get("result_json") or state.result_json)
            if task.last_status in {"failed", "cancelled"} and not task.doc_paths:
                state.docs[task.identity] = {
                    **state.docs.get(task.identity, self._pending_doc(task)),
                    "status": "failed",
                    "progress": 100,
                    "stage": "failed",
                    "stage_label": "图谱抽取失败",
                    "message": state.message,
                }
            self._publish_locked(key, state, status="running")

    @staticmethod
    def _pending_doc(task: _GraphQueueTask) -> dict[str, Any]:
        """构造入队瞬间即可展示的文件行。"""

        return {
            "path": task.display_path or task.identity,
            "name": task.display_name,
            "status": "pending",
            "progress": 0,
            "stage": "waiting",
            "stage_label": "等待图谱抽取",
            "stage_current": 0,
            "stage_total": 0,
            "message": "",
        }

    @staticmethod
    def _finish_task_docs(state: _GraphQueueState, task: _GraphQueueTask) -> None:
        """保证执行器退出时当前任务的所有行都离开在途状态。"""

        paths = task.doc_paths or {task.identity}
        fallback_status = "failed" if task.last_status in {"failed", "cancelled"} else "skipped"
        for path in paths:
            doc = state.docs.get(path)
            if doc is None or str(doc.get("status")) in _TERMINAL_DOC_STATUSES:
                continue
            state.docs[path] = {
                **doc,
                "status": fallback_status,
                "progress": 100,
                "stage": fallback_status,
                "stage_label": "图谱抽取失败" if fallback_status == "failed" else "无需重新抽取",
            }

    @staticmethod
    def _final_status(state: _GraphQueueState) -> str:
        """仅在所有文档都失败时报告整体失败，否则完成并保留逐行结果。"""

        docs = list(state.docs.values())
        return "failed" if docs and all(doc.get("status") == "failed" for doc in docs) else "completed"

    def _publish_locked(self, key: tuple[str, str], state: _GraphQueueState, *, status: str) -> None:
        """按当前队列快照重算总数与完成数，并写入共享进度。"""

        docs = list(state.docs.values())
        current = sum(1 for doc in docs if doc.get("status") in _TERMINAL_DOC_STATUSES)
        message = state.message
        if status == "completed" and not message:
            message = "图谱抽取完成"
        self._progress_writer(
            key[0],
            key[1],
            status=status,
            total=len(docs),
            current=current,
            message=message,
            result_json=state.result_json,
            docs=docs,
        )
