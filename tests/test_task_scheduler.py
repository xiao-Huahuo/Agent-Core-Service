"""
LLM 任务调度器测试脚本。

功能说明:
本文件用于验证 `agent_service.task_schedule` 第一版多级调度器的关键行为,重点覆盖
重试退避、任务去重和结果复用等基础能力,避免后续把主 Agent 与后台任务重新改回
直接调用模型。

使用说明:
在项目根目录执行 `python -m pytest tests/test_task_scheduler.py`。
"""

from __future__ import annotations

from threading import Event
from threading import Thread
import time

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from agent_service.core.agent_config import AgentConfig
from agent_service.services.scheduler import BACKGROUND_SUMMARY_TASK
from agent_service.services.scheduler import FOREGROUND_AGENT_TASK
from agent_service.services.scheduler import SMALL_MODEL_TIER
from agent_service.services.scheduler import get_llm_task_scheduler
from agent_service.services.scheduler import reset_llm_task_schedulers


def make_scheduler_test_config() -> AgentConfig:
    """创建调度器测试专用配置。"""

    return AgentConfig.load_config(
        {
            "task_schedule": {
                "global_max_concurrency": 2,
                "foreground_agent_worker_count": 1,
                "background_summary_worker_count": 1,
                "background_fact_worker_count": 1,
                "foreground_queue_max_size": 8,
                "background_queue_max_size": 8,
                "max_retries": 1,
                "initial_backoff_seconds": 0.01,
                "max_backoff_seconds": 0.02,
                "foreground_timeout_seconds": 3,
                "summary_timeout_seconds": 3,
                "fact_resolution_timeout_seconds": 3,
                "circuit_breaker_failure_threshold": 3,
                "circuit_breaker_recovery_seconds": 1,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )


def teardown_function() -> None:
    """每个测试结束后关闭调度器单例。"""

    reset_llm_task_schedulers()


def test_llm_task_scheduler_retries_retryable_error() -> None:
    """验证调度器会对 overload/429 类错误进行重试。"""

    scheduler = get_llm_task_scheduler(make_scheduler_test_config())
    attempts = {"count": 0}

    def flaky_operation() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("429 Too Many Requests")
        return "ok"

    result = scheduler.run(task_type=FOREGROUND_AGENT_TASK, operation=flaky_operation)

    assert result == "ok"
    assert attempts["count"] == 2


def test_llm_task_scheduler_deduplicates_summary_task_by_session() -> None:
    """验证同一 session 的 summary 任务会合并到同一个执行实例。"""

    scheduler = get_llm_task_scheduler(make_scheduler_test_config())
    started = Event()
    release = Event()
    calls = {"count": 0}

    def slow_summary() -> str:
        calls["count"] += 1
        started.set()
        release.wait(timeout=2)
        return "summary-ok"

    results: list[str] = []

    first_handle = scheduler.submit(
        task_type=BACKGROUND_SUMMARY_TASK,
        operation=slow_summary,
        dedup_key="session-1",
    )
    assert started.wait(timeout=1)

    def wait_duplicate() -> None:
        duplicate_handle = scheduler.submit(
            task_type=BACKGROUND_SUMMARY_TASK,
            operation=slow_summary,
            dedup_key="session-1",
        )
        results.append(duplicate_handle.wait(timeout=2))

    duplicate_thread = Thread(target=wait_duplicate, daemon=True)
    duplicate_thread.start()
    time.sleep(0.05)
    release.set()

    results.append(first_handle.wait(timeout=2))
    duplicate_thread.join(timeout=2)

    assert calls["count"] == 1
    assert results == ["summary-ok", "summary-ok"]


def test_llm_task_scheduler_invoke_chat_uses_local_fallback_without_redis(monkeypatch: object) -> None:
    """验证未配置 Redis 时,可序列化 Chat 请求会回退到本地队列执行。"""

    scheduler = get_llm_task_scheduler(make_scheduler_test_config())

    def fake_invoke_chat_request(_request: object) -> AIMessage:
        return AIMessage(content="chat-ok")

    monkeypatch.setattr(scheduler, "_invoke_chat_request", fake_invoke_chat_request)

    response = scheduler.invoke_chat(
        task_type=FOREGROUND_AGENT_TASK,
        messages=[HumanMessage(content="你好")],
    )

    assert isinstance(response, AIMessage)
    assert response.content == "chat-ok"


def test_llm_task_scheduler_submit_summary_job_uses_local_fallback_without_redis(monkeypatch: object) -> None:
    """验证未配置 Redis 时,Summary 业务任务会回退到本地队列执行。"""

    scheduler = get_llm_task_scheduler(make_scheduler_test_config())

    def fake_run_summary_business_task(*, user_id: str, session_id: str) -> str:
        return f"{user_id}:{session_id}"

    monkeypatch.setattr(scheduler, "_run_summary_business_task", fake_run_summary_business_task)

    handle = scheduler.submit_summary_job(user_id="u1", session_id="s1", dedup_key="s1")

    assert handle.wait(timeout=2) == "u1:s1"


def test_llm_task_scheduler_resolves_small_model_runtime() -> None:
    """验证调度器会为 `small` 模型池解析独立的小模型配置。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "large-model",
                "api_key": "large-key",
                "base_url": "https://large.example.com/v1",
                "small_model_name": "small-model",
                "small_model_api_key": "small-key",
                "small_model_base_url": "https://small.example.com/v1",
                "small_model_temperature": 0.3,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    scheduler = get_llm_task_scheduler(config)

    model_name, api_key, base_url, temperature = scheduler._resolve_model_runtime(
        model_tier=SMALL_MODEL_TIER,
        requested_temperature=None,
    )

    assert model_name == "small-model"
    assert api_key == "small-key"
    assert base_url == "https://small.example.com/v1"
    assert temperature == 0.3
