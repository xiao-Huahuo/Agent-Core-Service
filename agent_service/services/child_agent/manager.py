"""
父子 Agent 管理器。

功能说明:
本文件实现子 Agent 的创建、前后台执行、状态查询、结果投递、停止和上下文更新。
它只负责运行时编排,不绑定具体 LLM 或 LangGraph,具体执行逻辑通过执行器注入。

使用说明:
调用方应为每个子任务提供一个 `ChildAgentExecutor`。第一版的结果队列按
`parent_run_id` 隔离,未来可以在不改变调用协议的情况下替换为 Redis Stream。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
from threading import Event, Lock
import time
from typing import Any
from uuid import uuid4

from agent_service.core.agent_config import AgentConfig
from agent_service.tools.runtime_context import (
    AGENT_ACCESS_FULL,
    AGENT_ACCESS_READONLY,
    AGENT_ACCESS_SANDBOX,
    normalize_agent_access_mode,
)
from agent_service.services.child_agent.types import (
    ChildAgentContract,
    ChildAgentExecutionContext,
    ChildAgentEvent,
    ChildAgentExecutor,
    ChildAgentRecord,
    ChildAgentResult,
    ChildAgentStatus,
    ChildAgentStopped,
    ChildAgentUpdate,
)


class ChildAgentManager:
    """
    管理一个进程内的父子 Agent 运行实例。

    max_workers: 同时执行的子 Agent 最大线程数。
    event_callback: 每次状态变化时接收 `(event_name, record)` 的回调。
    """

    _ACCESS_RANK = {
        AGENT_ACCESS_READONLY: 0,
        AGENT_ACCESS_SANDBOX: 1,
        AGENT_ACCESS_FULL: 2,
    }

    def __init__(
        self,
        *,
        max_workers: int | None = None,
        config: AgentConfig | None = None,
        event_callback: Callable[[str, ChildAgentRecord], None] | None = None,
    ) -> None:
        """初始化线程池、运行记录表和按父级隔离的结果队列。"""

        limits = (config or AgentConfig()).limits
        self._executor = ThreadPoolExecutor(
            max_workers=max(limits.child_agent_max_workers if max_workers is None else max_workers, 1),
            thread_name_prefix="child-agent",
        )
        self._records: dict[str, ChildAgentRecord] = {}
        self._futures: dict[str, Future[Any]] = {}
        self._result_queues: defaultdict[str, Queue[ChildAgentResult]] = defaultdict(Queue)
        self._event_queues_by_session: defaultdict[str, Queue[ChildAgentEvent]] = defaultdict(Queue)
        self._lock = Lock()
        self._event_callback = event_callback
        self._closed = False

    def spawn(
        self,
        *,
        contract: ChildAgentContract,
        executor: ChildAgentExecutor,
        parent_tools: frozenset[str] | None = None,
        parent_access_mode: str = AGENT_ACCESS_SANDBOX,
        caller_is_child: bool = False,
    ) -> ChildAgentRecord:
        """创建并启动一个子 Agent,前台模式会等待完成后再返回。"""

        if self._closed:
            raise RuntimeError("ChildAgentManager 已关闭。")
        if caller_is_child:
            raise PermissionError("子 Agent 不能召唤其他子 Agent。")
        if not contract.goal.strip():
            raise ValueError("子 Agent 目标不能为空。")
        if contract.mode not in {"foreground", "background"}:
            raise ValueError("子 Agent mode 必须是 foreground 或 background。")

        effective_parent_access = normalize_agent_access_mode(parent_access_mode)
        effective_child_access = normalize_agent_access_mode(contract.access_mode)
        if self._ACCESS_RANK[effective_child_access] > self._ACCESS_RANK[effective_parent_access]:
            raise PermissionError("子 Agent 权限不能高于父 Agent 权限。")

        if contract.allowed_tools is None:
            effective_tools = parent_tools or frozenset()
        elif parent_tools is None:
            effective_tools = frozenset(contract.allowed_tools)
        else:
            effective_tools = frozenset(contract.allowed_tools) & parent_tools
        run_id = f"child_run_{uuid4().hex}"
        cancellation = Event()
        context = ChildAgentExecutionContext(
            run_id=run_id,
            parent_run_id=contract.parent_run_id,
            goal=contract.goal,
            user_id=contract.user_id,
            session_id=contract.session_id,
            agent_mode=contract.agent_mode,
            allowed_tools=effective_tools,
            access_mode=effective_child_access,
            input_refs=contract.input_refs,
            output_contract=contract.output_contract,
            cancellation=cancellation,
            category=contract.category,
            name=contract.name,
        )
        record = ChildAgentRecord(
            run_id=run_id,
            contract=contract,
            effective_tools=effective_tools,
            effective_access_mode=effective_child_access,
            context=context,
        )
        with self._lock:
            self._records[run_id] = record
            self._result_queues[contract.parent_run_id]
        self._emit("child_agent.created", record)

        future = self._executor.submit(self._run, record, executor)
        with self._lock:
            self._futures[run_id] = future
        if contract.mode == "foreground":
            future.result()
        return record

    def get(self, run_id: str) -> ChildAgentRecord | None:
        """按运行 ID 查询子 Agent 当前记录。"""

        with self._lock:
            return self._records.get(run_id)

    def list_children(self, parent_run_id: str) -> list[ChildAgentRecord]:
        """列出指定父 Agent 创建的全部子 Agent。"""

        with self._lock:
            return [
                record
                for record in self._records.values()
                if record.contract.parent_run_id == parent_run_id
            ]

    def list_children_for_session(self, session_id: str) -> list[ChildAgentRecord]:
        """列出指定主会话创建的子 Agent。"""

        with self._lock:
            return [
                record
                for record in self._records.values()
                if record.contract.session_id == session_id
            ]

    def drain_results(self, parent_run_id: str) -> list[ChildAgentResult]:
        """读取并清空指定父 Agent 的结果队列。"""

        result_queue = self._result_queues[parent_run_id]
        results: list[ChildAgentResult] = []
        while True:
            try:
                results.append(result_queue.get_nowait())
            except Empty:
                return results

    def drain_results_for_session(self, session_id: str) -> list[ChildAgentResult]:
        """读取并清空指定主会话下全部父 Agent 的结果队列。"""

        parent_run_ids = {
            record.contract.parent_run_id
            for record in self.list_children_for_session(session_id)
        }
        results: list[ChildAgentResult] = []
        for parent_run_id in parent_run_ids:
            results.extend(self.drain_results(parent_run_id))
        return results

    def drain_events_for_session(self, session_id: str) -> list[ChildAgentEvent]:
        """读取并清空指定主会话下的子 Agent 生命周期事件。"""

        event_queue = self._event_queues_by_session[session_id]
        events: list[ChildAgentEvent] = []
        while True:
            try:
                events.append(event_queue.get_nowait())
            except Empty:
                return events

    def wait_for_children(
        self,
        *,
        parent_run_id: str,
        run_ids: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> ChildAgentResult | None:
        """
        等待指定父 Agent 下一个子 Agent 产出终态结果。

        run_ids 为空时接收该父 Agent 任意子 Agent 的下一个结果。
        如果结果队列已有匹配结果,立即返回;否则阻塞到下一个结果或超时。
        未匹配 run_ids 的结果会放回队列,避免被错误消费。
        """

        deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
        target_run_ids = set(run_ids or [])
        result_queue = self._result_queues[parent_run_id]
        skipped_results: list[ChildAgentResult] = []
        while True:
            timeout = 0.05
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._restore_skipped_results(parent_run_id, skipped_results)
                    return None
                timeout = min(timeout, remaining)
            try:
                result = result_queue.get(timeout=timeout)
            except Empty:
                if not self._has_pending_children(parent_run_id=parent_run_id, run_ids=target_run_ids):
                    self._restore_skipped_results(parent_run_id, skipped_results)
                    return None
                continue
            if not target_run_ids or result.run_id in target_run_ids:
                self._restore_skipped_results(parent_run_id, skipped_results)
                return result
            skipped_results.append(result)

    def stop(self, run_id: str) -> bool:
        """向子 Agent 发送协作式停止信号。"""

        record = self._require_record(run_id)
        if record.status in {ChildAgentStatus.COMPLETED, ChildAgentStatus.FAILED, ChildAgentStatus.STOPPED}:
            return False
        assert record.context is not None
        record.context.cancellation.set()
        self._emit("child_agent.stop_requested", record)
        return True

    def update_context(self, run_id: str, update: Mapping[str, Any]) -> None:
        """把一条上下文更新排入子 Agent 的下一次安全检查点。"""

        record = self._require_record(run_id)
        if record.status not in {ChildAgentStatus.CREATED, ChildAgentStatus.RUNNING}:
            raise RuntimeError("只有未完成的子 Agent 才能接收上下文更新。")
        assert record.context is not None
        record.context._append_update(update)
        self._emit("child_agent.context_updated", record)

    def close(self) -> None:
        """停止接收新任务并关闭子 Agent 线程池。"""

        with self._lock:
            self._closed = True
            run_ids = list(self._records)
        for run_id in run_ids:
            self.stop(run_id)
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _run(self, record: ChildAgentRecord, executor: ChildAgentExecutor) -> None:
        """在线程池中执行一个子 Agent 并投递最终结果。"""

        assert record.context is not None
        record.status = ChildAgentStatus.RUNNING
        self._emit("child_agent.started", record)
        try:
            value = executor(record.context)
            if record.context.cancellation.is_set():
                raise ChildAgentStopped("子 Agent 在完成前收到停止信号。")
        except ChildAgentStopped as exc:
            result = ChildAgentResult(
                run_id=record.run_id,
                parent_run_id=record.contract.parent_run_id,
                status=ChildAgentStatus.STOPPED,
                error=str(exc),
            )
            record.status = ChildAgentStatus.STOPPED
        except Exception as exc:  # noqa: BLE001
            result = ChildAgentResult(
                run_id=record.run_id,
                parent_run_id=record.contract.parent_run_id,
                status=ChildAgentStatus.FAILED,
                error=str(exc),
            )
            record.status = ChildAgentStatus.FAILED
        else:
            result = ChildAgentResult(
                run_id=record.run_id,
                parent_run_id=record.contract.parent_run_id,
                status=ChildAgentStatus.COMPLETED,
                result=value,
                summary=str(value) if isinstance(value, str) else "",
            )
            record.status = ChildAgentStatus.COMPLETED
        record.result = result
        self._result_queues[record.contract.parent_run_id].put(result)
        self._emit(f"child_agent.{record.status.value}", record)

    def _require_record(self, run_id: str) -> ChildAgentRecord:
        """读取运行记录,不存在时抛出明确错误。"""

        record = self.get(run_id)
        if record is None:
            raise KeyError(f"子 Agent {run_id} 不存在。")
        return record

    def _has_pending_children(self, *, parent_run_id: str, run_ids: set[str]) -> bool:
        """判断指定父 Agent 是否还有目标子 Agent 尚未进入终态。"""

        records = self.list_children(parent_run_id)
        if run_ids:
            records = [record for record in records if record.run_id in run_ids]
        return any(record.status in {ChildAgentStatus.CREATED, ChildAgentStatus.RUNNING} for record in records)

    def _restore_skipped_results(self, parent_run_id: str, results: list[ChildAgentResult]) -> None:
        """把本次等待中跳过的非目标结果放回父 Agent 结果队列。"""

        if not results:
            return
        result_queue = self._result_queues[parent_run_id]
        for result in results:
            result_queue.put(result)

    def _emit(self, event_name: str, record: ChildAgentRecord) -> None:
        """向可选事件观察者发送状态变化。"""

        session_id = record.contract.session_id
        if session_id:
            result = record.result
            self._event_queues_by_session[session_id].put(
                ChildAgentEvent(
                    event_name=event_name,
                    run_id=record.run_id,
                    session_id=session_id,
                    parent_run_id=record.contract.parent_run_id,
                    goal=record.contract.goal,
                    mode=record.contract.mode,
                    status=record.status,
                    access_mode=record.effective_access_mode,
                    allowed_tools=tuple(sorted(record.effective_tools)),
                    created_at=time.time(),
                    category=record.contract.category,
                    name=record.contract.name,
                    summary=result.summary if result is not None else "",
                    result=result.result if result is not None else None,
                    error=result.error if result is not None else None,
                )
            )
        if self._event_callback is not None:
            self._event_callback(event_name, record)
