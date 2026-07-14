"""
统一长期记忆业务服务。

功能说明:
本文件负责把会话摘要记忆和知识库切片记忆写入 `LongTermMemorySpec` 表,并在
ChromaDB 中管理向量集合。关系数据走 SQLite,向量数据走 ChromaDB PersistentClient。

使用说明:
service = LongTermMemoryService(config=config)
memory = service.create_memory(LongTermMemorySpecCreate(...))
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.models.longterm_memory_spec import LongTermMemorySpec
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate, LongTermMemorySpecOut

try:
    import chromadb
    from chromadb.api.types import EmbeddingFunction
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class LongTermMemoryService:
    """
    统一长期记忆服务。

    config: 全局配置对象,用于读取 SQLite 路径和 ChromaDB 持久化目录。
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
        """初始化 SQLite 引擎和 ChromaDB 客户端,并按需创建表。"""

        self.config = config
        self.engine = engine or create_engine(
            f"sqlite:///{config.storage.sqlite_path}", pool_pre_ping=True
        )
        self._chroma_client = None
        self._chroma_collection = None
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    @property
    def chroma_available(self) -> bool:
        """ChromaDB 是否可用。"""
        return CHROMADB_AVAILABLE and self._chroma_client is not None

    def _ensure_chroma_collection(self, *, vector_dimension: int) -> None:
        """初始化 ChromaDB PersistentClient 并获取或创建向量集合。"""
        if not CHROMADB_AVAILABLE:
            return
        if self._chroma_client is None:
            persist_dir = str(self.config.storage.chroma_persist_dir)
            self._chroma_client = chromadb.PersistentClient(
                path=persist_dir,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
        if self._chroma_collection is not None:
            existing_dim = self._chroma_collection.metadata.get("dimension")
            if existing_dim is not None and int(existing_dim) != vector_dimension:
                self._chroma_client.delete_collection("longterm_memories")
                self._chroma_collection = None
        if self._chroma_collection is None:
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="longterm_memories",
                metadata={"dimension": vector_dimension},
            )
            # get_or_create_collection returns existing collection as-is if it
            # already exists; verify dimension and recreate if needed.
            existing_dim = self._chroma_collection.metadata.get("dimension")
            if existing_dim is not None and int(existing_dim) != vector_dimension:
                self._chroma_client.delete_collection("longterm_memories")
                self._chroma_collection = self._chroma_client.create_collection(
                    name="longterm_memories",
                    metadata={"dimension": vector_dimension},
                )

    def create_memory(self, memory_create: LongTermMemorySpecCreate) -> LongTermMemorySpecOut:
        """
        创建长期记忆并写入数据库。

        memory_create: 创建长期记忆 DTO。
        """

        now = self._utc_now()
        vector = memory_create.embedding_vector_json
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
        if vector:
            self._write_chroma(
                memory_id=record.memory_id,
                vector=vector,
                user_id=record.user_id,
                tag=record.tag,
                memory_type=record.memory_type,
            )
        return LongTermMemorySpecOut.from_record(record)

    def list_user_memories(
        self,
        *,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[LongTermMemorySpecOut]:
        """列出用户的自定义长期记忆。"""
        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == self.config.constants.memory_tag)
            .order_by(LongTermMemorySpec.created_at.desc())
            .limit(limit)
        )
        if memory_type:
            statement = statement.where(LongTermMemorySpec.memory_type == memory_type)
        with Session(self.engine) as db_session:
            rows = db_session.exec(statement).all()
            return [LongTermMemorySpecOut.from_record(r) for r in rows]

    def delete_memory(self, *, memory_id: str) -> bool:
        """删除指定长期记忆。返回是否删除成功。"""
        with Session(self.engine) as db_session:
            record = db_session.get(LongTermMemorySpec, memory_id)
            if record is None:
                return False
            db_session.delete(record)
            db_session.commit()
        if self.chroma_available:
            try:
                self._chroma_collection.delete(ids=[memory_id])
            except Exception:
                pass
        return True

    def delete_memories_for_source(
        self,
        *,
        user_id: str,
        tag: str,
        memory_type: str,
        source_id: str,
    ) -> int:
        """
        删除指定来源对应的长期记忆。

        user_id: 记忆归属用户。
        tag: 记忆大类,例如 Knowledge。
        memory_type: 记忆子类型,例如 knowledge_chunk。
        source_id: 来源文档 ID。
        """

        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .where(LongTermMemorySpec.source_id == source_id)
        )
        return self._delete_selected_memories(statement=statement)

    def delete_memories_except_sources(
        self,
        *,
        user_id: str,
        tag: str,
        memory_type: str,
        keep_source_ids: set[str],
    ) -> int:
        """
        删除本轮扫描未再出现的来源记忆,用于知识库重新扫描后清理已删除文件。

        user_id: 记忆归属用户。
        tag: 记忆大类,例如 Knowledge。
        memory_type: 记忆子类型,例如 knowledge_chunk。
        keep_source_ids: 本轮仍然存在的来源文档 ID 集合。
        """

        statement = (
            select(LongTermMemorySpec)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
        )
        if keep_source_ids:
            statement = statement.where(LongTermMemorySpec.source_id.not_in(keep_source_ids))
        return self._delete_selected_memories(statement=statement)

    def _delete_selected_memories(self, *, statement: Any) -> int:
        """
        执行长期记忆批量删除并尽力同步删除 Chroma 向量。

        statement: 返回 LongTermMemorySpec 记录的 SQLModel 查询。
        """

        with Session(self.engine) as db_session:
            records = list(db_session.exec(statement).all())
            memory_ids = [record.memory_id for record in records]
            for record in records:
                db_session.delete(record)
            db_session.commit()
        if memory_ids and self.chroma_available:
            try:
                self._chroma_collection.delete(ids=memory_ids)
            except Exception:
                pass
        return len(memory_ids)

    def has_source_hash(
        self,
        *,
        source_hash: str,
        memory_type: str,
        user_id: str | None = None,
        source_id: str | None = None,
    ) -> bool:
        """
        判断指定来源哈希和记忆类型是否已经入库。

        source_hash: 来源内容哈希。
        memory_type: 记忆类型,例如 `knowledge_chunk`。
        user_id: 可选记忆归属用户;为空时保持旧的全局哈希判断。
        source_id: 可选来源文档 ID;知识库哈希锁应传入该值,避免不同路径同内容或旧 ID 误跳过。
        """

        statement = (
            select(LongTermMemorySpec.memory_id)
            .where(LongTermMemorySpec.source_hash == source_hash)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .limit(1)
        )
        if user_id is not None:
            statement = statement.where(LongTermMemorySpec.user_id == user_id)
        if source_id is not None:
            statement = statement.where(LongTermMemorySpec.source_id == source_id)
        with Session(self.engine) as db_session:
            return db_session.exec(statement).first() is not None

    def list_source_ids(self, *, user_id: str, tag: str, memory_type: str) -> set[str]:
        """列出指定用户和类型下已存在的来源 ID。"""

        statement = (
            select(LongTermMemorySpec.source_id)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == tag)
            .where(LongTermMemorySpec.memory_type == memory_type)
            .where(LongTermMemorySpec.source_id.is_not(None))
        )
        with Session(self.engine) as db_session:
            return {str(source_id) for source_id in db_session.exec(statement).all() if source_id}

    def has_memories(self, *, user_id: str, tag: str, memory_type: str) -> bool:
        """
        判断指定用户是否已有某类长期记忆。

        user_id: 记忆归属用户。
        tag: 记忆大类。
        memory_type: 记忆子类型。
        """

        statement = (
            select(LongTermMemorySpec.memory_id)
            .where(LongTermMemorySpec.user_id == user_id)
            .where(LongTermMemorySpec.tag == tag)
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

    def _write_chroma(
        self,
        *,
        memory_id: str,
        vector: list[float],
        user_id: str = "",
        tag: str = "",
        memory_type: str = "",
    ) -> None:
        """将 embedding 向量写入 ChromaDB 集合。"""
        if not CHROMADB_AVAILABLE:
            return
        self._ensure_chroma_collection(vector_dimension=len(vector))
        if self._chroma_collection is not None:
            self._chroma_collection.upsert(
                ids=[memory_id],
                embeddings=[vector],
                metadatas=[{"user_id": user_id, "tag": tag, "memory_type": memory_type}],
            )

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

    def search_knowledge_content(
        self,
        *,
        query: str,
        user_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        在知识库切片的 content 字段中做全文模糊搜索。

        query: 搜索关键词。
        user_id: 当前用户 ID。
        limit: 最多返回条数。
        """

        from sqlalchemy import func

        like_pattern = f"%{query}%"
        with Session(self.engine) as db_session:
            rows = db_session.exec(
                select(
                    LongTermMemorySpec.source_uri,
                    LongTermMemorySpec.content,
                    func.length(LongTermMemorySpec.content).label("content_len"),
                )
                .where(LongTermMemorySpec.user_id.like(f"{user_id}%"))
                .where(LongTermMemorySpec.tag == "Knowledge")
                .where(LongTermMemorySpec.memory_type == "knowledge_chunk")
                .where(LongTermMemorySpec.content.ilike(like_pattern))
                .order_by(LongTermMemorySpec.source_uri)
                .limit(limit * 10)
            ).all()

        seen: set[str] = set()
        results: list[dict[str, Any]] = []
        for source_uri, content, content_len in rows:
            if source_uri in seen:
                continue
            seen.add(source_uri)
            pos = content.lower().find(query.lower())
            start = max(0, pos - 80)
            end = min(content_len, pos + len(query) + 80)
            snippet = content[start:end]
            if start > 0:
                snippet = f"...{snippet}"
            if end < content_len:
                snippet = f"{snippet}..."
            results.append({"source_uri": source_uri, "snippet": snippet})
            if len(results) >= limit:
                break
        return results
