"""Background runner that turns claimed queue tasks into independent Agent sessions."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.services.agent_queue_service import AgentQueueService

logger = logging.getLogger(__name__)


class AgentQueueScheduler:
    """Poll durable queue tasks and execute each claimed task without sharing sessions."""

    def __init__(self, *, queue_service: AgentQueueService, agent: Any, poll_seconds: float | None = None) -> None:
        limits = getattr(getattr(agent, "config", None), "limits", DEFAULT_BUSINESS_LIMITS)
        configured_poll = limits.agent_queue_poll_seconds if poll_seconds is None else poll_seconds
        self.limits = limits
        self.queue_service, self.agent, self.poll_seconds = queue_service, agent, max(limits.agent_queue_min_poll_seconds, configured_poll)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=limits.agent_queue_worker_count,
            thread_name_prefix="agent-queue",
        )

    def start(self) -> None:
        """Start the single queue dispatcher."""
        if self._thread and self._thread.is_alive(): return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="agent-queue-scheduler", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        """Stop new claims and wait for already running Agent calls."""
        self._stop_event.set()
        if self._thread: self._thread.join(timeout=self.limits.agent_queue_shutdown_timeout_seconds)
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _run_loop(self) -> None:
        """Dispatch every user that currently has pending work."""
        while not self._stop_event.is_set():
            try:
                for user_id in self.queue_service.pending_user_ids():
                    while (claim := self.queue_service.claim_next(user_id)) is not None:
                        self._executor.submit(self._execute, claim)
            except Exception:
                logger.exception("Agent queue scheduling failed")
            self._stop_event.wait(self.poll_seconds)

    def _execute(self, task: dict[str, Any]) -> None:
        """Run one task and move it to review unless it was manually terminated."""
        try:
            self.agent.run_session_prompt(
                prompt="请先创建任务列表，再按列表完成此独立任务。\n\n" + str(task["prompt"]),
                user_id=str(task["user_id"]), session_id=str(task["session_id"]), agent_mode="auto", agent_access_mode="sandbox",
            )
            self.queue_service.finish(str(task["task_id"]), "review")
        except Exception:
            logger.exception("Agent queue task failed | task=%s", task["task_id"])
            self.queue_service.finish(str(task["task_id"]), "review")
