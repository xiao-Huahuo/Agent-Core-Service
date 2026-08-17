"""
User feedback business service.

功能说明:
本服务负责用户反馈查询、入库、修改和删除。反馈是业务数据,统一写入 SQLite 表,不允许降级为
浏览器存储或文件型临时存储。

使用说明:
REST/gRPC 层注入 `FeedbackService` 后调用 `list_feedback`、`add_feedback`、
`update_feedback` 和 `delete_feedback` 管理当前用户反馈。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

import agent_service.models  # noqa: F401
from agent_service.models.feedback import FeedbackRecord
from agent_service.schemas.feedback import FeedbackCreate, FeedbackOut, FeedbackUpdate


class FeedbackService:
    """
    用户反馈业务服务。

    engine: SQLAlchemy Engine,通常复用 settings_service.engine。
    create_tables: 是否确保反馈表存在。
    """

    def __init__(self, *, engine: Engine, create_tables: bool = True) -> None:
        """保存数据库引擎并按需创建反馈表。"""

        self.engine = engine
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def add_feedback(self, payload: FeedbackCreate) -> FeedbackOut:
        """校验并写入一条用户反馈。"""

        record = FeedbackRecord(
            feedback_id=self.generate_feedback_id(),
            user_id=self._required(payload.user_id, "user_id"),
            content=self._required(payload.content, "content"),
            source=(payload.source or "editor_activity_bar").strip()[:128],
            page=(payload.page or "").strip()[:128],
            created_at=self._utc_now(),
        )
        with Session(self.engine) as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_out(record)

    def list_feedback(self, *, user_id: str | None = None) -> list[FeedbackOut]:
        """按创建时间倒序列出反馈;传入用户 ID 时仅返回该用户反馈。"""

        normalized_user_id = str(user_id or "").strip()
        statement = select(FeedbackRecord)
        if normalized_user_id:
            statement = statement.where(FeedbackRecord.user_id == normalized_user_id)
        statement = statement.order_by(FeedbackRecord.created_at.desc())
        with Session(self.engine) as db:
            records = db.exec(statement).all()
            return [self._to_out(record) for record in records]

    def update_feedback(self, *, feedback_id: str, payload: FeedbackUpdate) -> FeedbackOut | None:
        """修改指定反馈内容,找不到记录时返回 None。"""

        normalized_feedback_id = self._required(feedback_id, "feedback_id")
        normalized_content = self._required(payload.content, "content")
        with Session(self.engine) as db:
            record = db.get(FeedbackRecord, normalized_feedback_id)
            if record is None:
                return None
            record.content = normalized_content
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_out(record)

    def get_feedback(self, *, feedback_id: str, user_id: str | None = None) -> FeedbackOut | None:
        """按 ID 读取反馈；提供 user_id 时同时校验反馈所有权。"""

        normalized_feedback_id = self._required(feedback_id, "feedback_id")
        normalized_user_id = str(user_id or "").strip()
        with Session(self.engine) as db:
            statement = select(FeedbackRecord).where(FeedbackRecord.feedback_id == normalized_feedback_id)
            if normalized_user_id:
                statement = statement.where(FeedbackRecord.user_id == normalized_user_id)
            record = db.exec(statement).first()
            return self._to_out(record) if record is not None else None

    def delete_feedback(self, *, feedback_id: str) -> bool:
        """删除指定反馈,返回是否实际删除。"""

        normalized_feedback_id = self._required(feedback_id, "feedback_id")
        with Session(self.engine) as db:
            record = db.get(FeedbackRecord, normalized_feedback_id)
            if record is None:
                return False
            db.delete(record)
            db.commit()
            return True

    @staticmethod
    def generate_feedback_id() -> str:
        """生成反馈 ID。"""

        return f"fb_{uuid4().hex}"

    @staticmethod
    def _utc_now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    @staticmethod
    def _required(value: str, field_name: str) -> str:
        """校验并规范化必填字符串字段。"""

        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _to_out(record: FeedbackRecord) -> FeedbackOut:
        """将数据库记录转换为 API DTO。"""

        return FeedbackOut(
            feedback_id=record.feedback_id,
            user_id=record.user_id,
            content=record.content,
            source=record.source,
            page=record.page,
            created_at=record.created_at,
        )
