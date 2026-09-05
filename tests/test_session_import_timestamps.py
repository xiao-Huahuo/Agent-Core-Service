"""会话导入消息时间保真回归测试。

用途：确保导出的 created_at 经正式导入写入路径后仍作为消息历史时间保存，
供前端在重新加载会话时重建 30 分钟时间分隔。
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, select

from agent_service.api.rest.sessions import _import_messages
from agent_service.models.message import MessageRecord
from tests.db_test_utils import create_test_engine


def test_import_messages_preserves_created_at() -> None:
    """导入消息必须保留原始 ISO 时间，而不是替换为导入发生时间。"""

    engine = create_test_engine("sqlite://")
    message_service = SimpleNamespace(generate_message_id=lambda: "message-imported")
    with Session(engine) as db_session:
        imported_count = _import_messages(
            db_session=db_session,
            message_service=message_service,
            messages=[{
                "role": "user",
                "content": "历史问题",
                "created_at": "2026-08-30T08:01:00+00:00",
            }],
            session_id="session-imported",
            user_id="user-imported",
            fallback_created_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        db_session.commit()
        message = db_session.exec(select(MessageRecord)).one()

    assert imported_count == 1
    assert message.created_at == datetime(2026, 8, 30, 8, 1)
