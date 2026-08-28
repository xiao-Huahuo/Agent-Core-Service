"""
用户知识库重建服务。

功能说明:
本文件提供 editor/console/Agent 工具共享的知识库灌库函数。它根据用户设置档案中的
knowledge_dir 读取本地 Markdown/TXT 文件,先写入用户隔离的 frontmatter 目录,再切块、
Embedding 并写入长期记忆向量库。

使用说明:
service = KnowledgeLibraryService(config=config, memory_service=memory_service, settings_service=settings_service)
result = service.rebuild_user_knowledge(user_id="u1")
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



def _utcnow_naive() -> datetime:
    """Return a UTC datetime without tzinfo for legacy metadata compatibility."""

    return datetime.now(timezone.utc).replace(tzinfo=None)

from agent_service.core.agent_config import AgentConfig, DEFAULT_BUSINESS_LIMITS
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.memory.rag.pdf_cleaner import extract_pdf_text
from agent_service.services.settings.service import SettingsService
from agent_service.services.knowledge_graph import KnowledgeGraphService


class KnowledgeIgnoreMatcher:
    """知识库屏蔽规则匹配器,支持 gitignore 常用子集。"""

    def __init__(self, patterns_text: str) -> None:
        self.rules = self._parse(patterns_text)

    def is_ignored(self, relative_path: str, *, is_dir: bool = False) -> bool:
        """判断知识库相对路径是否被屏蔽。"""

        path = relative_path.replace("\\", "/").strip("/")
        if not path:
            return False
        parts = path.split("/")
        directory_parts = parts if is_dir else parts[:-1]
        if any(part.startswith(".") for part in directory_parts):
            return True
        ignored = False
        for negate, pattern, directory_only in self.rules:
            if directory_only and not (is_dir or "/" in path):
                # 文件仍可能被目录规则的父目录命中,下面会按前缀判断。
                pass
            if self._matches(pattern=pattern, directory_only=directory_only, path=path, parts=parts, is_dir=is_dir):
                ignored = not negate
        return ignored

    @classmethod
    def _parse(cls, patterns_text: str) -> list[tuple[bool, str, bool]]:
        rules: list[tuple[bool, str, bool]] = []
        for raw_line in patterns_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:].strip()
            line = line.replace("\\", "/").strip()
            directory_only = line.endswith("/")
            line = line.strip("/")
            if line:
                rules.append((negate, line, directory_only))
        return rules

    @staticmethod
    def _matches(*, pattern: str, directory_only: bool, path: str, parts: list[str], is_dir: bool) -> bool:
        if directory_only:
            return path == pattern or path.startswith(f"{pattern}/") or any(
                "/".join(parts[:index]) == pattern for index in range(1, len(parts) + 1)
            )
        if "/" in pattern:
            return fnmatch.fnmatchcase(path, pattern)
        return any(fnmatch.fnmatchcase(part, pattern) for part in parts) or fnmatch.fnmatchcase(path, pattern)


def _read_text_with_fallback(path: Path) -> str:
    """按常见编码读取文本预览文件,兼容 GBK/GB18030 CSV。"""

    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _open_text_with_fallback(path: Path) -> io.StringIO:
    """返回 StringIO,供 csv.reader 消费 fallback 解码后的文本。"""

    return io.StringIO(_read_text_with_fallback(path))


@dataclass(slots=True)
class KnowledgeLibraryRebuildResult:
    """
    用户知识库重建结果。

    user_id: 用户 ID。
    library_id: 当前重建的知识库配置 ID。
    knowledge_dir: 本次扫描的原始知识库目录。
    frontmatter_dir: 本次写入的结构化知识目录。
    frontmatter_files_seen: 原始文件扫描数量。
    frontmatter_files_written: 新写入或更新的结构化 JSON 数量。
    frontmatter_files_skipped: 未变化而跳过的结构化 JSON 数量。
    files_seen: 入库阶段扫描到的结构化 JSON 数量。
    files_ingested: 入库阶段实际写入向量库的文档数量。
    files_skipped: 入库阶段跳过的文档数量。
    chunks_created: 创建的知识 chunk 数量。
    chunks_deleted: 因源文件删除而清理的旧 chunk 数量。
    uploaded_path: 可选上传文件落盘路径。
    skip_reason: 单文件灌库跳过原因,用于前端区分屏蔽、不支持和无可入库文本。
    status_message: 可直接展示给用户的状态说明。
    """

    user_id: str
    library_id: str
    knowledge_dir: str
    frontmatter_dir: str
    frontmatter_files_seen: int
    frontmatter_files_written: int
    frontmatter_files_skipped: int
    files_seen: int
    files_ingested: int
    files_skipped: int
    chunks_created: int
    chunks_deleted: int
    uploaded_path: str = ""
    skip_reason: str = ""
    status_message: str = ""

    def to_dict(self) -> dict[str, int | str]:
        """转换为 REST/gRPC 可直接返回的字典。"""

        return {
            "user_id": self.user_id,
            "library_id": self.library_id,
            "knowledge_dir": self.knowledge_dir,
            "frontmatter_dir": self.frontmatter_dir,
            "frontmatter_files_seen": self.frontmatter_files_seen,
            "frontmatter_files_written": self.frontmatter_files_written,
            "frontmatter_files_skipped": self.frontmatter_files_skipped,
            "files_seen": self.files_seen,
            "files_ingested": self.files_ingested,
            "files_skipped": self.files_skipped,
            "chunks_created": self.chunks_created,
            "chunks_deleted": self.chunks_deleted,
            "uploaded_path": self.uploaded_path,
            "skip_reason": self.skip_reason,
            "status_message": self.status_message,
        }


from agent_service.services.knowledge_library.ingestion import KnowledgeIngestionMixin
from agent_service.services.knowledge_library.preview import KnowledgePreviewMixin
from agent_service.services.knowledge_library.search import KnowledgeSearchMixin
from agent_service.services.knowledge_library.trash import KnowledgeTrashMixin
from agent_service.services.knowledge_library.file_tree import KnowledgeFileTreeMixin

class KnowledgeLibraryService(KnowledgeIngestionMixin, KnowledgePreviewMixin, KnowledgeSearchMixin, KnowledgeTrashMixin, KnowledgeFileTreeMixin):
    """
    用户知识库灌库服务。

    config: 全局配置对象。
    memory_service: 长期记忆写入服务。
    settings_service: 用户设置服务。
    embedding_service: 可选 Embedding 服务,测试或复用时注入。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        memory_service: LongTermMemoryService,
        settings_service: SettingsService,
        embedding_service: EmbeddingService | None = None,
        knowledge_graph_service: KnowledgeGraphService | None = None,
    ) -> None:
        """保存依赖服务。"""

        self.config = config
        self.limits = getattr(config, "limits", DEFAULT_BUSINESS_LIMITS)
        self.memory_service = memory_service
        self.settings_service = settings_service
        self.embedding_service = embedding_service
        self.knowledge_graph_service = knowledge_graph_service or KnowledgeGraphService(config=config)

    @property
    def supported_suffixes(self) -> set[str]:
        """
        可灌库文件后缀白名单,从 AgentConfig.constants.knowledge_supported_suffixes 读取。
        如需添加 .pdf/.py/.json 等新格式,修改配置即可;如需多模态分支处理(如 PDF 解析),
        请同步修改 frontmatter_bootstrap._iter_source_files 和 knowledge_ingestion 管线。
        """
        return set(self.config.constants.knowledge_supported_suffixes)





























































































