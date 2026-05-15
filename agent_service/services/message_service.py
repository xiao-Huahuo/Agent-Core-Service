"""
Message 会话消息业务服务。

功能说明:
本文件实现会话消息的基础读写能力。Message 是 Session 下的原始事件日志,
用于保存用户输入、模型回复、工具调用和工具结果。ContextBuilder 后续通过
本服务读取同一 session 下的历史消息来构建短期上下文。

使用说明:
调用方需要显式传入 `AgentConfig`:

config = AgentConfig.load_config()
service = MessageService(config=config)
message = service.create_message(MessageCreate(...))
recent_messages = service.list_recent_messages(user_id="u1", session_id="s1", limit=20)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.message import MessageRecord
from agent_service.schemas.message import MessageCreate, MessageOut, MessageUpdate


class MessageService:
    """
    会话消息业务服务。

    config: 全局配置对象,用于读取 PostgreSQL 连接地址。
    engine: 可选 SQLAlchemy Engine,主要用于测试或外部依赖注入。
    create_tables: 是否初始化数据库表结构。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        engine: Engine | None = None,
        create_tables: bool = True,
    ) -> None:
        """初始化数据库引擎,并按需创建消息相关表。"""

        self.config = config
        self.engine = engine or create_engine(config.storage.relational_dsn, pool_pre_ping=True)
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def create_message(self, message_create: MessageCreate) -> MessageOut:
        """
        创建消息并写入数据库。

        message_create: 创建消息 DTO。
        """

        record = MessageRecord(
            message_id=self.generate_message_id(),
            session_id=message_create.session_id,
            user_id=message_create.user_id,
            role=message_create.role,
            content=message_create.content,
            tool_call_id=message_create.tool_call_id,
            tool_calls_json=message_create.tool_calls_json,
            metadata_json=message_create.metadata_json,
            created_at=self._utc_now(),
        )
        with Session(self.engine) as db_session:
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return MessageOut.from_record(record)

    def update_message(self, message_id: str, message_update: MessageUpdate) -> MessageOut | None:
        """
        更新消息正文、元数据或摘要覆盖状态。

        message_id: 需要更新的消息 ID。
        message_update: 更新消息 DTO。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(MessageRecord, message_id)
            if record is None:
                return None
            if message_update.content is not None:
                record.content = message_update.content
            if message_update.metadata_json is not None:
                record.metadata_json = message_update.metadata_json
            if message_update.is_summarized is not None:
                record.is_summarized = message_update.is_summarized
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return MessageOut.from_record(record)

    def list_recent_messages(self, *, user_id: str, session_id: str, limit: int) -> list[MessageOut]:
        """
        查询同一会话最近 N 条未摘要消息,并按时间正序返回。

        user_id: 用户 ID,用于防止跨用户读取消息。
        session_id: 会话 ID。
        limit: 最多返回的历史消息数量。
        """

        if limit <= 0:
            return []
        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.session_id == session_id)
            .where(MessageRecord.is_summarized == False)  # noqa: E712
            .order_by(MessageRecord.created_at.desc())
            .limit(limit)
        )
        with Session(self.engine) as db_session:
            records = list(db_session.exec(statement).all())
            records.reverse()
            return [MessageOut.from_record(record) for record in records]

    def list_session_messages(self, *, user_id: str, session_id: str, limit: int) -> list[MessageOut]:
        """
        查询同一会话最近 N 条消息(包含已摘要消息),按时间正序返回。

        供前端加载聊天历史使用,不做 is_summarized 过滤。
        """

        if limit <= 0:
            return []
        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.session_id == session_id)
            .order_by(MessageRecord.created_at.desc())
            .limit(limit)
        )
        with Session(self.engine) as db_session:
            records = list(db_session.exec(statement).all())
            records.reverse()
            return [MessageOut.from_record(record) for record in records]

    def list_unsummarized_messages(self, *, user_id: str, session_id: str) -> list[MessageOut]:
        """
        查询同一会话下所有尚未被摘要覆盖的消息。

        user_id: 用户 ID。
        session_id: 会话 ID。
        """

        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.session_id == session_id)
            .where(MessageRecord.is_summarized == False)  # noqa: E712
            .order_by(MessageRecord.created_at.asc())
        )
        with Session(self.engine) as db_session:
            records = list(db_session.exec(statement).all())
            return [MessageOut.from_record(record) for record in records]

    def mark_messages_summarized(self, *, message_ids: list[str]) -> int:
        """
        将指定消息批量标记为已被摘要覆盖。

        message_ids: 需要标记的消息 ID 列表。
        """

        if not message_ids:
            return 0
        updated_count = 0
        with Session(self.engine) as db_session:
            for message_id in message_ids:
                record = db_session.get(MessageRecord, message_id)
                if record is None:
                    continue
                record.is_summarized = True
                db_session.add(record)
                updated_count += 1
            db_session.commit()
        return updated_count

    @staticmethod
    def generate_message_id() -> str:
        """生成消息 ID。"""

        return f"msg_{uuid4().hex}"

    @staticmethod
    def _utc_now() -> datetime:
        """返回带 UTC 时区的当前时间。"""

        return datetime.now(timezone.utc)
