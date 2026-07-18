"""
LLM 调度器运行时辅助 mixin。

功能说明:
本文件承载 `LLMTaskScheduler` 的底层运行时能力,包括模型实例解析、模型池并发许可、
本地任务重试/超时、队列选择、去重键维护和任务参数校验。

使用说明:
`scheduler.py` 中的 `LLMTaskScheduler` 继承 `LLMTaskRuntimeMixin`。外部业务不直接实例化
本 mixin。
"""

from __future__ import annotations

import queue
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from typing import Any

from langchain_openai import ChatOpenAI

from agent_service.services.scheduler.types import (
    BACKGROUND_FACT_RESOLUTION_TASK,
    BACKGROUND_SUMMARY_TASK,
    FOREGROUND_AGENT_TASK,
    LLMOperation,
    LLMTaskHandle,
    LLMTaskOverloadedError,
    LARGE_MODEL_TIER,
    SMALL_MODEL_TIER,
    SUPPORTED_MODEL_TIERS,
    SUPPORTED_TASK_TYPES,
    ScheduledLLMTask,
)


class LLMTaskRuntimeMixin:
    """
    `LLMTaskScheduler` 的运行时辅助能力集合。

    继承者需要提供 config、task_config、模型缓存、模型信号量、本地队列和去重锁等字段。
    """

    def _get_chat_model(
        self,
        *,
        tool_names: list[str],
        temperature: float | None,
        timeout_seconds: float,
        model_tier: str,
        api_key: str | None = None,
        base_url: str | None = None,
        small_api_key: str | None = None,
        small_base_url: str | None = None,
    ) -> Any:
        """构造或复用与请求匹配的 ChatOpenAI 实例。"""

        model_name, resolved_api_key, resolved_base_url, final_temperature = self._resolve_model_runtime(
            model_tier=model_tier,
            requested_temperature=temperature,
            api_key=api_key,
            base_url=base_url,
            small_api_key=small_api_key,
            small_base_url=small_base_url,
        )
        if not resolved_api_key:
            logger = __import__("logging").getLogger(__name__)
            logger.error(
                "_get_chat_model: MISSING API KEY tier=%s model=%s has_api_key_param=%s has_small_api_key_param=%s",
                model_tier,
                model_name,
                bool(api_key),
                bool(small_api_key),
            )
        cache_key = (
            model_tier,
            tuple(sorted(tool_names)),
            float(final_temperature),
            float(timeout_seconds),
            resolved_api_key,
            resolved_base_url,
        )
        with self._model_cache_lock:
            model = self._model_cache.get(cache_key)
            if model is not None:
                return model
            model_kwargs = self.config.model.get_model_kwargs(model_name)
            model = ChatOpenAI(
                model=model_name,
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                temperature=final_temperature,
                timeout=timeout_seconds,
                max_retries=0,
                **model_kwargs,
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

    def _resolve_model_runtime(
        self,
        *,
        model_tier: str,
        requested_temperature: float | None,
        api_key: str | None = None,
        base_url: str | None = None,
        small_api_key: str | None = None,
        small_base_url: str | None = None,
    ) -> tuple[str, str, str, float]:
        """根据模型池等级解析实际调用所需的模型参数。"""

        if model_tier == SMALL_MODEL_TIER and self.config.model.small_model_name:
            return (
                self.config.model.small_model_name,
                small_api_key or api_key or self.config.model.small_model_api_key or self.config.model.api_key,
                small_base_url or base_url or self.config.model.small_model_base_url or self.config.model.base_url,
                self.config.model.resolve_small_temperature(requested_temperature),
            )
        return (
            self.config.model.model_name,
            api_key or self.config.model.api_key,
            base_url or self.config.model.base_url,
            self.config.model.resolve_primary_temperature(requested_temperature),
        )

    @contextmanager
    def _acquire_model_pool(self, model_tier: str) -> Any:
        """获取指定模型池的并发许可。"""

        semaphore = self._model_semaphores[model_tier]
        semaphore.acquire()
        try:
            yield
        finally:
            semaphore.release()

    def _get_tool_registry(self) -> Any:
        """懒加载工具注册表,避免在模块导入阶段引入环依赖。"""

        if self._tool_registry is not None:
            return self._tool_registry
        from agent_service.tools.tool_registry import ToolRegistry

        self._tool_registry = ToolRegistry.with_builtin_tools(config=self.config)
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
    def _ensure_supported_model_tier(model_tier: str) -> None:
        """校验模型池等级是否合法。"""

        if model_tier not in SUPPORTED_MODEL_TIERS:
            raise ValueError(f"不支持的模型池等级: {model_tier}")

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
            "connection error",
            "connection aborted",
            "server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        )
        return any(token in message for token in retryable_tokens)
