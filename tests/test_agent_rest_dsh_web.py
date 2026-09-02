"""DSH 子 Agent Web 入口的 REST 并发回归测试。

用途：验证 DSH Runtime 尚在启动并等待内部锁时，Web 入口不会阻塞 FastAPI
事件循环，确保同进程的子 Agent 状态轮询仍可继续响应。
"""

from __future__ import annotations

import asyncio
from threading import Event
from types import SimpleNamespace

from agent_service.api.rest import agent as agent_rest


def test_dsh_web_wait_does_not_block_event_loop(monkeypatch) -> None:
    """等待 DSH Web 地址时，事件循环中的其他请求必须仍有执行机会。"""

    release = Event()

    class BlockingDshExecutor:
        """模拟 DSH 启动线程尚未发布 Web 地址的执行器。"""

        def ensure_web(self, *, child, user_id: str) -> str:
            """等待测试线程放行后返回受管 DSH 地址。"""

            assert child["run_id"] == "child-dsh"
            assert user_id == "user-1"
            assert release.wait(timeout=1)
            return "http://127.0.0.1:3080/#readonly=1"

    monkeypatch.setattr(
        agent_rest,
        "_require_session_service",
        lambda: SimpleNamespace(get_session=lambda session_id: SimpleNamespace(user_id="user-1")),
    )
    monkeypatch.setattr(
        agent_rest,
        "_require_agent",
        lambda: SimpleNamespace(
            list_child_agents_for_session=lambda session_id: [
                {"run_id": "child-dsh", "provider": "dsh"},
            ],
        ),
    )
    monkeypatch.setattr(agent_rest, "_require_dsh_executor", BlockingDshExecutor)

    async def exercise() -> None:
        """并发等待路由与事件循环探针，并在探针完成后释放执行器。"""

        route_task = asyncio.create_task(
            agent_rest.get_child_agent_dsh_web(
                run_id="child-dsh",
                user_id="user-1",
                session_id="session-1",
            ),
        )
        probe = asyncio.create_task(asyncio.sleep(0.01))
        await asyncio.wait_for(probe, timeout=0.1)
        release.set()
        assert await route_task == {
            "run_id": "child-dsh",
            "url": "http://127.0.0.1:3080/#readonly=1",
        }

    try:
        asyncio.run(exercise())
    finally:
        release.set()

