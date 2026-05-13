"""
LLM 多级任务队列调度器模块。

功能说明:
本文件实现统一 `LLMTaskScheduler`。它同时支持两类执行路径:

1. 本地 generic 队列:
   用于当前进程内不可序列化的普通后台任务,例如 `SummaryNode` 触发的摘要业务入口。
2. Redis Chat 队列:
   用于真正的 LLM 请求。请求会被序列化为消息列表、工具名和推理参数,写入 Redis Stream,
   由 worker 消费并执行 `ChatOpenAI.invoke(...)`,再将结果回写 Redis。

这样做的原因是: Python callable 不能跨进程放入 Redis 队列,但项目里所有真正的 LLM
调用都可以抽象成“可序列化的 chat request”,因此可以在不破坏现有业务结构的前提下,
把 LLM 资源调度升级为生产可扩展模式。

使用说明:
- 普通本地任务继续使用 `run(...)` / `submit(...)`
- 所有 LLM 调用必须使用 `invoke_chat(...)` / `submit_chat(...)`
"""

from __future__ import annotations

import atexit
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
import itertools
import queue
import random
import threading
import time
from typing import Any
from uuid import uuid4
import sys

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from agent_service.core.agent_config import AgentConfig
from agent_service.task_schedule.circuit_breaker import CircuitBreaker, RedisCircuitBreakerStore
from agent_service.task_schedule.redis_backend import (
    RedisStreamLLMBackend,
    SerializedChatRequest,
    SerializedChatResult,
    SerializedSummaryJobRequest,
    SerializedSummaryJobResult,
)


LLMOperation = Callable[[], Any]
FOREGROUND_AGENT_TASK = "foreground_agent"
BACKGROUND_SUMMARY_TASK = "background_summary"
BACKGROUND_FACT_RESOLUTION_TASK = "background_fact_resolution"
SUPPORTED_TASK_TYPES = {
    FOREGROUND_AGENT_TASK,
    BACKGROUND_SUMMARY_TASK,
    BACKGROUND_FACT_RESOLUTION_TASK,
}


class LLMTaskSchedulerError(RuntimeError):
    """LLM 调度器基础异常。"""


class LLMTaskOverloadedError(LLMTaskSchedulerError):
    """调度队列或熔断器拒绝新任务时抛出的异常。"""


@dataclass(slots=True)
class LLMTaskHandle:
    """
    调度任务句柄。

    task_id: 调度任务 ID。
    task_type: 任务类型。
    future: 对应的本地 Future。
    result_loader: 可选的外部结果加载函数,用于 Redis 分布式结果等待。
    """

    task_id: str
    task_type: str
    future: Future[Any]
    result_loader: Callable[[float | None], Any] | None = None

    def wait(self, timeout: float | None = None) -> Any:
        """等待任务完成并返回结果。"""

        if self.future.done():
            return self.future.result(timeout=timeout)
        if self.result_loader is not None:
            result = self.result_loader(timeout)
            if not self.future.done():
                self.future.set_result(result)
            return result
        return self.future.result(timeout=timeout)

    def join(self, timeout: float | None = None) -> Any:
        """兼容线程风格的等待接口。"""

        return self.wait(timeout=timeout)


@dataclass(slots=True)
class ScheduledLLMTask:
    """
    本地 generic 队列任务对象。

    sequence: 单调递增序号。
    task_id: 任务 ID。
    task_type: 任务类型。
    operation: 实际执行函数。
    timeout_seconds: 超时时间。
    max_retries: 最大重试次数。
    dedup_key: 可选去重键。
    future: 对应 Future。
    """

    sequence: int
    task_id: str
    task_type: str
    operation: LLMOperation
    timeout_seconds: float
    max_retries: int
    dedup_key: str | None
    future: Future[Any] = field(default_factory=Future)


class LLMTaskScheduler:
    """
    统一 LLM 调度器。

    config: 全局配置对象。
    """

    def __init__(self, *, config: AgentConfig) -> None:
        """初始化本地队列、Redis backend、worker 池和熔断器。"""

        self.config = config
        self.task_config = config.task_schedule
        self._sequence = itertools.count()
        self._shutdown_event = threading.Event()
        self._global_semaphore = threading.Semaphore(max(self.task_config.global_max_concurrency, 1))
        self._dedup_lock = threading.Lock()
        self._dedup_handles: dict[str, LLMTaskHandle] = {}
        self._tool_registry: Any | None = None
        self._model_cache_lock = threading.Lock()
        self._model_cache: dict[tuple[tuple[str, ...], float, float], Any] = {}
        self._local_foreground_queue: queue.Queue[ScheduledLLMTask] = queue.Queue(
            maxsize=max(self.task_config.foreground_queue_max_size, 1)
        )
        self._local_summary_queue: queue.Queue[ScheduledLLMTask] = queue.Queue(
            maxsize=max(self.task_config.background_queue_max_size, 1)
        )
        self._local_fact_queue: queue.Queue[ScheduledLLMTask] = queue.Queue(
            maxsize=max(self.task_config.background_queue_max_size, 1)
        )
        self._backend: RedisStreamLLMBackend | None = None
        store = None
        if self.task_config.redis_url:
            store = RedisCircuitBreakerStore(
                redis_url=self.task_config.redis_url,
                key_prefix=self.task_config.redis_prefix,
            )
            self._backend = RedisStreamLLMBackend(
                redis_url=self.task_config.redis_url,
                key_prefix=self.task_config.redis_prefix,
                consumer_group=self.task_config.redis_consumer_group,
                result_ttl_seconds=self.task_config.redis_result_ttl_seconds,
                dedup_ttl_seconds=self.task_config.redis_dedup_ttl_seconds,
                block_timeout_ms=self.task_config.redis_block_timeout_ms,
                visibility_timeout_ms=self.task_config.redis_visibility_timeout_seconds * 1000,
                result_poll_interval_seconds=self.task_config.redis_result_poll_interval_seconds,
                stream_maxlen=self.task_config.redis_stream_maxlen,
            )
        self._circuit_breakers = {
            FOREGROUND_AGENT_TASK: CircuitBreaker(
                name=FOREGROUND_AGENT_TASK,
                failure_threshold=self.task_config.circuit_breaker_failure_threshold,
                recovery_seconds=self.task_config.circuit_breaker_recovery_seconds,
                store=store,
            ),
            BACKGROUND_SUMMARY_TASK: CircuitBreaker(
                name=BACKGROUND_SUMMARY_TASK,
                failure_threshold=self.task_config.circuit_breaker_failure_threshold,
                recovery_seconds=self.task_config.circuit_breaker_recovery_seconds,
                store=store,
            ),
            BACKGROUND_FACT_RESOLUTION_TASK: CircuitBreaker(
                name=BACKGROUND_FACT_RESOLUTION_TASK,
                failure_threshold=self.task_config.circuit_breaker_failure_threshold,
                recovery_seconds=self.task_config.circuit_breaker_recovery_seconds,
                store=store,
            ),
        }
        self._local_worker_threads = self._start_local_workers()
        self._redis_worker_threads = self._start_redis_workers()

    def run(
        self,
        *,
        task_type: str,
        operation: LLMOperation,
        dedup_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        """
        提交并同步等待一个本地 generic 任务。

        该入口保留给不可序列化的本地业务任务,不用于真正的 LLM 调用。
        """

        handle = self.submit(
            task_type=task_type,
            operation=operation,
            dedup_key=dedup_key,
            timeout_seconds=timeout_seconds,
        )
        return handle.wait()

    def submit(
        self,
        *,
        task_type: str,
        operation: LLMOperation,
        dedup_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMTaskHandle:
        """
        提交一个本地 generic 异步任务。

        该入口保留给不可序列化的本地业务任务,不用于真正的 LLM 调用。
        """

        self._ensure_supported_task_type(task_type)
        actual_dedup_key = self._normalize_dedup_key(task_type=task_type, dedup_key=dedup_key)
        if actual_dedup_key is not None:
            existing_handle = self._get_existing_local_dedup_handle(actual_dedup_key)
            if existing_handle is not None:
                return existing_handle
        task = ScheduledLLMTask(
            sequence=next(self._sequence),
            task_id=f"llm_task_{uuid4().hex}",
            task_type=task_type,
            operation=operation,
            timeout_seconds=timeout_seconds or self._resolve_timeout_seconds(task_type),
            max_retries=max(self.task_config.max_retries, 0),
            dedup_key=actual_dedup_key,
        )
        handle = LLMTaskHandle(task_id=task.task_id, task_type=task.task_type, future=task.future)
        if actual_dedup_key is not None:
            with self._dedup_lock:
                existing_handle = self._dedup_handles.get(actual_dedup_key)
                if existing_handle is not None:
                    return existing_handle
                self._dedup_handles[actual_dedup_key] = handle
        try:
            self._enqueue_local_task(task)
        except Exception:
            self._release_local_dedup_key(actual_dedup_key, handle)
            raise
        return handle

    def invoke_chat(
        self,
        *,
        task_type: str,
        messages: Sequence[BaseMessage],
        tool_names: list[str] | None = None,
        dedup_key: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
    ) -> BaseMessage:
        """提交并同步等待一个可序列化的 LLM Chat 请求。"""

        handle = self.submit_chat(
            task_type=task_type,
            messages=messages,
            tool_names=tool_names,
            dedup_key=dedup_key,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )
        return handle.wait(timeout=timeout_seconds)

    def submit_chat(
        self,
        *,
        task_type: str,
        messages: Sequence[BaseMessage],
        tool_names: list[str] | None = None,
        dedup_key: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
    ) -> LLMTaskHandle:
        """提交一个可序列化的 LLM Chat 请求。"""

        self._ensure_supported_task_type(task_type)
        actual_dedup_key = self._normalize_dedup_key(task_type=task_type, dedup_key=dedup_key)
        if not self._circuit_breakers[task_type].allow_request():
            raise LLMTaskOverloadedError(f"任务类型 {task_type} 当前处于熔断状态,暂时拒绝新请求。")
        request = SerializedChatRequest.from_messages(
            task_id=f"llm_chat_{uuid4().hex}",
            task_type=task_type,
            messages=list(messages),
            tool_names=tool_names or [],
            timeout_seconds=timeout_seconds or self._resolve_timeout_seconds(task_type),
            max_retries=max(self.task_config.max_retries, 0),
            dedup_key=actual_dedup_key,
            temperature=temperature,
        )
        if self._backend is None:
            return self._submit_local_chat_request(request)
        return self._submit_redis_chat_request(request)

    def submit_summary_job(
        self,
        *,
        user_id: str,
        session_id: str,
        dedup_key: str | None = None,
    ) -> LLMTaskHandle:
        """
        提交一个持久化的 Summary 业务任务。

        在启用 Redis backend 时,任务会被写入专用 Redis Stream,即使当前服务实例退出,
        其他实例或重启后的实例也可以继续消费处理。
        """

        actual_dedup_key = self._normalize_dedup_key(
            task_type=BACKGROUND_SUMMARY_TASK,
            dedup_key=dedup_key or session_id,
        )
        request = SerializedSummaryJobRequest(
            task_id=f"summary_job_{uuid4().hex}",
            user_id=user_id,
            session_id=session_id,
            dedup_key=actual_dedup_key,
        )
        if self._backend is None:
            return self.submit(
                task_type=BACKGROUND_SUMMARY_TASK,
                operation=lambda: self._run_summary_business_task(
                    user_id=user_id,
                    session_id=session_id,
                ),
                dedup_key=actual_dedup_key,
                timeout_seconds=self._resolve_timeout_seconds(BACKGROUND_SUMMARY_TASK),
            )
        effective_task_id = request.task_id
        if request.dedup_key is not None:
            effective_task_id = self._backend.register_dedup_or_get_existing(
                dedup_key=request.dedup_key,
                task_id=request.task_id,
            )
        handle = LLMTaskHandle(
            task_id=effective_task_id,
            task_type=BACKGROUND_SUMMARY_TASK,
            future=Future(),
            result_loader=lambda timeout: self._backend.wait_for_summary_result(
                task_id=effective_task_id,
                timeout=timeout,
            ),
        )
        if effective_task_id != request.task_id:
            return handle
        try:
            queue_max_size = self._resolve_queue_max_size(BACKGROUND_SUMMARY_TASK)
            self._backend.enqueue_summary_job(request, queue_max_size=queue_max_size)
        except Exception:
            self._backend.release_dedup_if_owner(dedup_key=request.dedup_key, task_id=request.task_id)
            raise
        return handle

    def shutdown(self) -> None:
        """停止 worker 线程。"""

        self._shutdown_event.set()
        for worker in self._local_worker_threads:
            worker.join(timeout=1.0)
        for worker in self._redis_worker_threads:
            worker.join(timeout=1.0)

    def supports_persistent_summary_jobs(self) -> bool:
        """返回当前调度器是否启用了 Redis 持久化 Summary 业务任务。"""

        return self._backend is not None

    def _submit_local_chat_request(self, request: SerializedChatRequest) -> LLMTaskHandle:
        """将 Chat 请求回退为本地 generic 队列任务。"""

        task = ScheduledLLMTask(
            sequence=next(self._sequence),
            task_id=request.task_id,
            task_type=request.task_type,
            operation=lambda: self._invoke_chat_request(request),
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
            dedup_key=request.dedup_key,
        )
        handle = LLMTaskHandle(task_id=task.task_id, task_type=task.task_type, future=task.future)
        if request.dedup_key is not None:
            with self._dedup_lock:
                existing_handle = self._dedup_handles.get(request.dedup_key)
                if existing_handle is not None:
                    return existing_handle
                self._dedup_handles[request.dedup_key] = handle
        try:
            self._enqueue_local_task(task)
        except Exception:
            self._release_local_dedup_key(request.dedup_key, handle)
            raise
        return handle

    def _submit_redis_chat_request(self, request: SerializedChatRequest) -> LLMTaskHandle:
        """将 Chat 请求写入 Redis Stream。"""

        assert self._backend is not None
        effective_task_id = request.task_id
        if request.dedup_key is not None:
            effective_task_id = self._backend.register_dedup_or_get_existing(
                dedup_key=request.dedup_key,
                task_id=request.task_id,
            )
        handle = LLMTaskHandle(
            task_id=effective_task_id,
            task_type=request.task_type,
            future=Future(),
            result_loader=lambda timeout: self._backend.wait_for_result(
                task_id=effective_task_id,
                timeout=timeout,
            ),
        )
        if effective_task_id != request.task_id:
            return handle
        try:
            queue_max_size = self._resolve_queue_max_size(request.task_type)
            self._backend.enqueue_chat_request(request, queue_max_size=queue_max_size)
        except Exception:
            self._backend.release_dedup_if_owner(dedup_key=request.dedup_key, task_id=request.task_id)
            raise
        return handle

    def _start_local_workers(self) -> list[threading.Thread]:
        """启动本地 generic 队列 worker。"""

        workers: list[threading.Thread] = []
        for index in range(max(self.task_config.foreground_agent_worker_count, 1)):
            worker = threading.Thread(
                target=self._local_foreground_worker_loop,
                daemon=True,
                name=f"llm-local-foreground-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        for index in range(max(self.task_config.background_summary_worker_count, 1)):
            worker = threading.Thread(
                target=self._local_summary_worker_loop,
                daemon=True,
                name=f"llm-local-summary-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        for index in range(max(self.task_config.background_fact_worker_count, 1)):
            worker = threading.Thread(
                target=self._local_fact_worker_loop,
                daemon=True,
                name=f"llm-local-fact-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        return workers

    def _start_redis_workers(self) -> list[threading.Thread]:
        """在启用 Redis backend 时启动对应的 Stream worker。"""

        if self._backend is None:
            return []
        workers: list[threading.Thread] = []
        for index in range(max(self.task_config.foreground_agent_worker_count, 1)):
            worker = threading.Thread(
                target=self._redis_worker_loop,
                kwargs={"task_type": FOREGROUND_AGENT_TASK, "consumer_name": f"fg-{uuid4().hex[:8]}-{index}"},
                daemon=True,
                name=f"llm-redis-foreground-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        for index in range(max(self.task_config.background_summary_worker_count, 1)):
            worker = threading.Thread(
                target=self._redis_worker_loop,
                kwargs={"task_type": BACKGROUND_SUMMARY_TASK, "consumer_name": f"sum-{uuid4().hex[:8]}-{index}"},
                daemon=True,
                name=f"llm-redis-summary-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        for index in range(max(self.task_config.background_summary_worker_count, 1)):
            worker = threading.Thread(
                target=self._redis_summary_business_worker_loop,
                kwargs={"consumer_name": f"sum-job-{uuid4().hex[:8]}-{index}"},
                daemon=True,
                name=f"llm-redis-summary-business-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        for index in range(max(self.task_config.background_fact_worker_count, 1)):
            worker = threading.Thread(
                target=self._redis_worker_loop,
                kwargs={"task_type": BACKGROUND_FACT_RESOLUTION_TASK, "consumer_name": f"fact-{uuid4().hex[:8]}-{index}"},
                daemon=True,
                name=f"llm-redis-fact-worker-{index}",
            )
            worker.start()
            workers.append(worker)
        return workers

    def _local_foreground_worker_loop(self) -> None:
        """本地主循环队列 worker。"""

        self._consume_local_queue(self._local_foreground_queue)

    def _local_summary_worker_loop(self) -> None:
        """本地 Summary 队列 worker。"""

        self._consume_local_queue(self._local_summary_queue)

    def _local_fact_worker_loop(self) -> None:
        """本地 Fact 队列 worker。"""

        self._consume_local_queue(self._local_fact_queue)

    def _consume_local_queue(self, task_queue: queue.Queue[ScheduledLLMTask]) -> None:
        """从指定本地队列持续消费 generic 任务。"""

        while not self._shutdown_event.is_set():
            try:
                task = task_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._execute_local_task(task)
            finally:
                task_queue.task_done()

    def _execute_local_task(self, task: ScheduledLLMTask) -> None:
        """执行一个本地 generic 任务。"""

        breaker = self._circuit_breakers[task.task_type]
        try:
            with self._global_semaphore:
                result = self._run_with_retries(task)
        except Exception as exc:  # noqa: BLE001
            breaker.record_failure()
            if not task.future.done():
                task.future.set_exception(exc)
            self._release_local_dedup_key(task.dedup_key, None)
            return
        breaker.record_success()
        if not task.future.done():
            task.future.set_result(result)
        self._release_local_dedup_key(task.dedup_key, None)

    def _redis_worker_loop(self, *, task_type: str, consumer_name: str) -> None:
        """持续消费 Redis Stream 中的 Chat 请求。"""

        assert self._backend is not None
        while not self._shutdown_event.is_set():
            item = self._backend.read_next_request(task_type=task_type, consumer_name=consumer_name)
            if item is None:
                continue
            entry_id, request = item
            self._execute_redis_chat_request(entry_id=entry_id, request=request)

    def _redis_summary_business_worker_loop(self, *, consumer_name: str) -> None:
        """持续消费 Redis Stream 中的 Summary 业务任务。"""

        assert self._backend is not None
        while not self._shutdown_event.is_set():
            item = self._backend.read_next_summary_job(consumer_name=consumer_name)
            if item is None:
                continue
            entry_id, request = item
            self._execute_redis_summary_job(entry_id=entry_id, request=request)

    def _execute_redis_chat_request(self, *, entry_id: str, request: SerializedChatRequest) -> None:
        """执行单条 Redis Chat 请求并写回结果。"""

        assert self._backend is not None
        breaker = self._circuit_breakers[request.task_type]
        try:
            with self._global_semaphore:
                task = ScheduledLLMTask(
                    sequence=next(self._sequence),
                    task_id=request.task_id,
                    task_type=request.task_type,
                    operation=lambda: self._invoke_chat_request(request),
                    timeout_seconds=request.timeout_seconds,
                    max_retries=request.max_retries,
                    dedup_key=request.dedup_key,
                )
                message = self._run_with_retries(task)
        except Exception as exc:  # noqa: BLE001
            breaker.record_failure()
            self._backend.write_result(task_id=request.task_id, result=SerializedChatResult.from_exception(exc))
            self._backend.release_dedup_if_owner(dedup_key=request.dedup_key, task_id=request.task_id)
            self._backend.ack_and_delete(task_type=request.task_type, entry_id=entry_id)
            return
        breaker.record_success()
        self._backend.write_result(task_id=request.task_id, result=SerializedChatResult.from_message(message))
        self._backend.release_dedup_if_owner(dedup_key=request.dedup_key, task_id=request.task_id)
        self._backend.ack_and_delete(task_type=request.task_type, entry_id=entry_id)

    def _execute_redis_summary_job(self, *, entry_id: str, request: SerializedSummaryJobRequest) -> None:
        """执行单条 Redis Summary 业务任务并写回结果。"""

        assert self._backend is not None
        try:
            summary_text = self._run_summary_business_task(
                user_id=request.user_id,
                session_id=request.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._backend.write_result(
                task_id=request.task_id,
                result=SerializedSummaryJobResult.from_exception(exc),
            )
            self._backend.release_dedup_if_owner(dedup_key=request.dedup_key, task_id=request.task_id)
            self._backend.ack_and_delete_summary_job(entry_id=entry_id)
            return
        self._backend.write_result(
            task_id=request.task_id,
            result=SerializedSummaryJobResult.from_summary(summary_text),
        )
        self._backend.release_dedup_if_owner(dedup_key=request.dedup_key, task_id=request.task_id)
        self._backend.ack_and_delete_summary_job(entry_id=entry_id)

    def _invoke_chat_request(self, request: SerializedChatRequest) -> BaseMessage:
        """根据序列化请求构造模型并执行真实 Chat 调用。"""

        messages = request.restore_messages()
        model = self._get_chat_model(
            tool_names=request.tool_names,
            temperature=request.temperature,
            timeout_seconds=request.timeout_seconds,
        )
        response = model.invoke(messages)
        if not isinstance(response, BaseMessage):
            raise TypeError("ChatOpenAI.invoke 未返回 LangChain BaseMessage。")
        return response

    def _run_summary_business_task(self, *, user_id: str, session_id: str) -> str | None:
        """执行 Summary 业务任务。"""

        from agent_service.services.memory.summary_service import SessionSummaryService

        summary_service = SessionSummaryService(
            config=self.config,
            task_scheduler=self,
        )
        return summary_service.summarize_session(user_id=user_id, session_id=session_id)

    def _get_chat_model(
        self,
        *,
        tool_names: list[str],
        temperature: float | None,
        timeout_seconds: float,
    ) -> Any:
        """构造或复用与请求匹配的 ChatOpenAI 实例。"""

        final_temperature = self.config.model.resolve_primary_temperature(temperature)
        cache_key = (tuple(sorted(tool_names)), float(final_temperature), float(timeout_seconds))
        with self._model_cache_lock:
            model = self._model_cache.get(cache_key)
            if model is not None:
                return model
            model = ChatOpenAI(
                model=self.config.model.model_name,
                api_key=self.config.model.api_key,
                base_url=self.config.model.base_url,
                temperature=final_temperature,
                timeout=timeout_seconds,
            )
            if tool_names:
                tool_registry = self._get_tool_registry()
                tools = [
                    tool
                    for tool in tool_registry.to_langchain_tools()
                    if tool.name in set(tool_names)
                ]
                if tools:
                    model = model.bind_tools(tools)
            self._model_cache[cache_key] = model
            return model

    def _get_tool_registry(self) -> Any:
        """懒加载工具注册表,避免在模块导入阶段引入环依赖。"""

        if self._tool_registry is not None:
            return self._tool_registry
        from agent_service.tools.tool_registry import ToolRegistry

        self._tool_registry = ToolRegistry.with_builtin_tools()
        return self._tool_registry

    def _run_with_retries(self, task: ScheduledLLMTask) -> Any:
        """执行任务并对可恢复错误做指数退避重试。"""

        attempt = 0
        last_error: Exception | None = None
        while attempt <= task.max_retries:
            try:
                return self._run_with_timeout(task)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= task.max_retries or not self._is_retryable_error(exc):
                    raise
                backoff_seconds = min(
                    self.task_config.initial_backoff_seconds * (2**attempt),
                    self.task_config.max_backoff_seconds,
                )
                jitter = random.uniform(0.0, backoff_seconds * 0.2)
                time.sleep(backoff_seconds + jitter)
                attempt += 1
        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM 任务重试失败但没有异常信息。")

    @staticmethod
    def _run_operation_future(operation: LLMOperation) -> Any:
        """作为线程池 target 包装实际操作。"""

        return operation()

    def _run_with_timeout(self, task: ScheduledLLMTask) -> Any:
        """使用受控超时执行实际操作。"""

        if self._shutdown_event.is_set() or sys.is_finalizing():
            raise RuntimeError("LLM 调度器正在关闭,不再接受新的本地执行任务。")
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{task.task_type}-call") as executor:
            future = executor.submit(self._run_operation_future, task.operation)
            try:
                return future.result(timeout=task.timeout_seconds)
            except FutureTimeoutError as exc:
                future.cancel()
                raise TimeoutError(
                    f"LLM 任务 {task.task_type} 超时,超过 {task.timeout_seconds} 秒仍未完成。"
                ) from exc

    def _enqueue_local_task(self, task: ScheduledLLMTask) -> None:
        """将任务放入对应本地等级队列。"""

        target_queue = self._resolve_local_queue(task.task_type)
        try:
            target_queue.put_nowait(task)
        except queue.Full as exc:
            if task.task_type != FOREGROUND_AGENT_TASK and self.task_config.drop_low_priority_when_overloaded:
                raise LLMTaskOverloadedError(f"后台本地队列已满,拒绝任务 {task.task_type}。") from exc
            raise LLMTaskOverloadedError(f"本地 LLM 队列已满,无法提交任务 {task.task_type}。") from exc

    def _resolve_local_queue(self, task_type: str) -> queue.Queue[ScheduledLLMTask]:
        """根据任务类型返回目标本地队列。"""

        if task_type == FOREGROUND_AGENT_TASK:
            return self._local_foreground_queue
        if task_type == BACKGROUND_SUMMARY_TASK:
            return self._local_summary_queue
        return self._local_fact_queue

    def _resolve_timeout_seconds(self, task_type: str) -> float:
        """根据任务类型返回默认超时。"""

        if task_type == FOREGROUND_AGENT_TASK:
            return float(self.task_config.foreground_timeout_seconds)
        if task_type == BACKGROUND_SUMMARY_TASK:
            return float(self.task_config.summary_timeout_seconds)
        if task_type == BACKGROUND_FACT_RESOLUTION_TASK:
            return float(self.task_config.fact_resolution_timeout_seconds)
        return float(self.task_config.default_timeout_seconds)

    def _resolve_queue_max_size(self, task_type: str) -> int:
        """根据任务类型返回 Redis 队列最大长度。"""

        if task_type == FOREGROUND_AGENT_TASK:
            return max(self.task_config.foreground_queue_max_size, 1)
        return max(self.task_config.background_queue_max_size, 1)

    def _normalize_dedup_key(self, *, task_type: str, dedup_key: str | None) -> str | None:
        """标准化去重键。"""

        if not dedup_key:
            return None
        if task_type == BACKGROUND_SUMMARY_TASK and not self.task_config.summary_deduplicate_by_session:
            return None
        return f"{task_type}:{dedup_key}"

    def _get_existing_local_dedup_handle(self, dedup_key: str) -> LLMTaskHandle | None:
        """读取仍在执行中的本地去重句柄。"""

        with self._dedup_lock:
            handle = self._dedup_handles.get(dedup_key)
            if handle is None:
                return None
            if handle.future.done():
                self._dedup_handles.pop(dedup_key, None)
                return None
            return handle

    def _release_local_dedup_key(self, dedup_key: str | None, handle: LLMTaskHandle | None) -> None:
        """释放本地去重键。"""

        if dedup_key is None:
            return
        with self._dedup_lock:
            current = self._dedup_handles.get(dedup_key)
            if handle is None or current is handle:
                self._dedup_handles.pop(dedup_key, None)

    @staticmethod
    def _ensure_supported_task_type(task_type: str) -> None:
        """校验任务类型是否合法。"""

        if task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError(f"不支持的 LLM 调度任务类型: {task_type}")

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """判断一个异常是否适合自动重试。"""

        if isinstance(exc, TimeoutError):
            return True
        message = str(exc).lower()
        retryable_tokens = (
            "429",
            "rate limit",
            "too many requests",
            "overload",
            "timeout",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        )
        return any(token in message for token in retryable_tokens)


_SCHEDULER_REGISTRY: dict[str, LLMTaskScheduler] = {}
_SCHEDULER_REGISTRY_LOCK = threading.Lock()


def get_llm_task_scheduler(config: AgentConfig) -> LLMTaskScheduler:
    """获取按项目路径缓存的进程内调度器单例。"""

    scheduler_key = f"{config.storage.project_root}|{config.task_schedule.redis_url}"
    with _SCHEDULER_REGISTRY_LOCK:
        scheduler = _SCHEDULER_REGISTRY.get(scheduler_key)
        if scheduler is not None:
            return scheduler
        scheduler = LLMTaskScheduler(config=config)
        _SCHEDULER_REGISTRY[scheduler_key] = scheduler
        return scheduler


def reset_llm_task_schedulers() -> None:
    """关闭并清空当前进程中的调度器注册表,主要供测试使用。"""

    with _SCHEDULER_REGISTRY_LOCK:
        for scheduler in _SCHEDULER_REGISTRY.values():
            scheduler.shutdown()
        _SCHEDULER_REGISTRY.clear()


atexit.register(reset_llm_task_schedulers)
