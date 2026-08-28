"""KnowledgeGraphService 的 rebuild 职责。

方法体由原服务机械迁移，业务行为不变。
"""

from __future__ import annotations
import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol
from langchain_core.messages import HumanMessage, SystemMessage
import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.core.db.engine import get_database_engine
from agent_service.models.knowledge_graph import (
    KnowledgeGraphDocumentStatus,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)
from agent_service.models.session import utc_now
from agent_service.services.memory.rag.frontmatter_document import (
    StructuredKnowledgeDocument,
    StructuredKnowledgeSection,
)
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.scheduler import (
    BACKGROUND_FACT_RESOLUTION_TASK,
    LLMTaskScheduler,
    SMALL_MODEL_TIER,
    get_llm_task_scheduler,
)
from agent_service.services.token_usage.service import TokenUsageService
from agent_service.services.knowledge_graph.service import (
    EntityCandidate, GraphExtractionResult, KnowledgeGraphExtractor,
    RelationCandidate, StructuredKnowledgeDocument, StructuredKnowledgeSection,
)

class KnowledgeGraphRebuildMixin:
    def extract_frontmatter_dir(
        self,
        *,
        user_id: str,
        library_id: str,
        frontmatter_dir: Path,
        keep_document_ids: set[str] | None = None,
        llm_config: dict[str, Any] | None = None,
    ) -> GraphExtractionResult:
        """扫描 frontmatter 目录并抽取知识图谱。"""

        result = GraphExtractionResult()
        paths = sorted(path for path in frontmatter_dir.rglob("*.json") if path.is_file()) if frontmatter_dir.exists() else []
        self.sync_document_nodes_frontmatter_dir(
            user_id=user_id,
            library_id=library_id,
            frontmatter_dir=frontmatter_dir,
            keep_document_ids=keep_document_ids,
        )
        for path in paths:
            result.files_seen += 1
            document = self._load_document(path)
            result.document_ids_seen.add(document.document_id)
            item_result = self.extract_document(
                user_id=user_id,
                library_id=library_id,
                document=document,
                llm_config=llm_config,
            )
            result.files_extracted += item_result.files_extracted
            result.files_skipped += item_result.files_skipped
            result.files_failed += item_result.files_failed
            result.entities_written += item_result.entities_written
            result.relations_written += item_result.relations_written
        self.delete_graph_except_documents(
            user_id=user_id,
            library_id=library_id,
            keep_document_ids=keep_document_ids if keep_document_ids is not None else result.document_ids_seen,
        )
        return result
    def sync_document_nodes_frontmatter_dir(
        self,
        *,
        user_id: str,
        library_id: str,
        frontmatter_dir: Path,
        keep_document_ids: set[str] | None = None,
    ) -> int:
        """Synchronize source document nodes without invoking semantic extraction."""

        paths = sorted(path for path in frontmatter_dir.rglob("*.json") if path.is_file()) if frontmatter_dir.exists() else []
        document_ids: set[str] = set()
        synced = 0
        for path in paths:
            document = self._load_document(path)
            document_ids.add(document.document_id)
            self._write_document_node(user_id=user_id, library_id=library_id, document=document)
            synced += 1
        self.delete_graph_except_documents(
            user_id=user_id,
            library_id=library_id,
            keep_document_ids=keep_document_ids if keep_document_ids is not None else document_ids,
        )
        return synced
    def extract_frontmatter_file(
        self,
        *,
        user_id: str,
        library_id: str,
        frontmatter_path: Path,
        llm_config: dict[str, Any] | None = None,
    ) -> GraphExtractionResult:
        """抽取单个 frontmatter 文件的知识图谱。"""

        document = self._load_document(frontmatter_path)
        return self.extract_document(
            user_id=user_id,
            library_id=library_id,
            document=document,
            llm_config=llm_config,
        )
