"""会话复合状态归一化回归测试。

功能说明：
保证子 Agent 等辅助快照保持顶层现代状态结构，并兼容读取旧版本误嵌套到 plan 的列表。
"""

import json
from types import SimpleNamespace

from agent_service.agent_core.runtime.session_runtime import SessionRuntimeMixin
from agent_service.agent_core.runtime.child_agent_runtime import ChildAgentRuntimeMixin
from agent_service.services.task_list.service import normalize_session_state


def test_child_agent_snapshot_is_not_misclassified_as_legacy_plan() -> None:
    """只有 child_agents 的现代状态不得被包进 plan。"""

    state = {"child_agents": [{"run_id": "child-1"}]}

    assert normalize_session_state(state) == state


def test_child_agent_snapshot_recovers_from_legacy_plan_nesting() -> None:
    """已被旧逻辑放进 plan.child_agents 的快照仍应可冷恢复。"""

    runtime = SimpleNamespace(
        session_service=SimpleNamespace(
            get_session_state=lambda _session_id: json.dumps({
                "plan": {"child_agents": [{"run_id": "child-1"}]}
            })
        )
    )

    assert SessionRuntimeMixin._load_session_state_list(runtime, "session-1", "child_agents") == [
        {"run_id": "child-1"}
    ]


def test_child_agent_snapshot_recovers_from_persisted_tool_and_event_messages() -> None:
    """state_json 已丢失时应合并 spawn 工具结果与最新生命周期状态。"""

    messages = [
        SimpleNamespace(
            role="tool",
            content=json.dumps({
                "run_id": "child-1",
                "provider": "dsh",
                "workspace_root": "D:/workspace",
                "status": "running",
            }),
            metadata_json={},
        ),
        SimpleNamespace(
            role="assistant",
            content="failed",
            metadata_json={
                "child_agent_event": {
                    "child": {"run_id": "child-1", "provider": "dsh", "status": "failed"}
                }
            },
        ),
    ]
    runtime = SimpleNamespace(
        session_service=SimpleNamespace(get_session=lambda _session_id: SimpleNamespace(user_id="u1")),
        _get_message_service=lambda: SimpleNamespace(
            list_session_messages=lambda **_kwargs: messages
        ),
    )

    children = ChildAgentRuntimeMixin._load_child_agents_from_messages(runtime, "session-1")

    assert children == [{
        "run_id": "child-1",
        "provider": "dsh",
        "workspace_root": "D:/workspace",
        "status": "failed",
    }]
