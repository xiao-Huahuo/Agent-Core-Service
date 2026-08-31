"""通过固定 Python SDK 驱动受管 DSH Windows Runtime。

一个 ``ChildAgentExecutionContext`` 对应一个稳定 DSH Session和热 Runtime；SDK
负责 JSON-RPC，PackageManager负责二进制，MW只在此处映射配置、权限与 Web入口。
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel

from agent_service.core.agent_config import AgentConfig
from agent_service.services.child_agent.types import ChildAgentExecutionContext, ChildAgentStopped
from agent_service.services.dsh_runtime import DshRuntimePackageManager
from agent_service.services.settings.service import SettingsService
from agent_service.vendor.deepseek_harness import DeepSeekHarness, DeepSeekHarnessConfig

logger = logging.getLogger(__name__)


class _SessionOpenResponse(BaseModel):
    """MW固定 Runtime 的 ``session/open`` 成功响应。"""

    sessionId: str
    disposition: str
    durableSeq: int


class _SessionFlushResponse(BaseModel):
    """MW固定 Runtime 的 ``session/flush`` 成功响应。"""

    sessionId: str
    durableSeq: int


@dataclass(slots=True)
class _RuntimeHandle:
    """保存一个 Child Agent 热 Runtime及其只读 Web访问材料。"""

    harness: DeepSeekHarness
    session_id: str
    session_root: Path
    web_url_file: Path
    web_token: str
    access_mode: str
    user_id: str
    web_base_url: str = ""
    running: bool = False
    last_activity: float = 0.0


class DshChildAgentExecutor:
    """复用热 DSH Runtime执行代码 Turn并提供对应只读 Web URL。"""

    def __init__(
        self,
        *,
        config: AgentConfig,
        settings_service: SettingsService,
        runtime_manager: DshRuntimePackageManager,
    ) -> None:
        """绑定 MW配置、用户模型设置与 Runtime资源管理器。"""

        self.config = config
        self.settings_service = settings_service
        self.runtime_manager = runtime_manager
        self.conversations_root = (Path(config.storage.base_data_dir) / "dsh" / "conversations").resolve()
        self.conversations_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._handles: dict[str, _RuntimeHandle] = {}

    def __call__(self, context: ChildAgentExecutionContext) -> str:
        """在当前 Child Agent的稳定 DSH Conversation中执行一个 Turn。"""

        context.raise_if_stopped()
        handle = self._get_or_start(context)
        with self._lock:
            handle.running = True
            handle.last_activity = time.monotonic()
        done = threading.Event()
        monitor = threading.Thread(
            target=self._monitor_cancellation,
            args=(context, done),
            name=f"dsh-cancel-{context.run_id[-8:]}",
            daemon=True,
        )
        monitor.start()
        try:
            result = handle.harness.start_session(handle.session_id).run(context.goal)
            handle.harness.client.request(
                "session/flush",
                {"sessionId": handle.session_id},
                response_model=_SessionFlushResponse,
            )
            context.raise_if_stopped()
            return result.final_response
        except Exception as exc:
            if context.cancellation.is_set():
                raise ChildAgentStopped("DSH 子 Agent已停止") from exc
            raise
        finally:
            done.set()
            monitor.join(timeout=1)
            self._refresh_web_url(handle)
            with self._lock:
                handle.running = False
                handle.last_activity = time.monotonic()

    @staticmethod
    def session_id_for_run(run_id: str) -> str:
        """把稳定 MW Child Agent ID映射为规范 UUID格式的 DSH Session ID。"""

        return str(uuid5(NAMESPACE_URL, f"metaweave:dsh:{run_id}"))

    def web_url(self, *, run_id: str, user_id: str) -> str:
        """返回指定用户所属热 DSH Conversation的受限 Web URL。"""

        with self._lock:
            handle = self._handles.get(run_id)
            if handle is None:
                raise KeyError("DSH 子 Agent Runtime当前不在线")
            if handle.user_id != user_id:
                raise PermissionError("不能查看其他用户的 DSH 子 Agent")
            handle.last_activity = time.monotonic()
            self._refresh_web_url(handle)
            if not handle.web_base_url:
                raise RuntimeError("DSH Runtime尚未公布 Web地址")
            query = urlencode({
                "mw_token": handle.web_token,
                "session": handle.session_id,
                "readonly": "1",
            })
            return f"{handle.web_base_url.rstrip('/')}#{query}"

    def ensure_web(self, *, child: dict[str, Any], user_id: str) -> str:
        """冷恢复已持久化的 DSH Child Agent并返回只读 Web URL。"""

        if child.get("provider") != "dsh":
            raise ValueError("该子 Agent不是 DSH 类型")
        run_id = str(child.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("DSH 子 Agent缺少 run_id")
        with self._lock:
            online = run_id in self._handles
        if not online:
            context = ChildAgentExecutionContext(
                run_id=run_id,
                parent_run_id=str(child.get("parent_run_id") or ""),
                goal=str(child.get("goal") or "查看历史"),
                user_id=user_id,
                session_id=str(child.get("session_id") or ""),
                agent_mode="react",
                allowed_tools=frozenset(str(item) for item in child.get("allowed_tools") or []),
                access_mode=str(child.get("access_mode") or "sandbox"),
                input_refs=(),
                output_contract={},
                cancellation=threading.Event(),
                category=str(child.get("category") or "dsh"),
                name=str(child.get("name") or ""),
                provider="dsh",
                workspace_root=str(child.get("workspace_root") or ""),
            )
            self._get_or_start(context)
        deadline = time.monotonic() + 5
        while True:
            try:
                return self.web_url(run_id=run_id, user_id=user_id)
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)

    def stop(self, run_id: str) -> None:
        """关闭一个热 Runtime并释放其受管资源租约。"""

        with self._lock:
            handle = self._handles.pop(run_id, None)
        if handle is None:
            return
        try:
            handle.harness.close()
        finally:
            self.runtime_manager.release_runtime(run_id)

    def shutdown(self) -> None:
        """关闭全部热 Runtime，供 FastAPI lifespan统一回收。"""

        with self._lock:
            run_ids = list(self._handles)
        for run_id in run_ids:
            try:
                self.stop(run_id)
            except Exception:
                logger.exception("关闭 DSH Runtime失败 | run_id=%s", run_id)

    def _get_or_start(self, context: ChildAgentExecutionContext) -> _RuntimeHandle:
        """复用兼容热 Runtime，或从受管 Windows产物启动一个新 Runtime。"""

        with self._lock:
            self._reap_idle_locked()
            existing = self._handles.get(context.run_id)
            if existing is not None:
                if existing.access_mode != context.access_mode:
                    self.stop(context.run_id)
                else:
                    return existing

            if len(self._handles) >= max(self.config.dsh.max_live_runtimes, 1):
                idle = [item for item in self._handles.items() if not item[1].running]
                if not idle:
                    raise RuntimeError("DSH Runtime容量已满，当前 Runtime均在运行")
                oldest = min(idle, key=lambda item: item[1].last_activity)[0]
                self.stop(oldest)

            self.runtime_manager.acquire_runtime(context.run_id)
            harness: DeepSeekHarness | None = None
            try:
                launcher = self.runtime_manager.resolve_launcher()
                runtime_args = self.runtime_manager.resolve_runtime_launch_args(context.access_mode)
                model = self._resolve_model(context.user_id)
                workspace = self._resolve_workspace(context.workspace_root)
                conversation_root = (self.conversations_root / context.run_id).resolve()
                if self.conversations_root not in conversation_root.parents:
                    raise ValueError("DSH Conversation目录越界")
                session_root = conversation_root / "sessions"
                session_root.mkdir(parents=True, exist_ok=True)
                dsh_home = conversation_root / "home"
                dsh_home.mkdir(parents=True, exist_ok=True)
                web_url_file = conversation_root / "web-url.txt"
                web_url_file.unlink(missing_ok=True)
                web_token = secrets.token_urlsafe(32)
                session_id = self.session_id_for_run(context.run_id)
                harness = DeepSeekHarness(DeepSeekHarnessConfig(
                    provider="deepseek-official",
                    model=model["model_name"],
                    cwd=str(workspace),
                    runtime_cwd=str(conversation_root),
                    session_root=str(session_root),
                    launch_args_override=(str(launcher), *runtime_args),
                    base_url=model["base_url"],
                    api_key=model["api_key"],
                    env={
                        "DSH_MW_MANAGED": "1",
                        "DSH_HOME": str(dsh_home),
                        "DSH_MW_WEB_READ_ONLY": "1",
                        "DSH_MW_WEB_TOKEN": web_token,
                        "DSH_MW_SESSION_ID": session_id,
                        "DSH_MW_WEB_URL_FILE": str(web_url_file),
                        "DSH_PERMISSION_MODE": {
                            "readonly": "read-only",
                            "sandbox": "workspace-write",
                            "full_access": "danger-full-access",
                        }[context.access_mode],
                    },
                ))
                harness.start()
                server_info = harness.initialize_response.serverInfo if harness.initialize_response else None
                capabilities = set(server_info.capabilities if server_info else [])
                required = {"mw-session-open-v1", "mw-session-flush-v1"}
                if server_info is None or server_info.name != "deepseek-harness-sdk-runtime" or not required <= capabilities:
                    raise RuntimeError("DSH Runtime不兼容 MW session/open与session/flush协议")
                opened = harness.client.request(
                    "session/open",
                    {"sessionId": session_id},
                    response_model=_SessionOpenResponse,
                )
                if opened.disposition not in {"created", "resumed", "already-open"}:
                    raise RuntimeError(f"DSH session/open返回未知状态: {opened.disposition}")
                handle = _RuntimeHandle(
                    harness=harness,
                    session_id=session_id,
                    session_root=session_root,
                    web_url_file=web_url_file,
                    web_token=web_token,
                    access_mode=context.access_mode,
                    user_id=context.user_id,
                    last_activity=time.monotonic(),
                )
                self._refresh_web_url(handle)
                self._handles[context.run_id] = handle
                return handle
            except Exception:
                if harness is not None:
                    harness.close()
                self.runtime_manager.release_runtime(context.run_id)
                raise

    def _reap_idle_locked(self) -> None:
        """在调度检查点回收超过服务级空闲上限的热 Runtime。"""

        cutoff = time.monotonic() - max(self.config.dsh.idle_timeout_seconds, 1)
        expired = [
            run_id for run_id, handle in self._handles.items()
            if not handle.running and handle.last_activity < cutoff
        ]
        for run_id in expired:
            self.stop(run_id)

    def _resolve_model(self, user_id: str) -> dict[str, str]:
        """读取用户覆盖优先的远程大模型配置并拒绝本地模型回退。"""

        configured = self.settings_service.get_llm_config(user_id=user_id)
        model_name = str(configured.get("effective_model_name") or "").strip()
        base_url = str(configured.get("effective_base_url") or "").strip()
        api_key = str(configured.get("effective_api_key") or "").strip()
        if configured.get("effective_model_source") != "remote" or not model_name or not base_url:
            raise ValueError("DSH 子 Agent需要已配置的远程 DeepSeek模型、Base URL和凭据")
        return {"model_name": model_name, "base_url": base_url, "api_key": api_key}

    def _resolve_workspace(self, requested: str) -> Path:
        """解析父 Agent明确提供的工作区；未提供时使用 MW项目根目录。"""

        workspace = Path(requested or self.config.storage.project_root).expanduser().resolve()
        if not workspace.is_dir():
            raise ValueError("DSH 子 Agent工作区不存在或不是目录")
        return workspace

    def _monitor_cancellation(
        self,
        context: ChildAgentExecutionContext,
        done: threading.Event,
    ) -> None:
        """在 SDK阻塞等待 Turn时响应 ChildAgentManager停止信号。"""

        while not done.wait(0.1):
            if not context.cancellation.is_set():
                continue
            self.stop(context.run_id)
            return

    @staticmethod
    def _refresh_web_url(handle: _RuntimeHandle) -> None:
        """从固定 URL文件或 SDK stderr发现同进程 loopback Web地址。"""

        candidates: list[str] = []
        if handle.web_url_file.is_file():
            candidates.append(handle.web_url_file.read_text(encoding="utf-8").strip())
        candidates.extend(
            line.split("dsh web:", 1)[1].strip()
            for line in handle.harness.client.stderr_lines
            if "dsh web:" in line
        )
        for candidate in reversed(candidates):
            parsed = urlparse(candidate)
            if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
                handle.web_base_url = candidate
                return
