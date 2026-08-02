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

from agent_service.schemas.session import SessionCreate
from agent_service.services.automation_service import AutomationService

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """在 Agent 服务生命周期内运行自动化任务。"""

    def __init__(
        self,
        *,
        automation_service: AutomationService,
        agent: Any,
        session_service: Any,
        poll_seconds: float = 15.0,
        max_workers: int = 2,
    ) -> None:
        """初始化调度器,不在构造阶段启动线程。"""

        self.automation_service = automation_service
        self.agent = agent
        self.session_service = session_service
        self.poll_seconds = max(1.0, poll_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="automation-run")

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
            self._thread.join(timeout=max(5.0, self.poll_seconds + 1.0))
        self._executor.shutdown(wait=True, cancel_futures=False)
        logger.info("自动化任务调度器已停止")

    def _run_loop(self) -> None:
        """扫描到期任务并提交后台执行。"""

        while not self._stop_event.is_set():
            try:
                claims = self.automation_service.claim_due_tasks()
                for claim in claims:
                    self._executor.submit(self._execute_claim, claim)
            except Exception:
                logger.exception("自动化任务扫描失败")
            self._stop_event.wait(self.poll_seconds)

    def _execute_claim(self, claim: dict[str, Any]) -> None:
        """执行一项已抢占任务并写回运行结果。"""

        task = claim["task"]
        run = claim["run"]
        automation_id = str(task["id"])
        run_id = str(run["id"])
        try:
            session = self.session_service.create_session(
                SessionCreate(
                    user_id=str(task["userId"]),
                    session_name=f"自动化：{task['id']}",
                )
            )
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
            self.automation_service.finish_run(
                automation_id=automation_id,
                run_id=run_id,
                status="success",
                output=str(result.get("final_output") or ""),
            )
            logger.info("自动化任务执行成功 | automation=%s run=%s", automation_id, run_id)
        except Exception as exc:
            logger.exception("自动化任务执行失败 | automation=%s run=%s", automation_id, run_id)
            self.automation_service.finish_run(
                automation_id=automation_id,
                run_id=run_id,
                status="failed",
                error=str(exc),
            )
