"""
Agent 思考文本(reasoning_content)持久化回归测试。

功能说明:
思考条(Think)的数据必须满足"落库 → 随对话加载 → 随导入导出迁移"的闭环。
本文件定向验证三个关键点:
1. 主 Agent 消息落库时 reasoning_content 写入 metadata_json(字符串形态)。
2. 流式合并后 reasoning_content 可能累积为片段列表,落库前必须拼接为字符串。
3. 会话导入(_import_messages)必须原样保留 metadata.reasoning_content,
   导出的 metadata 由前端 formatMessages 原样携带,导入端不再二次丢弃。

使用说明:
在项目根目录执行 `python -m pytest tests/test_agent_thinking_persistence.py`。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from agent_service.agent_core.agent_core import AgentCore
from agent_service.api.rest.sessions import _import_messages


class FakeDBSession:
    """只记录 add 调用的假数据库会话,避免真实建表。"""

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, record: object) -> None:
        self.added.append(record)


def test_message_to_create_persists_reasoning_content() -> None:
    """主 Agent 消息落库时,思考全文必须进入 metadata_json.reasoning_content。"""

    message = AIMessage(content="回答", additional_kwargs={"reasoning_content": "思考全文"})
    created = AgentCore._message_to_create(
        message=message,
        user_id="user-1",
        session_id="session-1",
        node_name="agent",
    )

    assert created.metadata_json["reasoning_content"] == "思考全文"


def test_message_to_create_joins_reasoning_fragments() -> None:
    """流式合并后 reasoning_content 可能是片段列表,落库前必须拼接为字符串。"""

    message = AIMessage(content="回答", additional_kwargs={"reasoning_content": ["让", "我", "想想"]})
    created = AgentCore._message_to_create(
        message=message,
        user_id="user-1",
        session_id="session-1",
        node_name="agent",
    )

    assert created.metadata_json["reasoning_content"] == "让我想想"


def test_import_messages_keeps_reasoning_content() -> None:
    """导入的会话消息必须原样保留 metadata.reasoning_content,不能二次丢弃。"""

    db = FakeDBSession()
    count = _import_messages(
        db_session=db,  # type: ignore[arg-type]
        message_service=MagicMock(),
        messages=[
            {
                "role": "assistant",
                "content": "回答",
                "created_at": "2026-08-30T08:00:00Z",
                "metadata": {"node": "agent", "reasoning_content": "导入的思考全文"},
            }
        ],
        session_id="session-1",
        user_id="user-1",
        fallback_created_at=datetime.now(timezone.utc),
    )

    assert count == 1
    record = db.added[0]
    assert record.metadata_json["reasoning_content"] == "导入的思考全文"
