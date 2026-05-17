"""
用户设置服务。

管理用户自定义系统提示词条目(数据库持久化)和用户自定义长期记忆(向量库持久化)。
系统提示词以条目形式存储，启动时全部加载并拼接注入到 agent 系统提示词。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Session, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.user_settings import UserSystemPromptEntry
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

    @staticmethod
    def _generate_prompt_id() -> str:
        return f"prompt_{uuid4().hex[:12]}"

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

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

    def remove_memory(self, *, memory_id: str) -> bool:
        """删除一条自定义长期记忆。"""
        return self.memory_service.delete_memory(memory_id=memory_id)
