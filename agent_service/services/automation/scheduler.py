"""
自动化任务后台调度器。

功能说明:
- 周期性从数据库抢占到期自动化任务。
- 为每次运行创建独立 Agent 会话并消费完整执行结果。
- 将成功、失败和输出回写到 AutomationService。
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.schemas.session import SessionCreate
from agent_service.services.automation.service import AutomationService

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """在 Agent 服务生命周期内运行自动化任务。"""

    def __init__(
        self,
        *,
        automation_service: AutomationService,
        agent: Any,
        session_service: Any,
        poll_seconds: float | None = None,
        max_workers: int | None = None,
        lease_seconds: int | None = None,
    ) -> None:
        """初始化调度器,不在构造阶段启动线程。"""

        self.automation_service = automation_service
        self.agent = agent
        self.session_service = session_service
        limits = getattr(getattr(agent, "config", None), "limits", DEFAULT_BUSINESS_LIMITS)
        self.limits = limits
        self.poll_seconds = max(limits.scheduler_min_poll_seconds, limits.automation_poll_seconds if poll_seconds is None else poll_seconds)
        self.max_workers = max(limits.scheduler_min_worker_count, limits.automation_max_workers if max_workers is None else max_workers)
        self.lease_seconds = max(limits.automation_min_lease_seconds, limits.automation_lease_seconds if lease_seconds is None else lease_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="automation-run")
        self._futures: set[Any] = set()

    def start(self) -> None:
        """启动单一调度线程。"""

        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="automation-scheduler", daemon=True)
        self._thread.start()
        logger.info("自动化任务调度器已启动 | poll_seconds=%s", self.poll_seconds)

    def shutdown(self) -> None:
        """停止调度线程并等待已提交任务结束。"""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(
                timeout=max(
                    self.limits.automation_shutdown_timeout_seconds,
                    self.poll_seconds + self.limits.automation_shutdown_grace_seconds,
                )
            )
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("自动化任务调度器已停止")

    def _run_loop(self) -> None:
        """扫描到期任务并提交后台执行。"""

        while not self._stop_event.is_set():
            try:
                self._futures = {future for future in self._futures if not future.done()}
                available_workers = self.max_workers - len(self._futures)
                claims = self.automation_service.claim_due_tasks(
                    lease_seconds=self.lease_seconds,
                    limit=available_workers,
                )
                for claim in claims:
                    self._futures.add(self._executor.submit(self._execute_claim, claim))
            except Exception:
                logger.exception("自动化任务扫描失败")
            self._stop_event.wait(self.poll_seconds)

    def _execute_claim(self, claim: dict[str, Any]) -> None:
        """执行一项已抢占任务并写回运行结果。"""

        task = claim["task"]
        run = claim["run"]
        automation_id = str(task["id"])
        run_id = str(run["id"])
        lease_id = str(claim["leaseId"])
        try:
            if not self.automation_service.is_claim_executable(
                automation_id=automation_id,
                run_id=run_id,
                lease_id=lease_id,
            ):
                logger.info("自动化任务已在排队期间删除或停用 | automation=%s run=%s", automation_id, run_id)
                return
            session = self.session_service.create_session(
                SessionCreate(
                    user_id=str(task["userId"]),
                    session_name=f"自动化：{task['id']}",
                )
            )
            if not self.automation_service.renew_claim(
                automation_id=automation_id,
                run_id=run_id,
                lease_id=lease_id,
                lease_seconds=self.lease_seconds,
            ):
                cancel_session = getattr(self.agent, "cancel_session", None)
                if callable(cancel_session):
                    cancel_session(session.session_id)
                logger.info("自动化任务在会话创建后删除或停用 | automation=%s run=%s", automation_id, run_id)
                return
            heartbeat_stop = threading.Event()
            heartbeat = threading.Thread(
                target=self._renew_while_running,
                args=(automation_id, run_id, lease_id, session.session_id, heartbeat_stop),
                name=f"automation-heartbeat-{run_id}",
                daemon=True,
            )
            heartbeat.start()
            try:
                result = self.agent.run_session_prompt(
                    prompt=(
                        "这是一个由定时自动化任务触发的独立执行。请完成以下任务，并在最后简要报告结果：\n"
                        + str(task["prompt"])
                    ),
                    user_id=str(task["userId"]),
                    session_id=session.session_id,
                    agent_mode="auto",
                    agent_access_mode=str(task.get("accessMode") or "sandbox"),
                )
            finally:
                heartbeat_stop.set()
                heartbeat.join(timeout=self.limits.automation_shutdown_timeout_seconds)
            persisted = self.automation_service.finish_run(
                automation_id=automation_id,
                run_id=run_id,
                status="success",
                output=str(result.get("final_output") or ""),
                lease_id=lease_id,
            )
            if persisted:
                logger.info("自动化任务执行成功 | automation=%s run=%s", automation_id, run_id)
            else:
                logger.info("自动化任务结果已因删除、停用或租约失效而丢弃 | automation=%s run=%s", automation_id, run_id)
        except Exception as exc:
            logger.exception("自动化任务执行失败 | automation=%s run=%s", automation_id, run_id)
            self.automation_service.finish_run(
                automation_id=automation_id,
                run_id=run_id,
                status="failed",
                error=str(exc),
                lease_id=lease_id,
            )

    def _renew_while_running(
        self,
        automation_id: str,
        run_id: str,
        lease_id: str,
        session_id: str,
        stop_event: threading.Event,
    ) -> None:
        """执行期间周期续租；删除、停用或失去租约时协作取消 Agent。"""

        # 同时承担删除/停用后的协作取消探测，最多 10 秒反馈一次。
        interval = max(
            self.limits.automation_heartbeat_min_seconds,
            min(self.limits.automation_heartbeat_max_seconds, self.lease_seconds / 3),
        )
        while not stop_event.wait(interval):
            if self.automation_service.renew_claim(
                automation_id=automation_id,
                run_id=run_id,
                lease_id=lease_id,
                lease_seconds=self.lease_seconds,
            ):
                continue
            cancel_session = getattr(self.agent, "cancel_session", None)
            if callable(cancel_session):
                cancel_session(session_id)
            logger.info("自动化任务失去执行租约，已请求中断 | automation=%s run=%s", automation_id, run_id)
            return
