"""
用户设置服务。

管理用户自定义系统提示词条目(数据库持久化)和用户自定义长期记忆(向量库持久化)。
系统提示词以条目形式存储，启动时全部加载并拼接注入到 agent 系统提示词。
"""

from __future__ import annotations

import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select
from sqlalchemy import text

from agent_service.core.agent_config import AgentConfig
from agent_service.models.user_settings import (
    UserKnowledgeLibrary,
    UserLLMConfig,
    UserSettingsRecord,
    UserSystemPromptEntry,
)
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import _get_shared_provider

logger = logging.getLogger(__name__)


class SettingsService:
    """用户设置服务 — 系统提示词条目 + 自定义长期记忆管理。"""

    def __init__(
        self,
        *,
        config: AgentConfig,
        memory_service: LongTermMemoryService,
    ) -> None:
        self.config = config
        self.memory_service = memory_service
        self.engine = memory_service.engine
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(self.engine)
        self._ensure_llm_config_schema()
        self._ensure_user_settings_schema()

    def _ensure_llm_config_schema(self) -> None:
        """Ensure user_llm_config table has the small_api_key / small_base_url / small_model_name columns."""
        from sqlalchemy import inspect as sa_inspect
        try:
            inspector = sa_inspect(self.engine)
            columns = [c["name"] for c in inspector.get_columns("user_llm_config")]
            migrations = {
                "small_api_key": "VARCHAR(1024) NOT NULL DEFAULT ''",
                "small_base_url": "VARCHAR(1024) NOT NULL DEFAULT ''",
                "small_model_name": "VARCHAR(256) NOT NULL DEFAULT ''",
            }
            with Session(self.engine) as db:
                for col_name, col_type in migrations.items():
                    if col_name not in columns:
                        db.execute(text(f"ALTER TABLE user_llm_config ADD COLUMN {col_name} {col_type}"))
                        logger.info("Schema migration: added column %s to user_llm_config", col_name)
                db.commit()
        except Exception:
            pass  # Table may not exist yet; create_all handles it

    def _ensure_user_settings_schema(self) -> None:
        """Ensure user_settings table has proxy_url / web_search_enabled columns."""
        from sqlalchemy import inspect as sa_inspect
        try:
            inspector = sa_inspect(self.engine)
            columns = [c["name"] for c in inspector.get_columns("user_settings")]
            migrations = {
                "proxy_url": "VARCHAR(1024) NOT NULL DEFAULT ''",
                "web_search_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            }
            with Session(self.engine) as db:
                for col_name, col_type in migrations.items():
                    if col_name not in columns:
                        db.execute(text(f"ALTER TABLE user_settings ADD COLUMN {col_name} {col_type}"))
                        logger.info("Schema migration: added column %s to user_settings", col_name)
                db.commit()
        except Exception:
            pass

    @staticmethod
    def _generate_prompt_id() -> str:
        return f"prompt_{uuid4().hex[:12]}"

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ---- 用户设置档案 ----

    def ensure_user_profile(self, *, user_id: str) -> dict:
        """确保用户设置档案存在,并返回 editor/console 可共享的基础设置。"""
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")

        with Session(self.engine) as db:
            record = db.get(UserSettingsRecord, normalized_user_id)
            if record is None:
                now = self._utc_now()
                record = UserSettingsRecord(
                    user_id=normalized_user_id,
                    knowledge_dir=str(self.config.storage.knowledge_dir),
                    created_at=now,
                    updated_at=now,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
            active_library = self._ensure_active_library(db=db, record=record)
            return self._serialize_user_profile(record)

    def update_knowledge_dir(self, *, user_id: str, knowledge_dir: str, name: str | None = None) -> dict:
        """
        更新用户当前知识库目录并返回设置档案。

        user_id: 用户 ID。
        knowledge_dir: 用户选择的知识库目录,可为绝对路径或项目根相对路径。
        name: 用户显式设置的知识库显示名,为空时保留已有名称或使用目录名。
        """

        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")
        normalized_knowledge_dir = self._resolve_knowledge_dir(knowledge_dir)
        now = self._utc_now()
        with Session(self.engine) as db:
            record = db.get(UserSettingsRecord, normalized_user_id)
            if record is None:
                record = UserSettingsRecord(
                    user_id=normalized_user_id,
                    knowledge_dir=str(normalized_knowledge_dir),
                    created_at=now,
                    updated_at=now,
                )
            else:
                record.knowledge_dir = str(normalized_knowledge_dir)
                record.updated_at = now
            db.add(record)
            active_library = self._upsert_active_library(
                db=db,
                user_id=normalized_user_id,
                knowledge_dir=normalized_knowledge_dir,
                name=name,
                now=now,
            )
            db.commit()
            db.refresh(record)
            db.refresh(active_library)
            return self._serialize_user_profile(record)

    def get_active_knowledge_library(self, *, user_id: str) -> dict:
        """
        获取用户当前 active 知识库配置。

        user_id: 用户 ID。
        """

        profile = self.ensure_user_profile(user_id=user_id)
        return dict(profile["active_knowledge_library"])

    def resolve_active_knowledge_owner_id(self, *, user_id: str) -> str:
        """
        返回当前 active 知识库在长期记忆表中的隔离 owner ID。

        user_id: 用户 ID。
        """

        active_library = self.get_active_knowledge_library(user_id=user_id)
        return self.build_knowledge_owner_id(
            user_id=user_id.strip(),
            library_id=str(active_library["library_id"]),
        )

    def _resolve_knowledge_dir(self, knowledge_dir: str) -> Path:
        """
        将用户传入的知识库目录解析为绝对路径。

        knowledge_dir: 用户输入目录;为空时使用默认知识库目录。
        """

        normalized = knowledge_dir.strip()
        if not normalized:
            return self.config.storage.knowledge_dir
        path = Path(normalized).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (self.config.storage.project_root / path).resolve()

    def _ensure_active_library(self, *, db: Session, record: UserSettingsRecord) -> UserKnowledgeLibrary:
        """
        确保用户至少拥有一个 active 知识库。

        db: 当前数据库 session。
        record: 用户设置记录。
        """

        statement = (
            select(UserKnowledgeLibrary)
            .where(UserKnowledgeLibrary.user_id == record.user_id)
            .where(UserKnowledgeLibrary.is_active == True)  # noqa: E712
            .limit(1)
        )
        active_library = db.exec(statement).first()
        if active_library is not None:
            return active_library
        libraries = list(
            db.exec(
                select(UserKnowledgeLibrary)
                .where(UserKnowledgeLibrary.user_id == record.user_id)
                .order_by(UserKnowledgeLibrary.updated_at.desc())
            ).all()
        )
        if libraries:
            active_library = libraries[0]
            now = self._utc_now()
            for library in libraries:
                library.is_active = library.library_id == active_library.library_id
                library.updated_at = now
                db.add(library)
            record.knowledge_dir = active_library.knowledge_dir
            record.updated_at = now
            db.add(record)
            db.commit()
            db.refresh(active_library)
            db.refresh(record)
            return active_library
        now = self._utc_now()
        library = self._upsert_active_library(
            db=db,
            user_id=record.user_id,
            knowledge_dir=self._resolve_knowledge_dir(record.knowledge_dir),
            now=now,
        )
        record.knowledge_dir = library.knowledge_dir
        record.updated_at = now
        db.add(record)
        db.commit()
        db.refresh(library)
        db.refresh(record)
        return library

    def _upsert_active_library(
        self,
        *,
        db: Session,
        user_id: str,
        knowledge_dir: Path,
        name: str | None = None,
        now: datetime,
    ) -> UserKnowledgeLibrary:
        """
        创建或更新用户知识库配置,并将其设为唯一 active。

        db: 当前数据库 session。
        user_id: 用户 ID。
        knowledge_dir: 规范化后的知识库目录。
        name: 可选知识库显示名。
        now: 当前 UTC 时间。
        """

        normalized_dir = str(knowledge_dir)
        library_id = self.build_library_id(user_id=user_id, knowledge_dir=normalized_dir)
        normalized_name = (name or "").strip()
        fallback_name = knowledge_dir.name or normalized_dir
        libraries = list(db.exec(select(UserKnowledgeLibrary).where(UserKnowledgeLibrary.user_id == user_id)).all())
        library = next((item for item in libraries if item.library_id == library_id), None)
        if library is None:
            library = UserKnowledgeLibrary(
                library_id=library_id,
                user_id=user_id,
                name=normalized_name or fallback_name,
                knowledge_dir=normalized_dir,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        else:
            library.knowledge_dir = normalized_dir
            library.name = normalized_name or library.name or fallback_name
            library.updated_at = now
        for item in libraries:
            item.is_active = item.library_id == library_id
            item.updated_at = now
            db.add(item)
        library.is_active = True
        db.add(library)
        return library

    def _list_knowledge_libraries(self, *, user_id: str) -> list[UserKnowledgeLibrary]:
        """
        列出用户全部知识库配置。

        user_id: 用户 ID。
        """

        with Session(self.engine) as db:
            statement = (
                select(UserKnowledgeLibrary)
                .where(UserKnowledgeLibrary.user_id == user_id)
                .order_by(UserKnowledgeLibrary.updated_at.desc())
            )
            return list(db.exec(statement).all())

    def _serialize_user_profile(self, record: UserSettingsRecord) -> dict:
        """将用户设置记录转换为 REST 响应。"""
        libraries = self._list_knowledge_libraries(user_id=record.user_id)
        active_library = next((item for item in libraries if item.is_active), None)
        if active_library is None and libraries:
            active_library = libraries[0]
        return {
            "user_id": record.user_id,
            "knowledge_dir": active_library.knowledge_dir if active_library else record.knowledge_dir,
            "active_library_id": active_library.library_id if active_library else "",
            "active_knowledge_library": (
                self._serialize_knowledge_library(active_library) if active_library else None
            ),
            "knowledge_libraries": [self._serialize_knowledge_library(item) for item in libraries],
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    @staticmethod
    def _serialize_knowledge_library(record: UserKnowledgeLibrary) -> dict:
        """
        将知识库配置记录转换为 API 响应。

        record: 知识库配置记录。
        """

        return {
            "library_id": record.library_id,
            "user_id": record.user_id,
            "name": record.name,
            "knowledge_dir": record.knowledge_dir,
            "is_active": record.is_active,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    @staticmethod
    def build_library_id(*, user_id: str, knowledge_dir: str) -> str:
        """
        根据用户和知识库目录生成稳定配置 ID。

        user_id: 用户 ID。
        knowledge_dir: 规范化后的知识库目录。
        """

        digest = hashlib.sha256(f"{user_id}\0{knowledge_dir}".encode("utf-8")).hexdigest()[:16]
        return f"kb_{digest}"

    @staticmethod
    def build_knowledge_owner_id(*, user_id: str, library_id: str) -> str:
        """
        构造长期记忆表中隔离知识库切片的 owner ID。

        user_id: 用户 ID。
        library_id: 知识库配置 ID。
        """

        return f"{user_id}::knowledge::{library_id}"

    # ---- 系统提示词条目 ----

    def get_system_prompt(self, *, user_id: str) -> str:
        """获取用户所有自定义系统提示词条目，拼接为完整提示词。"""
        entries = self._list_entries(user_id)
        if not entries:
            return ""
        return "\n\n".join(e.content for e in entries)

    def list_system_prompt_entries(self, *, user_id: str) -> list[dict]:
        """列出用户的所有系统提示词条目。"""
        entries = self._list_entries(user_id)
        return [
            {"prompt_id": e.prompt_id, "content": e.content, "created_at": e.created_at.isoformat()}
            for e in entries
        ]

    def add_system_prompt_entry(self, *, user_id: str, content: str) -> dict:
        """添加一条系统提示词条目。"""
        now = self._utc_now()
        entry = UserSystemPromptEntry(
            prompt_id=self._generate_prompt_id(),
            user_id=user_id,
            content=content,
            created_at=now,
        )
        with Session(self.engine) as db:
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return {"prompt_id": entry.prompt_id, "content": entry.content, "created_at": entry.created_at.isoformat()}

    def delete_system_prompt_entry(self, *, prompt_id: str) -> bool:
        """删除一条系统提示词条目。"""
        with Session(self.engine) as db:
            entry = db.get(UserSystemPromptEntry, prompt_id)
            if entry is None:
                return False
            db.delete(entry)
            db.commit()
            return True

    def _list_entries(self, user_id: str) -> list[UserSystemPromptEntry]:
        with Session(self.engine) as db:
            statement = (
                select(UserSystemPromptEntry)
                .where(UserSystemPromptEntry.user_id == user_id)
                .order_by(UserSystemPromptEntry.created_at.asc())
            )
            return list(db.exec(statement).all())

    # ---- 自定义长期记忆 ----

    def list_memories(self, *, user_id: str) -> list[dict]:
        """列出用户的自定义长期记忆。"""
        records = self.memory_service.list_user_memories(
            user_id=user_id, memory_type="user_custom"
        )
        return [
            {
                "memory_id": r.memory_id,
                "content": r.content,
                "importance": r.importance,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

    def add_memory(self, *, user_id: str, content: str, importance: float = 0.5) -> dict:
        """添加一条用户自定义长期记忆,生成向量并写入向量库。"""
        provider = _get_shared_provider(self.config)
        vectors = provider.embed_texts([content])
        vector = vectors[0] if vectors else []

        memory_create = LongTermMemorySpecCreate(
            user_id=user_id,
            tag=self.config.constants.memory_tag,
            memory_type="user_custom",
            content=content,
            source_type="user_input",
            source_id=str(uuid4()),
            importance=importance,
            confidence=1.0,
            authority=0.8,
            embedding_model=self.config.model.embedding_model_name,
            embedding_vector_json=vector,
        )
        record = self.memory_service.create_memory(memory_create)
        return {
            "memory_id": record.memory_id,
            "content": record.content,
            "importance": record.importance,
            "created_at": record.created_at.isoformat(),
        }

    # ---- 用户 LLM 配置 ----

    def get_llm_config(self, *, user_id: str) -> dict:
        """获取用户自定义 LLM 配置，包含大模型和小模型两套。

        返回原始的 api_key（不脱敏），REST 端点应对 API Key 做脱敏处理。
        """
        with Session(self.engine) as db:
            config = db.get(UserLLMConfig, user_id.strip())
            if config is None:
                return {}
            return {
                "user_id": config.user_id,
                "api_key": config.api_key,
                "base_url": config.base_url,
                "model_name": config.model_name,
                "small_api_key": config.small_api_key,
                "small_base_url": config.small_base_url,
                "small_model_name": config.small_model_name,
                "updated_at": config.updated_at.isoformat(),
            }

    def save_llm_config(
        self,
        *,
        user_id: str,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        small_api_key: str | None = None,
        small_base_url: str | None = None,
        small_model_name: str | None = None,
    ) -> dict:
        """保存用户自定义 LLM 配置，包含大模型和小模型两套。"""
        normalized_user_id = user_id.strip()
        now = self._utc_now()
        with Session(self.engine) as db:
            config = db.get(UserLLMConfig, normalized_user_id)
            if config is None:
                config = UserLLMConfig(
                    user_id=normalized_user_id,
                    api_key=api_key or "",
                    base_url=base_url or "",
                    model_name=model_name or "",
                    small_api_key=small_api_key or "",
                    small_base_url=small_base_url or "",
                    small_model_name=small_model_name or "",
                    updated_at=now,
                )
            else:
                if api_key is not None:
                    config.api_key = api_key
                if base_url is not None:
                    config.base_url = base_url
                if model_name is not None:
                    config.model_name = model_name
                if small_api_key is not None:
                    config.small_api_key = small_api_key
                if small_base_url is not None:
                    config.small_base_url = small_base_url
                if small_model_name is not None:
                    config.small_model_name = small_model_name
                config.updated_at = now
            db.add(config)
            db.commit()
            db.refresh(config)
            return {
                "user_id": config.user_id,
                "api_key": config.api_key,
                "base_url": config.base_url,
                "model_name": config.model_name,
                "small_api_key": config.small_api_key,
                "small_base_url": config.small_base_url,
                "small_model_name": config.small_model_name,
                "updated_at": config.updated_at.isoformat(),
            }

    def remove_memory(self, *, memory_id: str) -> bool:
        """删除一条自定义长期记忆。"""
        return self.memory_service.delete_memory(memory_id=memory_id)

    # ---- 联网搜索配置 ----

    def get_web_search_config(self, *, user_id: str) -> dict:
        """获取用户的联网搜索配置（代理地址 + 开关状态）。"""
        normalized_user_id = user_id.strip()
        with Session(self.engine) as db:
            record = db.get(UserSettingsRecord, normalized_user_id)
            if record is None:
                return {"proxy_url": "", "web_search_enabled": False}
            return {
                "proxy_url": record.proxy_url,
                "web_search_enabled": record.web_search_enabled,
            }

    def save_web_search_config(
        self,
        *,
        user_id: str,
        proxy_url: str | None = None,
        web_search_enabled: bool | None = None,
    ) -> dict:
        """保存用户的联网搜索配置。"""
        normalized_user_id = user_id.strip()
        now = self._utc_now()
        with Session(self.engine) as db:
            record = db.get(UserSettingsRecord, normalized_user_id)
            if record is None:
                record = UserSettingsRecord(
                    user_id=normalized_user_id,
                    knowledge_dir=str(self.config.storage.knowledge_dir),
                    proxy_url=proxy_url or "",
                    web_search_enabled=web_search_enabled or False,
                    created_at=now,
                    updated_at=now,
                )
            else:
                if proxy_url is not None:
                    record.proxy_url = proxy_url
                if web_search_enabled is not None:
                    record.web_search_enabled = web_search_enabled
                record.updated_at = now
            db.add(record)
            db.commit()
            db.refresh(record)
            return {
                "proxy_url": record.proxy_url,
                "web_search_enabled": record.web_search_enabled,
            }
