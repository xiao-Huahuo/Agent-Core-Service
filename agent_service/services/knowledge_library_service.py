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
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.image_ocr import ImageOcrService
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.memory.rag.pdf_cleaner import extract_pdf_text
from agent_service.services.settings_service import SettingsService
from agent_service.services.knowledge_graph_service import KnowledgeGraphService


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


class KnowledgeLibraryService:
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

    def rebuild_user_knowledge(
        self,
        *,
        user_id: str,
        knowledge_dir: str | None = None,
        uploaded_path: str = "",
    ) -> KnowledgeLibraryRebuildResult:
        """
        重新扫描用户知识库并写入向量库。

        user_id: 用户 ID。
        knowledge_dir: 可选新知识库目录;传入时先写入用户设置。
        uploaded_path: 可选上传文件路径,仅用于 API 返回。
        """

        if knowledge_dir is not None:
            profile = self.settings_service.update_knowledge_dir(user_id=user_id, knowledge_dir=knowledge_dir)
        else:
            profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        knowledge_owner_id = self.settings_service.build_knowledge_owner_id(
            user_id=normalized_user_id,
            library_id=library_id,
        )
        source_root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        source_root.mkdir(parents=True, exist_ok=True)
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id)
        frontmatter_root.mkdir(parents=True, exist_ok=True)
        ignore_matcher = self._build_ignore_matcher(user_id=normalized_user_id)

        ocr_enabled = self.settings_service.is_ocr_enabled_for_user(user_id=normalized_user_id)
        frontmatter_result = FrontmatterBootstrapService(config=self.config, ocr_enabled=ocr_enabled).build_frontmatter_dir(
            knowledge_dir=source_root,
            frontmatter_dir=frontmatter_root,
            supported_suffixes=self.supported_suffixes,
            exclude_path=lambda path: ignore_matcher.is_ignored(
                self._relative_path(path=path, root=source_root),
                is_dir=False,
            ),
        )
        self._delete_ignored_frontmatter_files(
            frontmatter_root=frontmatter_root,
            ignore_matcher=ignore_matcher,
        )
        ingestion_service = KnowledgeIngestionService(
            config=self.config,
            embedding_service=self.embedding_service,
            memory_service=self.memory_service,
        )
        ingestion_result = ingestion_service.ingest_frontmatter_dir(
            frontmatter_dir=frontmatter_root,
            user_id=knowledge_owner_id,
        )
        chunks_deleted = self.memory_service.delete_memories_except_sources(
            user_id=knowledge_owner_id,
            tag=self.config.constants.knowledge_tag,
            memory_type="knowledge_chunk",
            keep_source_ids=ingestion_result.source_ids_seen or set(),
        )
        return KnowledgeLibraryRebuildResult(
            user_id=normalized_user_id,
            library_id=library_id,
            knowledge_dir=str(source_root),
            frontmatter_dir=str(frontmatter_root),
            frontmatter_files_seen=frontmatter_result.files_seen,
            frontmatter_files_written=frontmatter_result.files_written,
            frontmatter_files_skipped=frontmatter_result.files_skipped,
            files_seen=ingestion_result.files_seen,
            files_ingested=ingestion_result.files_ingested,
            files_skipped=ingestion_result.files_skipped,
            chunks_created=ingestion_result.chunks_created,
            chunks_deleted=chunks_deleted,
            uploaded_path=uploaded_path,
        )

    def build_upload_only_result(self, *, user_id: str, uploaded_path: str) -> KnowledgeLibraryRebuildResult:
        """构造“仅上传不灌库”的统一返回。"""

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        source_root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id)
        return KnowledgeLibraryRebuildResult(
            user_id=normalized_user_id,
            library_id=library_id,
            knowledge_dir=str(source_root),
            frontmatter_dir=str(frontmatter_root),
            frontmatter_files_seen=0,
            frontmatter_files_written=0,
            frontmatter_files_skipped=0,
            files_seen=0,
            files_ingested=0,
            files_skipped=0,
            chunks_created=0,
            chunks_deleted=0,
            uploaded_path=uploaded_path,
        )

    def should_auto_ingest_on_upload(self, *, user_id: str) -> bool:
        """返回用户上传后是否自动灌库。默认关闭。"""

        config = self.settings_service.get_knowledge_ingestion_config(user_id=user_id)
        return bool(config.get("auto_ingest_on_upload"))

    def cleanup_ignored_sources(self, *, user_id: str) -> dict[str, int]:
        """按当前屏蔽规则立即删除已入库的屏蔽文件切片和 frontmatter。"""

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        source_root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id)
        ignore_matcher = self._build_ignore_matcher(user_id=normalized_user_id)
        ignored_paths = [
            self._relative_path(path=path, root=source_root)
            for path in source_root.rglob("*")
            if path.is_file() and ignore_matcher.is_ignored(self._relative_path(path=path, root=source_root), is_dir=False)
        ] if source_root.exists() else []
        chunks_deleted = self._delete_index_artifacts(user_id=normalized_user_id, relative_paths=ignored_paths)
        self._delete_ignored_frontmatter_files(
            frontmatter_root=frontmatter_root,
            ignore_matcher=ignore_matcher,
        )
        return {"files_seen": len(ignored_paths), "chunks_deleted": chunks_deleted}

    def ingest_single_file(self, *, user_id: str, path: str) -> KnowledgeLibraryRebuildResult:
        """
        只灌库当前 active 知识库中的单个文件。

        path: 知识库根目录内相对路径。该操作不会清理其他文件对应的向量切片。
        """

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        knowledge_owner_id = self.settings_service.build_knowledge_owner_id(
            user_id=normalized_user_id,
            library_id=library_id,
        )
        source_root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        source_path = self._resolve_child_path(root=source_root, relative_path=path)
        if not source_path.is_file():
            raise ValueError("file not found")
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id)
        frontmatter_root.mkdir(parents=True, exist_ok=True)
        relative_path = self._relative_path(path=source_path, root=source_root)
        source_id = FrontmatterBootstrapService._build_document_id(Path(relative_path))
        ignore_matcher = self._build_ignore_matcher(user_id=normalized_user_id)
        if ignore_matcher.is_ignored(relative_path, is_dir=False):
            frontmatter_path = (frontmatter_root / relative_path).with_suffix(".json").resolve()
            if self._is_relative_to(frontmatter_path, frontmatter_root) and frontmatter_path.exists():
                frontmatter_path.unlink()
            chunks_deleted = self.memory_service.delete_memories_for_source(
                user_id=knowledge_owner_id,
                tag=self.config.constants.knowledge_tag,
                memory_type="knowledge_chunk",
                source_id=source_id,
            )
            return KnowledgeLibraryRebuildResult(
                user_id=normalized_user_id,
                library_id=library_id,
                knowledge_dir=str(source_root),
                frontmatter_dir=str(frontmatter_root),
                frontmatter_files_seen=1,
                frontmatter_files_written=0,
                frontmatter_files_skipped=1,
                files_seen=1,
                files_ingested=0,
                files_skipped=1,
                chunks_created=0,
                chunks_deleted=chunks_deleted,
                uploaded_path=str(source_path),
                skip_reason="ignored",
                status_message="文件命中知识库屏蔽规则,已跳过并清理旧索引。",
            )
        if source_path.suffix.lower() not in self.supported_suffixes:
            return KnowledgeLibraryRebuildResult(
                user_id=normalized_user_id,
                library_id=library_id,
                knowledge_dir=str(source_root),
                frontmatter_dir=str(frontmatter_root),
                frontmatter_files_seen=1,
                frontmatter_files_written=0,
                frontmatter_files_skipped=1,
                files_seen=1,
                files_ingested=0,
                files_skipped=1,
                chunks_created=0,
                chunks_deleted=0,
                uploaded_path=str(source_path),
                skip_reason="unsupported_suffix",
                status_message=f"当前后缀 {source_path.suffix.lower()} 不在知识库入库白名单中。",
            )

        ocr_enabled = self.settings_service.is_ocr_enabled_for_user(user_id=normalized_user_id)
        frontmatter_result, frontmatter_path = FrontmatterBootstrapService(config=self.config, ocr_enabled=ocr_enabled).build_frontmatter_file(
            source_path=source_path,
            knowledge_dir=source_root,
            frontmatter_dir=frontmatter_root,
            supported_suffixes=self.supported_suffixes,
        )
        ingestion_result = KnowledgeIngestionService(
            config=self.config,
            embedding_service=self.embedding_service,
            memory_service=self.memory_service,
        ).ingest_frontmatter_file(
            frontmatter_path=frontmatter_path,
            user_id=knowledge_owner_id,
        )
        skip_reason, status_message = self._describe_single_file_ingestion_result(
            source_path=source_path,
            frontmatter_path=frontmatter_path,
            files_ingested=ingestion_result.files_ingested,
            chunks_created=ingestion_result.chunks_created,
        )
        if skip_reason:
            logger.warning(
                "单文件灌库未生成切片 | path=%s suffix=%s reason=%s message=%s",
                relative_path,
                source_path.suffix.lower(),
                skip_reason,
                status_message,
            )
        return KnowledgeLibraryRebuildResult(
            user_id=normalized_user_id,
            library_id=library_id,
            knowledge_dir=str(source_root),
            frontmatter_dir=str(frontmatter_root),
            frontmatter_files_seen=frontmatter_result.files_seen,
            frontmatter_files_written=frontmatter_result.files_written,
            frontmatter_files_skipped=frontmatter_result.files_skipped,
            files_seen=ingestion_result.files_seen,
            files_ingested=ingestion_result.files_ingested,
            files_skipped=ingestion_result.files_skipped,
            chunks_created=ingestion_result.chunks_created,
            chunks_deleted=ingestion_result.chunks_deleted,
            uploaded_path=str(source_path),
            skip_reason=skip_reason,
            status_message=status_message,
        )

    def ingest_path(self, *, user_id: str, path: str) -> KnowledgeLibraryRebuildResult:
        """
        灌库文件或文件夹。文件直接灌库,文件夹递归灌入其下所有支持的文件。

        path: 知识库根目录内相对路径。
        """

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        source_root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        source_path = self._resolve_child_path(root=source_root, relative_path=path)
        if not source_path.exists():
            raise ValueError("path not found")
        if source_path.is_file():
            return self.ingest_single_file(user_id=user_id, path=path)
        supported = self.supported_suffixes
        file_paths = sorted(
            p for p in source_path.rglob("*") if p.is_file() and p.suffix.lower() in supported
        )
        if not file_paths:
            return KnowledgeLibraryRebuildResult(
                user_id=normalized_user_id,
                library_id=library_id,
                knowledge_dir=str(source_root),
                frontmatter_dir=str(self._resolve_user_frontmatter_dir(normalized_user_id, library_id)),
                frontmatter_files_seen=0,
                frontmatter_files_written=0,
                frontmatter_files_skipped=0,
                files_seen=0,
                files_ingested=0,
                files_skipped=0,
                chunks_created=0,
                chunks_deleted=0,
                uploaded_path=str(source_path),
                skip_reason="no_supported_files",
                status_message="该文件夹中没有可灌库的知识文件。",
            )
        agg = KnowledgeLibraryRebuildResult(
            user_id=normalized_user_id,
            library_id=library_id,
            knowledge_dir=str(source_root),
            frontmatter_dir=str(self._resolve_user_frontmatter_dir(normalized_user_id, library_id)),
            frontmatter_files_seen=0,
            frontmatter_files_written=0,
            frontmatter_files_skipped=0,
            files_seen=0,
            files_ingested=0,
            files_skipped=0,
            chunks_created=0,
            chunks_deleted=0,
        )
        for fp in file_paths:
            relative = self._relative_path(path=fp, root=source_root)
            try:
                result = self.ingest_single_file(user_id=user_id, path=relative)
                agg.frontmatter_files_seen += result.frontmatter_files_seen
                agg.frontmatter_files_written += result.frontmatter_files_written
                agg.frontmatter_files_skipped += result.frontmatter_files_skipped
                agg.files_seen += result.files_seen
                agg.files_ingested += result.files_ingested
                agg.files_skipped += result.files_skipped
                agg.chunks_created += result.chunks_created
                agg.chunks_deleted += result.chunks_deleted
            except Exception:
                logger.exception("灌库文件失败 | path=%s", relative)
                agg.files_skipped += 1
        agg.status_message = f"文件夹灌库完成,共 {agg.files_ingested} 个文件入库,{agg.chunks_created} 个切片。"
        return agg

    def _describe_single_file_ingestion_result(
        self,
        *,
        source_path: Path,
        frontmatter_path: Path,
        files_ingested: int,
        chunks_created: int,
    ) -> tuple[str, str]:
        """根据单文件 frontmatter 和入库统计生成跳过原因。"""

        if files_ingested > 0:
            return "", ""
        try:
            payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "no_chunks", "文件已结构化,但没有生成可入库切片。"
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        if source_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            ocr_status = str(metadata.get("ocr_status") or "")
            if ocr_status == "no_text":
                return "ocr_no_text", "图片已处理,但 OCR 未识别到可入库文字。"
            if ocr_status == "engine_unavailable":
                return "ocr_engine_unavailable", "图片需要 OCR,但当前 OCR 引擎不可用。"
            if ocr_status == "disabled":
                return "ocr_disabled", "图片需要 OCR,但当前用户未启用 OCR。"
            if chunks_created <= 0:
                return "ocr_no_chunks", "图片已 OCR,但识别结果没有形成可入库切片。"
        if chunks_created <= 0:
            return "no_chunks", "文件已处理,但没有生成可入库文本切片。"
        return "", ""

    def write_uploaded_file(
        self,
        *,
        user_id: str,
        filename: str,
        content: bytes,
        relative_dir: str = "",
        conflict_strategy: str = "overwrite",
    ) -> Path:
        """
        将前端上传的文件写入用户知识库目录。

        user_id: 用户 ID。
        filename: 上传文件名。
        content: 文件二进制内容。
        relative_dir: 可选目标子目录,必须位于知识库根目录内。
        conflict_strategy: 同名冲突策略,支持 overwrite / skip / rename。
        """

        active_library = self.settings_service.get_active_knowledge_library(user_id=user_id)
        root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        safe_filename = Path(filename).name.strip()
        if not safe_filename:
            raise ValueError("filename is required")
        target_dir = self._resolve_child_dir(root=root, relative_dir=relative_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = (target_dir / safe_filename).resolve()
        if not self._is_relative_to(target_path, root):
            raise ValueError("upload path escapes knowledge_dir")
        normalized_strategy = conflict_strategy.strip().lower()
        if normalized_strategy not in {"overwrite", "skip", "rename"}:
            raise ValueError("invalid conflict_strategy")
        if target_path.exists():
            if normalized_strategy == "skip":
                return target_path
            if normalized_strategy == "rename":
                target_path = self._unique_child_path(target_dir=target_dir, preferred_name=safe_filename)
        target_path.write_bytes(content)
        return target_path

    def list_files(self, *, user_id: str) -> list[dict]:
        """
        列出当前 active 知识库的递归文件树。

        user_id: 用户 ID。
        """

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        knowledge_owner_id = self.settings_service.build_knowledge_owner_id(
            user_id=normalized_user_id,
            library_id=library_id,
        )
        root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        ignore_matcher = self._build_ignore_matcher(user_id=normalized_user_id)
        ocr_enabled = self.settings_service.is_ocr_enabled_for_user(user_id=normalized_user_id)
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id).resolve()
        indexed_source_ids = self.memory_service.list_source_ids(
            user_id=knowledge_owner_id,
            tag=self.config.constants.knowledge_tag,
            memory_type="knowledge_chunk",
        )
        source_updated_at = self.memory_service.list_source_updated_at(
            user_id=knowledge_owner_id,
            tag=self.config.constants.knowledge_tag,
            memory_type="knowledge_chunk",
        )
        return [
            self._path_to_node(
                path=path,
                root=root,
                ignore_matcher=ignore_matcher,
                indexed_source_ids=indexed_source_ids,
                source_updated_at=source_updated_at,
                frontmatter_root=frontmatter_root,
                ocr_enabled=ocr_enabled,
            )
            for path in sorted(root.iterdir(), key=self._sort_path)
        ]

    def get_active_root_path(self, *, user_id: str) -> Path:
        """
        返回当前 active 知识库根目录并确保目录存在。

        user_id: 用户 ID。
        """

        root = self._get_active_root(user_id=user_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def read_multimodal_file_info(self, *, user_id: str, path: str) -> dict:
        """
        Read the already-ingested frontmatter JSON for a multimodal source file.
        user_id: Current user id.
        path: Source file path relative to the active knowledge library root.
        """

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        source_path = self._resolve_child_path(root=root, relative_path=path)
        if not source_path.is_file():
            raise ValueError("source file not found in active knowledge library")

        relative_path = self._relative_path(path=source_path, root=root)
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id).resolve()
        frontmatter_path = (frontmatter_root / relative_path).with_suffix(".json").resolve()
        if not self._is_relative_to(frontmatter_path, frontmatter_root):
            raise ValueError("frontmatter path escapes user library")
        if not frontmatter_path.is_file():
            raise ValueError("frontmatter json not found; refresh or ingest this file first")

        payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        sections = payload.get("sections", [])
        return {
            "path": relative_path,
            "frontmatter_path": str(frontmatter_path),
            "title": payload.get("title", ""),
            "source_type": payload.get("source_type", ""),
            "source_uri": payload.get("source_uri", ""),
            "source_hash": payload.get("source_hash", ""),
            "summary": payload.get("summary", ""),
            "tags": payload.get("tags", []),
            "metadata": payload.get("metadata", {}),
            "section_count": len(sections) if isinstance(sections, list) else 0,
            "sections": [
                {
                    "section_id": section.get("section_id", ""),
                    "heading": section.get("heading", ""),
                    "title_path": section.get("title_path", []),
                    "content_preview": str(section.get("content", ""))[:800],
                }
                for section in sections[:20]
                if isinstance(section, dict)
            ],
        }

    def read_file(self, *, user_id: str, path: str) -> dict:
        """
        读取当前 active 知识库中的文本文件。

        user_id: 用户 ID。
        path: 知识库根目录内的相对文件路径。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if not target.is_file():
            raise ValueError("file not found")
        return {
            "path": self._relative_path(path=target, root=root),
            "content": target.read_text(encoding="utf-8"),
            "mtime": self._format_mtime(target),
            "size": target.stat().st_size,
        }

    def preview_file(self, *, user_id: str, path: str) -> dict:
        """
        为 editor 多模态查看器生成只读预览数据。

        user_id: 用户 ID。
        path: 知识库根目录内的相对文件路径。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if not target.is_file():
            raise ValueError("file not found")

        suffix = target.suffix.lower()
        base_payload = {
            "path": self._relative_path(path=target, root=root),
            "mtime": self._format_mtime(target),
            "size": target.stat().st_size,
            "extension": suffix,
        }
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
            mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            image_preview = self._preview_image_ocr(user_id=user_id, path=target)
            return {
                **base_payload,
                "kind": "image",
                "mime_type": mime_type,
                "data_url": self._file_data_url(path=target, mime_type=mime_type),
                **image_preview,
                "readonly": True,
            }
        if suffix == ".pdf":
            pdf_preview = self._preview_pdf(path=target)
            return {
                **base_payload,
                **pdf_preview,
                "kind": "pdf",
                "mime_type": "application/pdf",
                "raw_url": self._raw_file_url(user_id=user_id, relative_path=str(base_payload["path"])),
                "readonly": True,
            }
        if suffix in {".csv", ".tsv"}:
            return {
                **base_payload,
                "kind": "table",
                "sheets": [self._preview_delimited_table(path=target, delimiter="\t" if suffix == ".tsv" else ",")],
                "readonly": True,
            }
        if suffix == ".xlsx":
            return {
                **base_payload,
                "kind": "table",
                "sheets": self._preview_xlsx(path=target),
                "readonly": True,
            }
        if suffix in {".ppt", ".pptx"}:
            # Try to convert PPTX → PDF for native iframe preview
            if suffix == ".pptx":
                pdf_output = target.with_name(target.name + ".pdf")
                if self._can_generate_pptx_pdf():
                    if not pdf_output.exists() or pdf_output.stat().st_mtime < target.stat().st_mtime:
                        try:
                            self._generate_pdf_from_pptx(path=target, output_path=pdf_output)
                        except Exception as exc:
                            logger.warning("PPTX→PDF generation failed: %s", exc)
                    if pdf_output.exists():
                        pdf_preview = self._preview_pdf(path=pdf_output)
                        # Merge parsed PPTX text content into the PDF preview
                        # so Edit mode shows readable text, not empty scanned metadata.
                        pptx_content = self._preview_pptx(path=target).get("content", "")
                        return {
                            **base_payload,
                            **pdf_preview,
                            "content": pptx_content,
                            "kind": "pdf",
                            "mime_type": "application/pdf",
                            "raw_url": self._raw_file_url(user_id=user_id, relative_path=str(base_payload["path"]) + ".pdf"),
                            "readonly": True,
                        }
            # Fallback: HTML-based preview
            return {
                **base_payload,
                **self._preview_pptx(path=target),
                "kind": "document",
                "readonly": True,
            }
        if suffix == ".docx":
            return {
                **base_payload,
                "kind": "document",
                "html": self._preview_docx_html(path=target),
                "readonly": True,
            }
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {
                **base_payload,
                "kind": "unsupported",
                "message": "当前文件不是 UTF-8 文本,也没有可用的多模态预览器。",
                "readonly": True,
            }
        return {
            **base_payload,
            "kind": "text",
            "content": content,
            "readonly": False,
        }

    def search_file_contents(self, *, user_id: str, query: str, limit: int = 20) -> list[dict[str, str]]:
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
        if not needle:
            return []
        results: list[dict[str, str]] = []
        for path in sorted(root.rglob("*"), key=self._sort_path):
            if len(results) >= limit:
                break
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
    def _resolve_raw_mime_type(path: Path) -> str:
        """解析原始文件正确的 MIME 类型,特别处理 Office 格式。"""
        OFFICE_MIME_TYPES: dict[str, str] = {
            ".pdf": "application/pdf",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        suffix = path.suffix.lower()
        if suffix in OFFICE_MIME_TYPES:
            return OFFICE_MIME_TYPES[suffix]
        return mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    def resolve_file_for_raw_response(self, *, user_id: str, path: str) -> tuple[Path, str]:
        """
        解析可供浏览器预览的原始文件响应路径。

        user_id: 用户 ID。
        path: 知识库根目录内的相对文件路径。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if not target.is_file():
            raise ValueError("file not found")
        mime_type = self._resolve_raw_mime_type(target)
        return target, mime_type

    @staticmethod
    def _file_data_url(*, path: Path, mime_type: str) -> str:
        """把图片/PDF 文件编码为浏览器可直接使用的 data URL。"""

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _raw_file_url(*, user_id: str, relative_path: str) -> str:
        """构造同源 raw 文件预览 URL,由前端按 API origin 补全。"""

        return f"/knowledge/files/raw?user_id={quote(user_id)}&path={quote(relative_path)}"

    @staticmethod
    def _preview_delimited_table(*, path: Path, delimiter: str) -> dict:
        """读取 CSV/TSV 的前若干行用于表格预览。"""

        rows: list[list[str]] = []
        with _open_text_with_fallback(path) as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            for index, row in enumerate(reader):
                if index >= 200:
                    break
                rows.append([cell.strip() for cell in row])
        return {"name": path.stem, "rows": rows}

    @classmethod
    def _preview_xlsx(cls, *, path: Path) -> list[dict]:
        """从 XLSX OOXML 中读取工作表前若干行用于表格预览。"""

        sheets: list[dict] = []
        with zipfile.ZipFile(path) as archive:
            shared_strings = cls._read_xlsx_shared_strings(archive)
            sheet_paths = sorted(
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            for index, sheet_path in enumerate(sheet_paths, start=1):
                rows = cls._extract_xlsx_rows(archive=archive, sheet_path=sheet_path, shared_strings=shared_strings)
                sheets.append({"name": f"Sheet {index}", "rows": rows})
        return sheets

    @staticmethod
    def _preview_docx_html(*, path: Path) -> str:
        """优先使用 mammoth 转换 DOCX,依赖缺失时回退到 OOXML 段落抽取。"""

        try:
            import mammoth  # type: ignore[import-untyped]

            with path.open("rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
            return str(result.value or "")
        except Exception:
            paragraphs: list[str] = []
            with zipfile.ZipFile(path) as archive:
                try:
                    xml_text = archive.read("word/document.xml").decode("utf-8", errors="ignore")
                except KeyError:
                    return "<p>无法读取 DOCX 正文。</p>"
            root = ElementTree.fromstring(xml_text)
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] != "p":
                    continue
                text = " ".join(part.strip() for part in node.itertext() if part.strip())
                if text:
                    paragraphs.append(f"<p>{html.escape(text)}</p>")
            return "\n".join(paragraphs) or "<p>DOCX 中没有可预览文本。</p>"

    @staticmethod
    def _can_generate_pptx_pdf() -> bool:
        """检查是否可用内建渲染引擎生成 PPTX PDF 预览。需要 Pillow 和可用中文字体。"""
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            return False
        return not not KnowledgeLibraryService._find_cjk_font_path()

    @staticmethod
    def _find_cjk_font_path() -> str | None:
        """查找系统中可用的中文字体路径。"""
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/simsunb.ttf",
            "C:/Windows/Fonts/SimsunExtG.ttf",
            "C:/Windows/Fonts/yahei.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        return None

    @staticmethod
    def _generate_pdf_from_pptx(*, path: Path, output_path: Path) -> None:
        """用 Pillow 渲染每个幻灯片为图像页并生成多页 PDF,无需外部依赖。"""
        from PIL import Image, ImageDraw, ImageFont

        ns = {
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        }

        slides: list[dict] = []
        with zipfile.ZipFile(path) as archive:
            slide_paths = sorted(
                name for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            if not slide_paths:
                raise ValueError("no slides found")

            for slide_index, slide_path in enumerate(slide_paths, start=1):
                xml_text = archive.read(slide_path).decode("utf-8", errors="ignore")
                slide_root = ElementTree.fromstring(xml_text)

                text_parts: list[str] = []
                for text_elem in slide_root.iter(f"{{{ns['a']}}}t"):
                    if text_elem.text:
                        text_parts.append(text_elem.text.strip())
                slide_text = "\n".join(part for part in text_parts if part)

                rels_path = f"ppt/slides/_rels/{Path(slide_path).name}.rels"
                rels_map: dict[str, str] = {}
                try:
                    rels_xml = archive.read(rels_path).decode("utf-8", errors="ignore")
                    rels_root = ElementTree.fromstring(rels_xml)
                    for rel in rels_root:
                        rid = rel.get("Id", "")
                        target = rel.get("Target", "")
                        if rid and target and "image" in str(rel.get("Type", "")):
                            media_path = str(Path("ppt/slides") / target).replace("\\", "/")
                            rels_map[rid] = media_path
                except KeyError:
                    pass

                slide_images: list[bytes] = []
                for blip in slide_root.iter(f"{{{ns['a']}}}blip"):
                    rid = blip.get(f"{{{ns['r']}}}embed") or blip.get(f"{{{ns['r']}}}link") or ""
                    media_path = rels_map.get(rid)
                    if media_path and media_path in archive.namelist():
                        slide_images.append(archive.read(media_path))

                slides.append({"text": slide_text, "images": slide_images, "index": slide_index})

        # Render each slide as a Pillow image page
        font_path = KnowledgeLibraryService._find_cjk_font_path()
        page_w, page_h = 1280, 720  # 16:9
        margin = 48
        title_size, body_size = 36, 22
        title_font = ImageFont.truetype(font_path, title_size) if font_path else ImageFont.load_default()
        body_font = ImageFont.truetype(font_path, body_size) if font_path else ImageFont.load_default()

        pages: list[Image.Image] = []
        for slide in slides:
            img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            y = margin

            # Slide title
            draw.text((margin, y), f"Slide {slide['index']}", font=title_font, fill=(80, 80, 80))
            y += 60

            # Text lines
            if slide["text"]:
                for line in slide["text"].split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Manual line wrapping for long text
                    while len(line) > 0:
                        bbox = draw.textbbox((0, 0), line[:100], font=body_font)
                        avail_w = page_w - 2 * margin
                        # Binary search for the longest substring that fits
                        if bbox[2] - bbox[0] > avail_w:
                            lo, hi = 1, min(len(line), 80)
                            while lo < hi:
                                mid = (lo + hi + 1) // 2
                                b = draw.textbbox((0, 0), line[:mid], font=body_font)
                                if b[2] - b[0] <= avail_w:
                                    lo = mid
                                else:
                                    hi = mid - 1
                            wrapped = line[:lo]
                            line = line[lo:]
                        else:
                            wrapped = line
                            line = ""
                        draw.text((margin, y), wrapped, font=body_font, fill=(30, 30, 30))
                        y += body_size + 6
                        if y > page_h - margin:
                            y = margin
                            pages.append(img)
                            img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
                            draw = ImageDraw.Draw(img)

            # Embedded images
            for img_bytes in slide["images"]:
                if y > page_h - 200:
                    pages.append(img)
                    img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
                    draw = ImageDraw.Draw(img)
                    y = margin
                try:
                    slide_img = Image.open(io.BytesIO(img_bytes))
                    max_img_w = page_w - 2 * margin
                    max_img_h = 400
                    if slide_img.width > max_img_w or slide_img.height > max_img_h:
                        ratio = min(max_img_w / slide_img.width, max_img_h / slide_img.height)
                        slide_img = slide_img.resize(
                            (int(slide_img.width * ratio), int(slide_img.height * ratio))
                        )
                    img.paste(slide_img, (margin, y))
                    y += slide_img.height + 16
                except Exception:
                    pass

            pages.append(img)

        if pages:
            from fpdf import FPDF
            pdf = FPDF(unit='pt', format=(page_w, page_h))
            for page_img in pages:
                buf = io.BytesIO()
                page_img.save(buf, format='PNG')
                pdf.add_page()
                pdf.image(buf, x=0, y=0, w=page_w, h=page_h)
            pdf.output(str(output_path))
        else:
            raise ValueError("no pages to render")

    @staticmethod
    def _preview_pptx(*, path: Path) -> dict:
        """提取 PPTX 按幻灯片文本内容供 Edit 模式展示,同时生成 HTML 预览。"""

        if path.suffix.lower() == ".ppt":
            return {
                "content": "",
                "html": "<p>旧版 .ppt 暂不支持预览,请转换为 .pptx 格式。</p>",
                "image_count": 0,
                "slide_count": 0,
            }

        try:
            import xml.etree.ElementTree as ET

            ns = {
                "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            }

            slides: list[dict] = []
            with zipfile.ZipFile(path) as archive:
                slide_paths = sorted(
                    name for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                )
                if not slide_paths:
                    return {
                        "content": "",
                        "html": "<p>PPTX 中没有找到幻灯片。</p>",
                        "image_count": 0,
                        "slide_count": 0,
                    }

                # Build an image cache: rId -> base64 data URL per slide
                for slide_index, slide_path in enumerate(slide_paths, start=1):
                    xml_text = archive.read(slide_path).decode("utf-8", errors="ignore")
                    slide_root = ET.fromstring(xml_text)

                    # Extract text
                    text_parts: list[str] = []
                    for text_elem in slide_root.iter(f"{{{ns['a']}}}t"):
                        if text_elem.text:
                            text_parts.append(text_elem.text.strip())
                    slide_text = "\n".join(part for part in text_parts if part)

                    # Extract images via relationships
                    rels_path = f"ppt/slides/_rels/{Path(slide_path).name}.rels"
                    rels_map: dict[str, str] = {}
                    try:
                        rels_xml = archive.read(rels_path).decode("utf-8", errors="ignore")
                        rels_root = ET.fromstring(rels_xml)
                        for rel in rels_root:
                            rid = rel.get("Id", "")
                            target = rel.get("Target", "")
                            if rid and target and "image" in str(rel.get("Type", "")):
                                # Resolve relative to ppt/slides/
                                media_path = str(Path("ppt/slides") / target).replace("\\", "/")
                                rels_map[rid] = media_path
                    except KeyError:
                        pass

                    # Find blip references in the slide
                    slide_images: list[str] = []
                    for blip in slide_root.iter(f"{{{ns['a']}}}blip"):
                        rid = blip.get(f"{{{ns['r']}}}embed") or blip.get(f"{{{ns['r']}}}link") or ""
                        media_path = rels_map.get(rid)
                        if media_path and media_path in archive.namelist():
                            img_bytes = archive.read(media_path)
                            ext = Path(media_path).suffix.lstrip(".") or "png"
                            if ext.lower() == "jpg":
                                ext = "jpeg"
                            b64 = base64.b64encode(img_bytes).decode("ascii")
                            slide_images.append(
                                f'<p><img src="data:image/{ext};base64,{b64}" style="max-width:100%" /></p>'
                            )

                    slides.append({
                        "text": slide_text,
                        "images": slide_images,
                        "index": slide_index,
                    })

            if not slides:
                return {
                    "content": "",
                    "html": "<p>PPTX 中没有可预览内容。</p>",
                    "image_count": 0,
                    "slide_count": 0,
                }

            # Build content (for Edit mode - plain text)
            content_parts: list[str] = []
            for slide in slides:
                content_parts.append(f"## Slide {slide['index']}\n\n{slide['text']}")
            content = "\n\n".join(content_parts).strip()

            # Build HTML (for Preview mode - rendered)
            html_parts: list[str] = []
            for slide in slides:
                html_parts.append(f"<h2>第 {slide['index']} 页</h2>")
                if slide["text"]:
                    for line in slide["text"].split("\n"):
                        line = line.strip()
                        if line:
                            html_parts.append(f"<p>{html.escape(line)}</p>")
                html_parts.extend(slide["images"])
            final_html = "\n".join(html_parts) or "<p>PPTX 中没有可预览内容。</p>"

            image_count = sum(len(s["images"]) for s in slides)
            return {
                "content": content,
                "html": final_html,
                "image_count": image_count,
                "slide_count": len(slides),
            }
        except Exception as exc:
            logger.warning("PPTX preview failed for %s: %s: %s", path, type(exc).__name__, exc)
            return {
                "content": "",
                "html": "<p>PPTX 解析失败。</p>",
                "image_count": 0,
                "slide_count": 0,
            }

    @staticmethod
    def _preview_pdf(*, path: Path) -> dict:
        """提取 PDF 文本层供 Edit 模式展示,Preview 模式仍使用原始 PDF。"""

        try:
            extracted = extract_pdf_text(path)
        except Exception:
            return {
                "content": "",
                "pdf_scanned": True,
                "page_count": 0,
                "image_count": 0,
                "table_count": 0,
            }
        return {
            "content": extracted.content,
            "pdf_scanned": extracted.is_scanned,
            "page_count": extracted.page_count,
            "image_count": extracted.image_count,
            "table_count": extracted.table_count,
        }

    def _preview_image_ocr(self, *, user_id: str, path: Path) -> dict:
        """对普通图片执行 OCR,供 Edit 模式展示识别文本。"""

        if not self.settings_service.is_ocr_enabled_for_user(user_id=user_id):
            return {"content": "", "ocr_status": "disabled", "ocr_word_count": 0}
        result = ImageOcrService(config=self.config).extract_image_text(path)
        return {
            "content": result.content,
            "ocr_status": "completed" if result.has_text else ("no_text" if result.engine_available else "engine_unavailable"),
            "ocr_engine_available": result.engine_available,
            "ocr_word_count": result.word_count,
            "ocr_average_confidence": result.average_confidence,
        }

    @staticmethod
    def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
        """读取 XLSX sharedStrings 表。"""

        try:
            xml_text = archive.read("xl/sharedStrings.xml").decode("utf-8", errors="ignore")
        except KeyError:
            return []
        root = ElementTree.fromstring(xml_text)
        return [" ".join(part.strip() for part in item.itertext() if part.strip()) for item in root]

    @classmethod
    def _extract_xlsx_rows(
        cls,
        *,
        archive: zipfile.ZipFile,
        sheet_path: str,
        shared_strings: list[str],
    ) -> list[list[str]]:
        """从 XLSX 工作表 XML 中读取前 200 行。"""

        root = ElementTree.fromstring(archive.read(sheet_path).decode("utf-8", errors="ignore"))
        rows: list[list[str]] = []
        for row in root.iter():
            if row.tag.rsplit("}", 1)[-1] != "row":
                continue
            values: list[str] = []
            for cell in row:
                if cell.tag.rsplit("}", 1)[-1] != "c":
                    continue
                values.append(cls._xlsx_cell_value(cell=cell, shared_strings=shared_strings))
            if any(values):
                rows.append(values)
            if len(rows) >= 200:
                break
        return rows

    @staticmethod
    def _xlsx_cell_value(*, cell: ElementTree.Element, shared_strings: list[str]) -> str:
        """解析 XLSX 单元格文本值。"""

        cell_type = cell.attrib.get("t")
        value = ""
        for child in cell:
            local_name = child.tag.rsplit("}", 1)[-1]
            if local_name == "v":
                value = child.text or ""
                break
            if local_name == "is":
                value = " ".join(part.strip() for part in child.itertext() if part.strip())
                break
        if cell_type == "s":
            try:
                return shared_strings[int(value)]
            except (ValueError, IndexError):
                return value
        return value

    def write_file(self, *, user_id: str, path: str, content: str) -> dict:
        """
        保存当前 active 知识库中的文本文件。

        注意: 保存文件只写入磁盘,不会触发向量灌库; 灌库只由显式扫描/重建触发。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if target.exists() and target.is_dir():
            raise ValueError("path is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return self._path_to_node(path=target, root=root)

    def create_file(self, *, user_id: str, path: str, content: str = "") -> dict:
        """
        在当前 active 知识库中新建文本文件。

        user_id: 用户 ID。
        path: 知识库根目录内的相对文件路径。
        content: 可选初始文本内容。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if target.exists():
            raise ValueError("path already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return self._path_to_node(path=target, root=root)

    def create_folder(self, *, user_id: str, path: str) -> dict:
        """
        在当前 active 知识库中新建文件夹。

        user_id: 用户 ID。
        path: 知识库根目录内的相对文件夹路径。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        target.mkdir(parents=True, exist_ok=True)
        return self._path_to_node(path=target, root=root)

    @staticmethod
    def _remove_readonly(func: Any, path: Path, exc_info: Any) -> None:
        """shutil.rmtree onerror 回调: 清除只读属性后重试删除。"""

        os.chmod(path, stat.S_IWRITE)
        func(path)

    @staticmethod
    def _force_unlink(path: Path) -> None:
        """先清除只读属性再删除文件,兼容 Windows 只读文件。"""

        os.chmod(path, stat.S_IWRITE)
        path.unlink()

    def delete_path(self, *, user_id: str, path: str) -> dict:
        """
        删除当前 active 知识库中的文件或文件夹。

        user_id: 用户 ID。
        path: 知识库根目录内的相对路径。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if not target.exists():
            raise ValueError("path not found")
        affected_paths = self._collect_relative_file_paths(target=target, root=root)
        try:
            self._delete_index_artifacts(user_id=user_id, relative_paths=affected_paths)
        except Exception:
            logger.exception("删除知识库索引工件失败,继续删除文件")
        if target.is_dir():
            shutil.rmtree(target, onerror=KnowledgeLibraryService._remove_readonly)
        else:
            self._force_unlink(target)
        return {"ok": True}

    def rename_path(self, *, user_id: str, source_path: str, target_path: str) -> dict:
        """
        移动或重命名当前 active 知识库中的文件/文件夹。

        user_id: 用户 ID。
        source_path: 原相对路径。
        target_path: 新相对路径。
        """

        root = self._get_active_root(user_id=user_id)
        source = self._resolve_child_path(root=root, relative_path=source_path)
        target = self._resolve_child_path(root=root, relative_path=target_path)
        if not source.exists():
            raise ValueError("source path not found")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError("target path already exists")
        affected_paths = self._collect_relative_file_paths(target=source, root=root)
        self._delete_index_artifacts(user_id=user_id, relative_paths=affected_paths)
        source.replace(target)
        return self._path_to_node(path=target, root=root)

    def copy_path(self, *, user_id: str, source_path: str, target_path: str) -> dict:
        """
        复制当前 active 知识库中的文件/文件夹。

        user_id: 用户 ID。
        source_path: 原相对路径。
        target_path: 复制后的相对路径。
        """

        root = self._get_active_root(user_id=user_id)
        source = self._resolve_child_path(root=root, relative_path=source_path)
        target = self._resolve_child_path(root=root, relative_path=target_path)
        if not source.exists():
            raise ValueError("source path not found")
        if target.exists():
            raise ValueError("target path already exists")
        if source.is_dir() and self._is_relative_to(target, source):
            raise ValueError("cannot copy a directory into itself")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        return self._path_to_node(path=target, root=root)

    def build_tree_signature(self, *, user_id: str) -> dict[str, tuple[int, int, str]]:
        """
        构建文件树轻量签名,供事件流检测变化。

        user_id: 用户 ID。
        """

        root = self._get_active_root(user_id=user_id)
        if not root.exists():
            return {}
        signature: dict[str, tuple[int, int, str]] = {}
        for path in root.rglob("*"):
            stat = path.stat()
            path_type = "dir" if path.is_dir() else "file"
            signature[self._relative_path(path=path, root=root)] = (
                int(stat.st_mtime_ns),
                stat.st_size,
                path_type,
            )
        return signature

    def _get_active_root(self, *, user_id: str) -> Path:
        """
        返回用户当前 active 知识库根目录。

        user_id: 用户 ID。
        """

        active_library = self.settings_service.get_active_knowledge_library(user_id=user_id)
        return Path(str(active_library["knowledge_dir"])).expanduser().resolve()

    def _resolve_user_frontmatter_dir(self, user_id: str, library_id: str) -> Path:
        """
        返回用户隔离的结构化知识目录。

        user_id: 用户 ID。
        library_id: 知识库配置 ID。
        """

        safe_user_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", user_id).strip("_") or "default"
        safe_library_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", library_id).strip("_") or "default"
        return self.config.storage.frontmatter_dir / "users" / safe_user_id / safe_library_id

    @classmethod
    def _resolve_child_dir(cls, *, root: Path, relative_dir: str) -> Path:
        """
        解析上传目标子目录并防止路径穿越。

        root: 知识库根目录。
        relative_dir: 前端传入的相对目录。
        """

        normalized = relative_dir.strip().replace("\\", "/")
        if not normalized:
            return root
        candidate = (root / normalized).resolve()
        if not cls._is_relative_to(candidate, root):
            raise ValueError("relative_dir escapes knowledge_dir")
        return candidate

    @classmethod
    def _resolve_child_path(cls, *, root: Path, relative_path: str) -> Path:
        """
        解析知识库根目录内的相对路径并防止路径穿越。

        root: 知识库根目录。
        relative_path: 前端传入的相对路径。
        """

        normalized = relative_path.strip().replace("\\", "/").strip("/")
        if not normalized:
            raise ValueError("path is required")
        candidate = (root / normalized).resolve()
        if not cls._is_relative_to(candidate, root):
            raise ValueError("path escapes knowledge_dir")
        return candidate

    @classmethod
    def _unique_child_path(cls, *, target_dir: Path, preferred_name: str) -> Path:
        """返回 target_dir 中不冲突的子路径,命名格式为 `file (1).txt`。"""

        safe_name = Path(preferred_name).name.strip() or "untitled"
        first_path = (target_dir / safe_name).resolve()
        if not first_path.exists():
            return first_path
        stem = first_path.stem
        suffix = first_path.suffix
        for index in range(1, 1000):
            candidate = (target_dir / f"{stem} ({index}){suffix}").resolve()
            if not candidate.exists():
                return candidate
        return (target_dir / f"{stem} ({int(time.time())}){suffix}").resolve()

    def _path_to_node(
        self,
        *,
        path: Path,
        root: Path,
        ignore_matcher: KnowledgeIgnoreMatcher | None = None,
        indexed_source_ids: set[str] | None = None,
        source_updated_at: dict[str, datetime] | None = None,
        frontmatter_root: Path | None = None,
        ocr_enabled: bool = False,
    ) -> dict:
        """
        将文件系统路径转换为前端文件树节点。

        path: 文件或文件夹绝对路径。
        root: 知识库根目录。
        """

        is_dir = path.is_dir()
        stat = path.stat()
        relative_path = self._relative_path(path=path, root=root)
        ignored = bool(ignore_matcher and ignore_matcher.is_ignored(relative_path, is_dir=is_dir))
        source_id = FrontmatterBootstrapService._build_document_id(Path(relative_path)) if not is_dir else ""
        is_indexed = bool(source_id and source_id in (indexed_source_ids or set()))
        if is_indexed and ocr_enabled and frontmatter_root and self._source_needs_ocr_reindex(
            source_path=path,
            relative_path=relative_path,
            frontmatter_root=frontmatter_root,
        ):
            is_indexed = False
        node = {
            "name": path.name,
            "path": relative_path,
            "isDir": is_dir,
            "mtime": self._format_mtime(path),
            "indexStatus": "ignored" if ignored else ("indexed" if is_indexed else "dirty"),
        }
        if is_indexed and source_id and source_updated_at:
            ingested_at = source_updated_at.get(source_id)
            if ingested_at:
                node["ingestedAt"] = self._format_datetime(ingested_at)
        if is_dir:
            node["children"] = [
                self._path_to_node(
                    path=child,
                    root=root,
                    ignore_matcher=ignore_matcher,
                    indexed_source_ids=indexed_source_ids,
                    source_updated_at=source_updated_at,
                    frontmatter_root=frontmatter_root,
                    ocr_enabled=ocr_enabled,
                )
                for child in sorted(path.iterdir(), key=self._sort_path)
            ]
            child_ingested_at = [
                str(child.get("ingestedAt") or "")
                for child in node["children"]
                if child.get("ingestedAt")
            ]
            if child_ingested_at:
                node["ingestedAt"] = max(child_ingested_at)
        else:
            node["size"] = stat.st_size
        return node

    def _build_ignore_matcher(self, *, user_id: str) -> KnowledgeIgnoreMatcher:
        """从用户设置构造知识库屏蔽规则匹配器。"""

        config = self.settings_service.get_knowledge_ingestion_config(user_id=user_id)
        return KnowledgeIgnoreMatcher(str(config.get("knowledge_ignore_patterns") or ""))

    def _delete_ignored_frontmatter_files(
        self,
        *,
        frontmatter_root: Path,
        ignore_matcher: KnowledgeIgnoreMatcher,
    ) -> None:
        """删除已被屏蔽规则命中的旧 frontmatter JSON,确保后续入库扫描看不到它们。"""

        if not frontmatter_root.exists():
            return
        for frontmatter_path in sorted(frontmatter_root.rglob("*.json")):
            if not frontmatter_path.is_file():
                continue
            try:
                payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
            relative_path = str(metadata.get("relative_path") or "")
            if relative_path and ignore_matcher.is_ignored(relative_path, is_dir=False):
                frontmatter_path.unlink(missing_ok=True)

    def _collect_relative_file_paths(self, *, target: Path, root: Path) -> list[str]:
        """收集文件或目录子树内的知识库相对文件路径。"""

        if target.is_file():
            return [self._relative_path(path=target, root=root)]
        if target.is_dir():
            return [
                self._relative_path(path=path, root=root)
                for path in target.rglob("*")
                if path.is_file()
            ]
        return []

    def _delete_index_artifacts(self, *, user_id: str, relative_paths: list[str]) -> int:
        """删除给定来源文件对应的 frontmatter 和向量切片。"""

        if not relative_paths:
            return 0
        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        active_library = dict(profile["active_knowledge_library"])
        normalized_user_id = str(profile["user_id"])
        library_id = str(active_library["library_id"])
        knowledge_owner_id = self.settings_service.build_knowledge_owner_id(
            user_id=normalized_user_id,
            library_id=library_id,
        )
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id).resolve()
        chunks_deleted = 0
        for relative_path in relative_paths:
            normalized_path = relative_path.replace("\\", "/").strip("/")
            if not normalized_path:
                continue
            source_id = FrontmatterBootstrapService._build_document_id(Path(normalized_path))
            chunks_deleted += self.memory_service.delete_memories_for_source(
                user_id=knowledge_owner_id,
                tag=self.config.constants.knowledge_tag,
                memory_type="knowledge_chunk",
                source_id=source_id,
            )
            frontmatter_path = (frontmatter_root / normalized_path).with_suffix(".json").resolve()
            if self._is_relative_to(frontmatter_path, frontmatter_root) and frontmatter_path.exists():
                frontmatter_path.unlink()
        return chunks_deleted

    def _source_needs_ocr_reindex(
        self,
        *,
        source_path: Path,
        relative_path: str,
        frontmatter_root: Path,
    ) -> bool:
        """判断 OCR 开启后当前文件的旧 frontmatter 是否需要重建。"""

        if not self._source_may_contain_images(source_path):
            return False
        frontmatter_path = (frontmatter_root / relative_path).with_suffix(".json").resolve()
        if not self._is_relative_to(frontmatter_path, frontmatter_root) or not frontmatter_path.is_file():
            return True
        try:
            payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        except Exception:
            return True
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        return not bool(metadata.get("ocr_enabled"))

    @staticmethod
    def _source_may_contain_images(source_path: Path) -> bool:
        """快速判断文件是否可能需要 OCR 重新结构化。"""

        suffix = source_path.suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf"}:
            return True
        media_prefixes = {
            ".docx": "word/media/",
            ".pptx": "ppt/media/",
            ".xlsx": "xl/media/",
        }
        media_prefix = media_prefixes.get(suffix)
        if not media_prefix:
            return False
        try:
            with zipfile.ZipFile(source_path) as archive:
                return any(name.startswith(media_prefix) for name in archive.namelist())
        except (OSError, zipfile.BadZipFile):
            return False

    @staticmethod
    def _relative_path(*, path: Path, root: Path) -> str:
        """
        返回 POSIX 风格相对路径。

        path: 子路径。
        root: 根目录。
        """

        return path.relative_to(root).as_posix()

    @staticmethod
    def _sort_path(path: Path) -> tuple[int, str]:
        """
        文件树排序键: 文件夹优先,同级按名称排序。

        path: 待排序路径。
        """

        return (0 if path.is_dir() else 1, path.name.lower())

    @staticmethod
    def _format_mtime(path: Path) -> str:
        """
        格式化文件修改时间。

        path: 文件系统路径。
        """

        from datetime import datetime

        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        """格式化数据库时间为前端展示时间。"""

        if value.tzinfo is None:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.astimezone().strftime("%Y-%m-%d %H:%M")

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

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        """
        判断 path 是否位于 root 目录下。

        path: 待检查路径。
        root: 根目录。
        """

        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
