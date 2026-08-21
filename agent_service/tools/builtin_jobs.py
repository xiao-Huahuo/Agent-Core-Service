"""Agent 内置长任务的进程内状态管理。

使用说明:
知识灌库与图谱抽取工具通过 ``tool_job_manager`` 启动后台线程，并使用统一的
job_id 查询、取消和失败重试协议。任务状态属于可丢弃的运行时观测数据，服务重启后
清空符合预期；知识库、图谱等业务结果仍由正式服务和数据库持久化。
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from agent_service.core.agent_config import AgentConfig


class ToolJobCancelled(RuntimeError):
    """由任务进度回调抛出，用于在安全检查点终止后台工作。"""


@dataclass(slots=True)
class ToolJob:
    """保存一个用户级 Agent 后台任务的可观测状态。"""

    job_id: str
    user_id: str
    kind: str
    status: str = "queued"
    total: int = 0
    current: int = 0
    message: str = "已排队"
    result: dict[str, Any] | None = None
    failed_items: list[dict[str, str]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """返回不暴露线程对象的 JSON 可序列化快照。"""

        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "kind": self.kind,
            "status": self.status,
            "total": self.total,
            "current": self.current,
            "message": self.message,
            "result": self.result,
            "failed_items": list(self.failed_items),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


JobRunner = Callable[[Callable[..., None], threading.Event], dict[str, Any]]


class ToolJobManager:
    """线程安全地启动和查询 Agent 内置长任务。"""

    def __init__(self, *, config: AgentConfig | None = None) -> None:
        """初始化任务表及互斥锁。"""

        self._lock = threading.RLock()
        self.config = config or AgentConfig()
        self._jobs: dict[str, ToolJob] = {}

    def start(self, *, user_id: str, kind: str, runner: JobRunner) -> dict[str, Any]:
        """启动后台任务并立即返回包含 job_id 的初始快照。"""

        job = ToolJob(job_id=f"job_{uuid.uuid4().hex}", user_id=user_id, kind=kind)
        with self._lock:
            self._jobs[job.job_id] = job
            self._trim_completed_jobs()

        def update(**changes: Any) -> None:
            """由 runner 在安全检查点更新进度。"""

            with self._lock:
                for key, value in changes.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                job.updated_at = datetime.now(timezone.utc).isoformat()
            if job.cancel_event.is_set():
                raise ToolJobCancelled("任务已取消")

        def worker() -> None:
            """执行任务并归一化完成、取消和失败状态。"""

            try:
                update(status="running", message="正在执行")
                result = runner(update, job.cancel_event)
                update(status="completed", message="执行完成", result=result)
            except ToolJobCancelled:
                with self._lock:
                    job.status = "cancelled"
                    job.message = "任务已取消"
                    job.updated_at = datetime.now(timezone.utc).isoformat()
            except Exception as exc:  # noqa: BLE001 - task failures must remain observable to the Agent.
                with self._lock:
                    job.status = "failed"
                    job.message = str(exc)
                    job.updated_at = datetime.now(timezone.utc).isoformat()

        threading.Thread(target=worker, name=f"agent-tool-{kind}", daemon=True).start()
        return job.to_dict()

    def get(self, *, user_id: str, job_id: str) -> dict[str, Any]:
        """读取当前用户拥有的任务，不允许跨用户查看。"""

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.user_id != user_id:
                raise ValueError("knowledge job not found")
            return job.to_dict()

    def cancel(self, *, user_id: str, job_id: str) -> dict[str, Any]:
        """请求任务在下一个安全检查点取消。"""

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.user_id != user_id:
                raise ValueError("knowledge job not found")
            if job.status in {"completed", "failed", "cancelled"}:
                return job.to_dict()
            job.cancel_event.set()
            job.status = "cancelling"
            job.message = "正在取消"
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job.to_dict()

    def _trim_completed_jobs(self) -> None:
        """保留最近 200 个任务，避免长驻进程无限积累瞬时状态。"""

        max_entries = self.config.limits.tool_job_registry_max_entries
        if len(self._jobs) <= max_entries:
            return
        removable = [
            job
            for job in self._jobs.values()
            if job.status in {"completed", "failed", "cancelled"}
        ]
        removable.sort(key=lambda job: job.updated_at)
        for job in removable[: len(self._jobs) - max_entries]:
            self._jobs.pop(job.job_id, None)


tool_job_manager = ToolJobManager()
