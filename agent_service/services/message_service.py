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

from sqlalchemy import and_, or_
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.message import MessageRecord
from agent_service.schemas.message import MessageCreate, MessageOut, MessageUpdate
from agent_service.services.token_usage_service import TokenUsageService


# Trace fields required by RAG and latency curve calculations. Large raw tool
# results and context snapshots are deliberately excluded from history payloads.
OBSERVABILITY_TRACE_FIELDS = (
    "node",
    "event",
    "duration_ms",
    "ts",
    "tool_name",
    "tool_call_id",
    "tool_args_summary",
    "result_count",
    "confidence",
)


class MessageService:
    """
    会话消息业务服务。

    config: 全局配置对象,用于读取 SQLite 连接地址。
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
        self.engine = engine or create_engine(f"sqlite:///{config.storage.sqlite_path}", pool_pre_ping=True)
        self.token_usage_service = TokenUsageService(config=config, engine=self.engine, create_tables=create_tables)
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
            result = MessageOut.from_record(record)
        if record.role == "assistant":
            self.token_usage_service.record_message_token_usage(record)
        return result

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

    def list_recent_messages(
        self, *, user_id: str, session_id: str, limit: int, include_summarized: bool = False
    ) -> list[MessageOut]:
        """
        查询同一会话最近 N 条消息,并按时间正序返回。

        user_id: 用户 ID,用于防止跨用户读取消息。
        session_id: 会话 ID。
        limit: 最多返回的历史消息数量。
        include_summarized: 是否包含已摘要消息,默认 False 仅返回未摘要。
        """

        if limit is not None and limit <= 0:
            return []
        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.session_id == session_id)
            .order_by(MessageRecord.created_at.desc(), MessageRecord.message_id.desc())
            .limit(limit)
        )
        if not include_summarized:
            statement = statement.where(MessageRecord.is_summarized == False)  # noqa: E712
        with Session(self.engine) as db_session:
            records = list(db_session.exec(statement).all())
            records.reverse()
            return [MessageOut.from_record(record) for record in records]

    def list_session_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int | None,
        exclude_roles: list[str] | None = None,
    ) -> list[MessageOut]:
        """
        查询同一会话最近 N 条消息(包含已摘要消息),按时间正序返回。

        供前端加载聊天历史使用,不做 is_summarized 过滤。
        exclude_roles: 可选,排除指定角色的消息(如 ["system"]),在 DB 层面过滤,
                       避免浪费 limit 配额。
        """

        if limit is not None and limit <= 0:
            return []
        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.session_id == session_id)
        )
        if exclude_roles:
            statement = statement.where(~MessageRecord.role.in_(exclude_roles))
        statement = statement.order_by(MessageRecord.created_at.desc(), MessageRecord.message_id.desc())
        if limit is not None:
            statement = statement.limit(limit)
        with Session(self.engine) as db_session:
            records = list(db_session.exec(statement).all())
            records.reverse()
            return [MessageOut.from_record(record) for record in records]

    def list_user_messages(self, *, user_id: str, limit: int | None = None) -> list[MessageOut]:
        """
        查询用户全部 session 的消息历史并按时间正序返回。

        user_id: 用户 ID,用于隔离不同用户的观测数据。
        limit: 可选的最近消息数量上限;为空时返回该用户的完整历史。
        """

        statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .order_by(MessageRecord.created_at.asc(), MessageRecord.message_id.asc())
        )
        if limit is None:
            with Session(self.engine) as db_session:
                records = list(db_session.exec(statement).all())
                return [MessageOut.from_record(record) for record in records]

        if limit is not None and limit <= 0:
            return []
        recent_statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .order_by(MessageRecord.created_at.desc(), MessageRecord.message_id.desc())
            .limit(limit)
        )
        with Session(self.engine) as db_session:
            records = list(db_session.exec(recent_statement).all())
            records.reverse()
            return [MessageOut.from_record(record) for record in records]

    def list_user_observability_messages(
        self,
        *,
        user_id: str,
        turn_limit: int | None,
    ) -> list[MessageOut]:
        """
        查询用户最近 N 个对话轮次所需的观测消息。

        user_id: 用户 ID,用于隔离不同用户的观测数据。
        turn_limit: 最近用户 message 的数量;为空时返回完整历史。

        每个轮次保留用户消息、与其时间最近的 RAG 指标系统消息,以及该
        Session 下一条用户消息之前产生的 assistant/tool 消息。这样前端
        无需下载完整事件表即可计算 RAG 三率和每次 message 耗时。
        """

        if turn_limit is None:
            return self.list_user_messages(user_id=user_id)
        if turn_limit <= 0:
            return []

        recent_user_statement = (
            select(MessageRecord)
            .where(MessageRecord.user_id == user_id)
            .where(MessageRecord.role == "user")
            .order_by(MessageRecord.created_at.desc(), MessageRecord.message_id.desc())
            .limit(turn_limit)
        )
        with Session(self.engine) as db_session:
            recent_user_records = list(db_session.exec(recent_user_statement).all())
            if not recent_user_records:
                return []

            session_ids = {record.session_id for record in recent_user_records}
            session_user_statement = (
                select(MessageRecord)
                .where(MessageRecord.user_id == user_id)
                .where(MessageRecord.role == "user")
                .where(MessageRecord.session_id.in_(session_ids))
                .order_by(MessageRecord.created_at.asc(), MessageRecord.message_id.asc())
            )
            session_user_records = list(db_session.exec(session_user_statement).all())

            earliest_selected_by_session: dict[str, MessageRecord] = {}
            for record in reversed(recent_user_records):
                earliest_selected_by_session.setdefault(record.session_id, record)

            lower_bounds: dict[str, MessageRecord | None] = {}
            users_by_session: dict[str, list[MessageRecord]] = {}
            for record in session_user_records:
                users_by_session.setdefault(record.session_id, []).append(record)
            for session_id, earliest_selected in earliest_selected_by_session.items():
                previous_user: MessageRecord | None = None
                for record in users_by_session.get(session_id, []):
                    if record.message_id == earliest_selected.message_id:
                        break
                    previous_user = record
                lower_bounds[session_id] = previous_user

            session_ranges = []
            for session_id, previous_user in lower_bounds.items():
                session_filter = MessageRecord.session_id == session_id
                if previous_user is not None:
                    session_filter = and_(
                        session_filter,
                        or_(
                            MessageRecord.created_at > previous_user.created_at,
                            and_(
                                MessageRecord.created_at == previous_user.created_at,
                                MessageRecord.message_id > previous_user.message_id,
                            ),
                        ),
                    )
                session_ranges.append(session_filter)

            candidate_statement = (
                select(MessageRecord)
                .where(MessageRecord.user_id == user_id)
                .where(MessageRecord.role.in_(["user", "system", "assistant", "tool"]))
                .where(or_(*session_ranges))
                .order_by(MessageRecord.created_at.asc(), MessageRecord.message_id.asc())
            )
            candidate_records = list(db_session.exec(candidate_statement).all())
            messages = [MessageOut.from_record(record) for record in candidate_records]

        role_order = {"system": 0, "user": 1, "assistant": 2, "tool": 3}
        messages.sort(
            key=lambda message: (
                message.created_at,
                role_order.get(message.role, 4),
                message.message_id,
            )
        )
        selected_user_ids = {
            record.message_id
            for record in recent_user_records
        }

        previous_user_by_message: dict[str, MessageOut] = {}
        previous_user_by_session: dict[str, MessageOut] = {}
        for message in messages:
            previous = previous_user_by_session.get(message.session_id)
            if previous is not None:
                previous_user_by_message[message.message_id] = previous
            if message.role == "user":
                previous_user_by_session[message.session_id] = message
                previous_user_by_message[message.message_id] = message

        next_user_by_message: dict[str, MessageOut] = {}
        next_user_by_session: dict[str, MessageOut] = {}
        for message in reversed(messages):
            following = next_user_by_session.get(message.session_id)
            if following is not None:
                next_user_by_message[message.message_id] = following
            if message.role == "user":
                next_user_by_session[message.session_id] = message
                next_user_by_message[message.message_id] = message

        selected_messages: list[MessageOut] = []
        for message in messages:
            owner: MessageOut | None = None
            if message.role == "user":
                owner = message
            elif message.role == "system" and (message.metadata_json or {}).get("rag_metrics"):
                # ContextBuilder persists RAG metrics immediately before the
                # user prompt row, so the following user owns this sample.
                owner = (
                    next_user_by_message.get(message.message_id)
                    or previous_user_by_message.get(message.message_id)
                )
            elif message.role in {"assistant", "tool"}:
                owner = previous_user_by_message.get(message.message_id)

            if owner is not None and owner.message_id in selected_user_ids:
                selected_messages.append(message)
        return selected_messages

    @staticmethod
    def compact_observability_metadata(metadata: dict | None) -> dict:
        """
        保留曲线计算需要的 message metadata 字段。

        metadata: 数据库存储的完整消息元数据。返回值会移除 raw_content、
        context_messages 等体积较大的调试字段。
        """

        source = metadata or {}
        compact: dict = {}
        node = source.get("node")
        if node:
            compact["node"] = node
        rag_metrics = source.get("rag_metrics")
        if isinstance(rag_metrics, dict):
            compact["rag_metrics"] = rag_metrics
        traces = source.get("trace")
        if isinstance(traces, list):
            compact["trace"] = [
                {
                    key: trace[key]
                    for key in OBSERVABILITY_TRACE_FIELDS
                    if key in trace
                }
                for trace in traces
                if isinstance(trace, dict)
            ]
        return compact

    @staticmethod
    def compact_observability_tool_calls(tool_calls: list | None) -> list[dict]:
        """
        保留工具调用计数和标识所需字段,移除可能很大的参数正文。

        tool_calls: 数据库存储的完整工具调用列表。
        """

        return [
            {
                key: tool_call[key]
                for key in ("id", "name")
                if key in tool_call
            }
            for tool_call in (tool_calls or [])
            if isinstance(tool_call, dict)
        ]

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
