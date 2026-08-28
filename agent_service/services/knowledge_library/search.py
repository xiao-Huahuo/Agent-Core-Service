"""KnowledgeLibraryService 的 search 职责。

方法体由原服务机械迁移，业务行为不变。
"""

from __future__ import annotations

import base64
import csv
import fnmatch
import hashlib
import html
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import stat
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

logger = logging.getLogger(__name__)



from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.memory.rag.pdf_cleaner import extract_pdf_text
from agent_service.services.settings.service import SettingsService
from agent_service.services.knowledge_graph import KnowledgeGraphService

from agent_service.services.knowledge_library.service import (
    KnowledgeIgnoreMatcher, KnowledgeLibraryRebuildResult, _open_text_with_fallback,
    _read_text_with_fallback, _utcnow_naive,
)

class KnowledgeSearchMixin:
    def search_file_contents(self, *, user_id: str, query: str, limit: int | None = None) -> list[dict[str, str]]:
        """
        直接扫描当前 active 知识库中的文本文件内容。

        user_id: 用户 ID。
        query: 需要匹配的文本。
        limit: 最多返回多少个文件结果。
        """

        root = self._get_active_root(user_id=user_id)
        if not root.exists():
            return []
        needle = query.strip().lower()
        limit = limit or self.limits.knowledge_content_search_limit
        if not needle:
            return []
        results: list[dict[str, str]] = []
        for path in sorted(root.rglob("*"), key=self._sort_path):
            if len(results) >= limit:
                break
            if self._is_mw_managed_path(path=path, root=root):
                continue
            if not path.is_file() or path.suffix.lower() not in self.supported_suffixes:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            position = content.lower().find(needle)
            if position < 0:
                continue
            snippet = self._build_search_snippet(content=content, position=position, query_length=len(query.strip()))
            results.append({"source_uri": str(path), "snippet": snippet})
        return results
    @staticmethod
    def _build_search_snippet(*, content: str, position: int, query_length: int) -> str:
        """
        根据匹配位置生成搜索结果片段。

        content: 完整文件内容。
        position: 命中的起始位置。
        query_length: 查询文本长度。
        """

        content_len = len(content)
        start = max(0, position - 80)
        end = min(content_len, position + query_length + 80)
        snippet = content[start:end]
        if start > 0:
            snippet = f"...{snippet}"
        if end < content_len:
            snippet = f"{snippet}..."
        return snippet
