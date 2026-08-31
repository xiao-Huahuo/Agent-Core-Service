"""
Session 会话业务服务。

功能说明:
本文件实现会话生命周期管理业务逻辑,直接使用 SQLite 作为持久化数据库。
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
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.core.db.engine import get_database_engine
from agent_service.models.message import MessageRecord
from agent_service.models.session import SessionRecord
from agent_service.models.token_usage import TokenUsageRecord
from agent_service.schemas.session import SessionCreate, SessionOut, SessionUpdate


class SessionService:
    """
    会话管理业务服务。

    config: 全局配置对象,用于读取 SQLite 连接地址和默认会话名。
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
        """初始化 SQLite 引擎,并按需创建会话表。"""

        self.config = config
        self.engine = engine or get_database_engine(config)

    def create_session(self, session_create: SessionCreate) -> SessionOut:
        """
        创建新会话并写入 SQLite。

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

    def create_child_agent_session(
        self,
        *,
        user_id: str,
        parent_session_id: str,
        run_id: str,
        session_name: str,
        provider: str = "native",
        dsh_session_id: str | None = None,
        workspace_root: str = "",
        dsh_runtime_version: str | None = None,
    ) -> SessionOut:
        """创建或返回一个不会进入根会话历史列表的子 Agent 对话。"""

        session_id = self.child_agent_session_id(parent_session_id, run_id)
        with Session(self.engine) as db_session:
            parent = db_session.get(SessionRecord, parent_session_id)
            if parent is None or parent.user_id != user_id or parent.parent_session_id is not None:
                raise ValueError("子 Agent 对话必须归属于同一用户的根会话。")
            existing = db_session.get(SessionRecord, session_id)
            if existing is not None:
                return SessionOut.from_record(existing)
            now = self._utc_now()
            record = SessionRecord(
                session_id=session_id,
                user_id=user_id,
                session_name=session_name,
                parent_session_id=parent_session_id,
                child_agent_run_id=run_id,
                child_agent_provider=provider,
                dsh_session_id=dsh_session_id,
                child_workspace_root=workspace_root or None,
                dsh_runtime_version=dsh_runtime_version,
                created_at=now,
                updated_at=now,
            )
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
            child_records = list(db_session.exec(
                select(SessionRecord).where(SessionRecord.parent_session_id == session_id)
            ).all())
            for target in [*child_records, record]:
                self._delete_session_record(db_session, target)
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
            count = sum(record.parent_session_id is None for record in records)
            for record in sorted(records, key=lambda item: item.parent_session_id is None):
                self._delete_session_record(db_session, record)
            db_session.commit()
            return count

    def prune_empty_sessions(self, user_id: str) -> int:
        """Delete sessions that have zero messages for the given user. Returns the count pruned."""

        with Session(self.engine) as db_session:
            records = db_session.exec(
                select(SessionRecord)
                .where(SessionRecord.user_id == user_id)
                .where(SessionRecord.parent_session_id.is_(None))
            ).all()
            pruned = 0
            for record in records:
                count = db_session.exec(
                    select(func.count(MessageRecord.message_id)).where(
                        MessageRecord.session_id == record.session_id
                    )
                ).one()
                if count == 0:
                    db_session.delete(record)
                    pruned += 1
            db_session.commit()
            return pruned

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

    def update_session_state(self, session_id: str, state_json: str | None) -> bool:
        """
        更新会话 Agent 探索状态。

        session_id: 会话 ID。
        state_json: 探索状态 JSON 字符串,为 None 时清空状态。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(SessionRecord, session_id)
            if record is None:
                return False
            record.state_json = state_json
            record.updated_at = self._utc_now()
            db_session.add(record)
            db_session.commit()
            return True

    def get_session_state(self, session_id: str) -> str | None:
        """
        获取会话 Agent 探索状态。

        session_id: 会话 ID。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(SessionRecord, session_id)
            if record is None:
                return None
            return record.state_json

    def list_user_sessions(self, user_id: str) -> list[SessionOut]:
        """
        查询用户所有会话,按更新时间倒序排列。

        user_id: 需要查询的用户 ID。
        """

        statement = (
            select(SessionRecord)
            .where(SessionRecord.user_id == user_id)
            .where(SessionRecord.parent_session_id.is_(None))
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
    def child_agent_session_id(parent_session_id: str, run_id: str) -> str:
        """生成稳定且定长的子 Agent 对话 Session ID。"""

        digest = sha256(f"{parent_session_id}\0{run_id}".encode("utf-8")).hexdigest()
        return f"child_{digest[:58]}"

    @staticmethod
    def _delete_session_record(db_session: Session, record: SessionRecord) -> None:
        """删除一个 Session 及其消息和 token 用量记录。"""

        for message in db_session.exec(
            select(MessageRecord).where(MessageRecord.session_id == record.session_id)
        ).all():
            db_session.delete(message)
        for usage in db_session.exec(
            select(TokenUsageRecord).where(TokenUsageRecord.session_id == record.session_id)
        ).all():
            db_session.delete(usage)
        db_session.delete(record)

    @staticmethod
    def _utc_now() -> datetime:
        """返回带 UTC 时区的当前时间。"""

        return datetime.now(timezone.utc)
