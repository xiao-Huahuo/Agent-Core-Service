"""
Session 会话业务服务。

功能说明:
本文件实现会话生命周期管理业务逻辑,直接使用 PostgreSQL 作为持久化数据库。
服务层负责创建、查询、重命名和删除会话;`AgentCore` 只消费已有的 `session_id`,
不负责会话生命周期。

使用说明:
调用方需要显式传入 `AgentConfig`:

config = AgentConfig.load_config()
service = SessionService(config=config)
session = service.create_session(SessionCreate(user_id="u1"))
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.message import MessageRecord
from agent_service.models.session import SessionRecord
from agent_service.schemas.session import SessionCreate, SessionOut, SessionUpdate


class SessionService:
    """
    会话管理业务服务。

    config: 全局配置对象,用于读取 PostgreSQL 连接地址和默认会话名。
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
        """初始化 PostgreSQL 引擎,并按需创建会话表。"""

        self.config = config
        self.engine = engine or create_engine(config.storage.relational_dsn, pool_pre_ping=True)
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def create_session(self, session_create: SessionCreate) -> SessionOut:
        """
        创建新会话并写入 PostgreSQL。

        session_create: 创建会话 DTO。
        """

        now = self._utc_now()
        record = SessionRecord(
            session_id=self.generate_session_id(),
            user_id=session_create.user_id,
            session_name=session_create.session_name or self.config.constants.default_session_name,
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as db_session:
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return SessionOut.from_record(record)

    def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话。

        session_id: 需要删除的会话 ID。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(SessionRecord, session_id)
            if record is None:
                return False
            # 先删除关联的消息，再删除会话
            msgs = db_session.exec(
                select(MessageRecord).where(MessageRecord.session_id == session_id)
            ).all()
            for msg in msgs:
                db_session.delete(msg)
            db_session.delete(record)
            db_session.commit()
            return True

    def delete_all_user_sessions(self, user_id: str) -> int:
        """
        删除指定用户的所有会话,返回删除数量。

        user_id: 需要清空会话的用户 ID。
        """

        with Session(self.engine) as db_session:
            records = db_session.exec(
                select(SessionRecord).where(SessionRecord.user_id == user_id)
            ).all()
            count = len(records)
            # 先删除所有关联消息
            for record in records:
                msgs = db_session.exec(
                    select(MessageRecord).where(MessageRecord.session_id == record.session_id)
                ).all()
                for msg in msgs:
                    db_session.delete(msg)
            # 再删除会话
            for record in records:
                db_session.delete(record)
            db_session.commit()
            return count

    def update_session_name(self, session_id: str, session_update: SessionUpdate) -> SessionOut | None:
        """
        更新会话显示名称。

        session_id: 需要更新的会话 ID。
        session_update: 更新会话 DTO。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(SessionRecord, session_id)
            if record is None:
                return None
            record.session_name = session_update.session_name
            record.updated_at = self._utc_now()
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return SessionOut.from_record(record)

    def get_session(self, session_id: str) -> SessionOut | None:
        """
        查询单个会话。

        session_id: 需要查询的会话 ID。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(SessionRecord, session_id)
            if record is None:
                return None
            return SessionOut.from_record(record)

    def list_user_sessions(self, user_id: str) -> list[SessionOut]:
        """
        查询用户所有会话,按更新时间倒序排列。

        user_id: 需要查询的用户 ID。
        """

        statement = (
            select(SessionRecord)
            .where(SessionRecord.user_id == user_id)
            .order_by(SessionRecord.updated_at.desc())
        )
        with Session(self.engine) as db_session:
            records = db_session.exec(statement).all()
            return [SessionOut.from_record(record) for record in records]

    @staticmethod
    def generate_session_id() -> str:
        """生成会话 ID。"""

        return f"sess_{uuid4().hex}"

    @staticmethod
    def _utc_now() -> datetime:
        """返回带 UTC 时区的当前时间。"""

        return datetime.now(timezone.utc)
