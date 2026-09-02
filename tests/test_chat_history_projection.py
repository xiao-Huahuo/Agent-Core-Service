"""聊天历史语义投影回归测试。

用途：验证原始 Agent 事件日志仍可完整保存，而聊天历史加载不会重复暴露同一
用户 Turn 内的中间 agent 回复和病态空等待工具结果。
"""

from sqlmodel import SQLModel, create_engine

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.message import MessageCreate
from agent_service.services.message.service import MessageService


def test_chat_history_folds_agent_iterations_and_empty_child_waits() -> None:
    """一个 Turn 中重复的 agent/wait 事件只投影为一个等待行和最终回复。"""

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=AgentConfig(), engine=engine, create_tables=False)
    session_id = "history-loop"
    service.create_message(MessageCreate(session_id=session_id, user_id="u1", role="user", content="继续等待"))
    for index in range(3):
        call_id = f"wait-{index}"
        service.create_message(MessageCreate(
            session_id=session_id,
            user_id="u1",
            role="assistant",
            content="当前已收到 3/4 子 Agent 结果，继续等待最后一个。",
            tool_calls_json=[{"id": call_id, "name": "wait_for_child_agents", "args": {}}],
            metadata_json={"node": "agent", "source": "agent_graph"},
        ))
        service.create_message(MessageCreate(
            session_id=session_id,
            user_id="u1",
            role="tool",
            content='{"result": null, "children": []}',
            tool_call_id=call_id,
            metadata_json={
                "node": "action",
                "source": "agent_graph",
                "trace": [{"tool_call_id": call_id, "tool_name": "wait_for_child_agents"}],
            },
        ))

    raw = service.list_session_messages(user_id="u1", session_id=session_id, limit=None)
    projected = service.list_chat_messages(user_id="u1", session_id=session_id, limit=None)

    assert len(raw) == 7
    assert [message.role for message in projected] == ["user", "tool", "assistant"]
    assert projected[-1].content == "当前已收到 3/4 子 Agent 结果，继续等待最后一个。"


def test_chat_history_drops_duplicate_automatic_wakeup_turn() -> None:
    """同一子 Agent 终态被旧版多窗口重复唤醒时，历史只恢复第一轮。"""

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = MessageService(config=AgentConfig(), engine=engine, create_tables=False)
    metadata = {
        "wakeup": True,
        "child_agent_event": {
            "event_name": "child_agent.completed",
            "child": {"run_id": "child-1", "status": "completed"},
        },
    }
    for index in range(2):
        service.create_message(MessageCreate(
            session_id="duplicate-wakeup",
            user_id="u1",
            role="user",
            content="子 Agent 完成提醒",
            metadata_json=metadata,
        ))
        service.create_message(MessageCreate(
            session_id="duplicate-wakeup",
            user_id="u1",
            role="assistant",
            content=f"第 {index + 1} 次处理",
            metadata_json={"node": "agent", "source": "agent_graph"},
        ))
    service.create_message(MessageCreate(
        session_id="duplicate-wakeup",
        user_id="u1",
        role="user",
        content="另一个子 Agent 完成提醒",
        metadata_json={
            **metadata,
            "child_agent_event": {
                "event_name": "child_agent.completed",
                "child": {"run_id": "child-2", "status": "completed"},
            },
        },
    ))
    service.create_message(MessageCreate(
        session_id="duplicate-wakeup",
        user_id="u1",
        role="assistant",
        content="第 1 次处理",
        metadata_json={"node": "agent", "source": "agent_graph"},
    ))

    projected = service.list_chat_messages(user_id="u1", session_id="duplicate-wakeup", limit=None)

    assert [message.content for message in projected] == [
        "子 Agent 完成提醒",
        "第 1 次处理",
        "另一个子 Agent 完成提醒",
    ]
