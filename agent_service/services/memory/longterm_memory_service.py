"""
统一长期记忆业务服务。

功能说明:
本文件负责把会话摘要记忆和知识库切片记忆写入 `LongTermMemorySpec` 表,并在
PostgreSQL 环境下初始化 pgvector 扩展、`embedding_vector` 向量列和 ivfflat
索引。业务层只需要传入统一 DTO,本服务会同时保存 JSON 向量和 pgvector 向量列。

使用说明:
service = LongTermMemoryService(config=config)
memory = service.create_memory(LongTermMemorySpecCreate(...))
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.longterm_memory_spec import LongTermMemorySpec
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate, LongTermMemorySpecOut


class LongTermMemoryService:
    """
    统一长期记忆服务。

    config: 全局配置对象,用于读取向量库 DSN 和常量标签。
    engine: 可选 SQLAlchemy Engine,测试时可注入 SQLite Engine。
    create_tables: 是否初始化 SQLModel 表结构。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        engine: Engine | None = None,
        create_tables: bool = True,
    ) -> None:
        """初始化数据库引擎并按需创建长期记忆表。"""

        self.config = config
        self.engine = engine or create_engine(config.storage.vector_dsn, pool_pre_ping=True)
        self.pgvector_available: bool | None = None
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def create_memory(self, memory_create: LongTermMemorySpecCreate) -> LongTermMemorySpecOut:
        """
        创建长期记忆并写入数据库。

        memory_create: 创建长期记忆 DTO。
        """

        now = self._utc_now()
        vector = memory_create.embedding_vector_json
        if vector:
            self.ensure_pgvector_storage(vector_dimension=len(vector))
        record = LongTermMemorySpec(
            memory_id=self.generate_memory_id(),
            user_id=memory_create.user_id,
            session_id=memory_create.session_id,
            tag=memory_create.tag,
            memory_type=memory_create.memory_type,
            content=memory_create.content,
            source_type=memory_create.source_type,
            source_id=memory_create.source_id,
            source_uri=memory_create.source_uri,
            source_hash=memory_create.source_hash,
            source_range_json=memory_create.source_range_json,
            metadata_json=memory_create.metadata_json,
            valid_from=memory_create.valid_from or now,
            valid_until=memory_create.valid_until,
            confidence=memory_create.confidence,
            importance=memory_create.importance,
            authority=memory_create.authority,
            embedding_model=memory_create.embedding_model,
            embedding_vector_json=vector,
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as db_session:
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
        if vector and self.pgvector_available is not False:
            self._write_pgvector(memory_id=record.memory_id, vector=vector)
        return LongTermMemorySpecOut.from_record(record)

    def has_source_hash(self, *, source_hash: str, memory_type: str) -> bool:
        """
        判断指定来源哈希和记忆类型是否已经入库。

        source_hash: 来源内容哈希。
        memory_type: 记忆类型,例如 `knowledge_chunk`。
        """

        statement = (
            select(LongTermMemorySpec.memory_id)
            .where(LongTermMemorySpec.source_hash == source_hash)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .limit(1)
        )
        with Session(self.engine) as db_session:
            return db_session.exec(statement).first() is not None

    def list_active_fact_memories(
        self,
        *,
        user_id: str,
        namespace: str,
        key: str,
        exclude_memory_id: str | None = None,
    ) -> list[LongTermMemorySpecOut]:
        """
        读取指定用户下当前仍然有效的结构化事实记忆。
        user_id: 用户 ID。
        namespace: 事实命名空间。
        key: 事实键名。
        exclude_memory_id: 可选的排除记忆 ID,用于避免把新事实自己查回来。
        """

        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == self.config.constants.memory_tag)
            .where(LongTermMemorySpec.memory_type == "session_fact")
            .order_by(LongTermMemorySpec.updated_at.desc())
        )
        if exclude_memory_id is not None:
            statement = statement.where(LongTermMemorySpec.memory_id != exclude_memory_id)
        now = self._utc_now()
        with Session(self.engine) as db_session:
            records = db_session.exec(statement).all()
        active_memories: list[LongTermMemorySpecOut] = []
        for record in records:
            metadata_json = record.metadata_json or {}
            fact = metadata_json.get("fact", {})
            if not isinstance(fact, dict):
                continue
            if fact.get("namespace") != namespace or fact.get("key") != key:
                continue
            if metadata_json.get("fact_status", "active") != "active":
                continue
            valid_until = self._ensure_aware_datetime(record.valid_until)
            if valid_until is not None and valid_until <= now:
                continue
            active_memories.append(LongTermMemorySpecOut.from_record(record))
        return active_memories

    def update_fact_status(
        self,
        *,
        memory_id: str,
        fact_status: str,
        valid_until: datetime | None = None,
        superseded_by_memory_id: str | None = None,
    ) -> LongTermMemorySpecOut:
        """
        更新结构化事实记忆的状态。
        memory_id: 需要更新的事实记忆 ID。
        fact_status: 新的事实状态,例如 `active`、`superseded`、`expired`。
        valid_until: 可选失效时间。
        superseded_by_memory_id: 可选覆盖来源记忆 ID。
        """

        with Session(self.engine) as db_session:
            record = db_session.get(LongTermMemorySpec, memory_id)
            if record is None:
                raise ValueError(f"未找到长期记忆: {memory_id}")
            metadata_json = dict(record.metadata_json or {})
            fact = dict(metadata_json.get("fact", {}))
            if fact:
                fact["status"] = fact_status
                if valid_until is not None:
                    fact["valid_until"] = valid_until.isoformat()
                metadata_json["fact"] = fact
            metadata_json["fact_status"] = fact_status
            if superseded_by_memory_id is not None:
                metadata_json["superseded_by_memory_id"] = superseded_by_memory_id
            record.metadata_json = metadata_json
            if valid_until is not None:
                record.valid_until = valid_until
            record.updated_at = self._utc_now()
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return LongTermMemorySpecOut.from_record(record)

    def ensure_pgvector_storage(self, *, vector_dimension: int) -> None:
        """
        在 PostgreSQL 中初始化 pgvector 扩展和向量列。

        vector_dimension: 当前 Embedding 向量维度。
        """

        if vector_dimension <= 0 or not self.engine.dialect.name.startswith("postgresql"):
            return
        if self.pgvector_available is False:
            return
        try:
            with self.engine.begin() as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                existing_dimension = self._get_existing_vector_dimension()
                if existing_dimension is not None and existing_dimension != vector_dimension:
                    raise ValueError(
                        "pgvector 向量列维度与当前 Embedding 维度不一致: "
                        f"existing={existing_dimension}, current={vector_dimension}"
                    )
                connection.execute(
                    text(
                        "ALTER TABLE longterm_memory_specs "
                        f"ADD COLUMN IF NOT EXISTS embedding_vector vector({vector_dimension})"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_longterm_memory_embedding_vector "
                        "ON longterm_memory_specs USING ivfflat (embedding_vector vector_cosine_ops)"
                    )
                )
            self.pgvector_available = True
        except SQLAlchemyError as exc:
            self.pgvector_available = False
            print(
                "pgvector is unavailable; memory will keep embedding_vector_json only. "
                f"{exc.__class__.__name__}: {exc.__cause__ or exc}"
            )

    def _get_existing_vector_dimension(self) -> int | None:
        """
        读取已存在 pgvector 列的维度。

        返回 None 表示向量列尚未创建或当前数据库不是 PostgreSQL。
        """

        if not self.engine.dialect.name.startswith("postgresql"):
            return None
        with self.engine.begin() as connection:
            vector_type = connection.execute(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) "
                    "FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid "
                    "WHERE c.relname = 'longterm_memory_specs' "
                    "AND a.attname = 'embedding_vector' "
                    "AND NOT a.attisdropped"
                )
            ).scalar()
        if not vector_type:
            return None
        match = re.fullmatch(r"vector\((\d+)\)", str(vector_type))
        return int(match.group(1)) if match else None

    def _write_pgvector(self, *, memory_id: str, vector: list[float]) -> None:
        """
        将 JSON 向量同步写入 pgvector 向量列。

        memory_id: 长期记忆 ID。
        vector: Embedding 向量。
        """

        if not self.engine.dialect.name.startswith("postgresql"):
            return
        vector_literal = json.dumps(vector, separators=(",", ":"))
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE longterm_memory_specs "
                        "SET embedding_vector = CAST(:vector_literal AS vector) "
                        "WHERE memory_id = :memory_id"
                    ),
                    {"vector_literal": vector_literal, "memory_id": memory_id},
                )
        except SQLAlchemyError as exc:
            raise RuntimeError("写入 pgvector 向量列失败,请确认数据库已安装 vector 扩展。") from exc

    @staticmethod
    def generate_memory_id() -> str:
        """生成长期记忆 ID。"""

        return f"mem_{uuid4().hex}"

    @staticmethod
    def _utc_now() -> datetime:
        """返回 UTC 当前时间。"""

        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_aware_datetime(value: datetime | None) -> datetime | None:
        """
        将数据库读回的时间统一规范为带 UTC 时区的 datetime。

        value: 可能来自 SQLite 的无时区 datetime。
        """

        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
