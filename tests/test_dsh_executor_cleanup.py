"""DSH 子 Agent Runtime 异常回收测试。

功能说明：
验证 Runtime 已启动但 Turn 执行失败时，执行器关闭句柄并释放 PackageManager 租约，
避免后续修复、卸载和新子 Agent 永久被“正在使用”阻塞。
"""

from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from agent_service.services.dsh_adapter.executor import DshChildAgentExecutor, _RuntimeHandle


def test_failed_turn_releases_runtime_lease(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """DSH Turn 抛错后应移除热句柄、关闭进程并释放同一 run_id 租约。"""

    released: list[str] = []
    harness = SimpleNamespace(
        close=lambda: None,
        start_session=lambda _session_id: SimpleNamespace(
            run=lambda _goal: (_ for _ in ()).throw(RuntimeError("runtime failed"))
        ),
        client=SimpleNamespace(stderr_lines=[]),
    )
    handle = _RuntimeHandle(
        harness=harness,
        session_id="session-1",
        session_root=tmp_path,
        web_url_file=tmp_path / "web-url.txt",
        web_token="token",
        access_mode="sandbox",
        user_id="u1",
    )
    executor = DshChildAgentExecutor.__new__(DshChildAgentExecutor)
    executor._lock = threading.RLock()
    executor._handles = {"run-1": handle}
    executor.runtime_manager = SimpleNamespace(release_runtime=released.append)
    monkeypatch.setattr(executor, "_get_or_start", lambda _context: handle)
    monkeypatch.setattr(executor, "_refresh_web_url", lambda _handle: None)
    context = SimpleNamespace(
        run_id="run-1",
        goal="fail",
        cancellation=threading.Event(),
        raise_if_stopped=lambda: None,
    )

    with pytest.raises(RuntimeError, match="runtime failed"):
        executor(context)

    assert "run-1" not in executor._handles
    assert released == ["run-1"]
