"""KnowledgeLibraryService 的 file_tree 职责。

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

class KnowledgeFileTreeMixin:
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
            elif normalized_strategy == "overwrite":
                relative_path = self._relative_path(path=target_path, root=root)
                self.invalidate_paths(user_id=user_id, relative_paths=[relative_path])
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
        list_graph_statuses = getattr(self.knowledge_graph_service, "list_document_statuses", None)
        graph_status_by_document = (
            list_graph_statuses(user_id=normalized_user_id, library_id=library_id)
            if callable(list_graph_statuses)
            else {}
        )
        return [
            self._path_to_node(
                path=path,
                root=root,
                ignore_matcher=ignore_matcher,
                indexed_source_ids=indexed_source_ids,
                source_updated_at=source_updated_at,
                graph_status_by_document=graph_status_by_document,
                frontmatter_root=frontmatter_root,
                ocr_enabled=ocr_enabled,
            )
            for path in sorted(root.iterdir(), key=self._sort_path)
            if path.name != ".git"
        ]
    def get_active_root_path(self, *, user_id: str) -> Path:
        """
        返回当前 active 知识库根目录并确保目录存在。

        user_id: 用户 ID。
        """

        root = self._get_active_root(user_id=user_id)
        root.mkdir(parents=True, exist_ok=True)
        return root
    def read_markdown_projection(self, *, user_id: str, path: str) -> dict:
        """读取源文件的受管 Markdown 投影，缺失或过期时先执行单文件灌库。

        user_id: 当前用户 ID。
        path: 当前 active 知识库内的源文件相对路径，而不是 `.mw/md` 内部路径。
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
        source_path = self._resolve_child_path(root=root, relative_path=path)
        if not source_path.is_file():
            raise ValueError("file not found")

        relative_path = self._relative_path(path=source_path, root=root)
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id).resolve()
        markdown_root = self._resolve_user_markdown_dir(normalized_user_id, library_id).resolve()
        frontmatter_path = (frontmatter_root / relative_path).with_suffix(".json").resolve()
        markdown_path = (markdown_root / relative_path).with_suffix(".md").resolve()
        if (
            not self._is_relative_to(frontmatter_path, frontmatter_root)
            or not self._is_relative_to(markdown_path, markdown_root)
        ):
            raise ValueError("projection path escapes user library")

        source_id = FrontmatterBootstrapService._build_document_id(Path(relative_path))
        indexed_source_ids = self.memory_service.list_source_ids(
            user_id=knowledge_owner_id,
            tag=self.config.constants.knowledge_tag,
            memory_type="knowledge_chunk",
        )
        projection_is_current = (
            markdown_path.is_file()
            and frontmatter_path.is_file()
            and source_id in indexed_source_ids
        )
        if projection_is_current:
            try:
                payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
                metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
                projection_is_current = (
                    str(metadata.get("relative_path") or "") == relative_path
                    and str(payload.get("source_hash") or "") == FrontmatterBootstrapService._hash_file(source_path)
                )
            except (OSError, json.JSONDecodeError):
                projection_is_current = False
        if (
            projection_is_current
            and self.settings_service.is_ocr_enabled_for_user(user_id=normalized_user_id)
            and self._source_needs_ocr_reindex(
                source_path=source_path,
                relative_path=relative_path,
                frontmatter_root=frontmatter_root,
            )
        ):
            projection_is_current = False

        if not projection_is_current:
            self.ingest_single_file(user_id=normalized_user_id, path=relative_path)
        if not markdown_path.is_file():
            raise ValueError("markdown projection not found after ingestion")

        return {
            "path": relative_path,
            "projection_path": self._relative_path(path=markdown_path, root=root),
            "content": markdown_path.read_text(encoding="utf-8"),
            "mtime": self._format_mtime(markdown_path),
            "size": markdown_path.stat().st_size,
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
    def write_file(self, *, user_id: str, path: str, content: str) -> dict:
        """
        保存当前 active 知识库中的文本文件。

        注意: 覆盖已有文件会先清理该来源的旧 frontmatter、向量切片与图谱数据。
        新内容的重新入库仍由显式扫描/重建触发。
        """

        root = self._get_active_root(user_id=user_id)
        target = self._resolve_child_path(root=root, relative_path=path)
        if target.exists() and target.is_dir():
            raise ValueError("path is a directory")
        if target.exists():
            relative_path = self._relative_path(path=target, root=root)
            self.invalidate_paths(user_id=user_id, relative_paths=[relative_path])
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
            # 目录 mtime 会因任一子项变化而改变。只跟踪文件可避免把整个目录
            # 误判为失效目标；目录删除仍会表现为其中所有旧文件路径消失。
            if not path.is_file():
                continue
            stat = path.stat()
            signature[self._relative_path(path=path, root=root)] = (
                int(stat.st_mtime_ns),
                stat.st_size,
                "file",
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

        managed_dir = self._resolve_user_managed_dir(user_id=user_id, library_id=library_id, name="frontmatter")
        safe_user_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", user_id).strip("_") or "default"
        safe_library_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", library_id).strip("_") or "default"
        legacy_dir = self.config.storage.frontmatter_dir / "users" / safe_user_id / safe_library_id
        if legacy_dir.is_dir() and legacy_dir.resolve() != managed_dir.resolve():
            for source in sorted(legacy_dir.rglob("*.json")):
                destination = managed_dir / source.relative_to(legacy_dir)
                if destination.exists():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
        return managed_dir
    def _resolve_user_markdown_dir(self, user_id: str, library_id: str) -> Path:
        """Return the active knowledge library's mirrored Markdown directory."""

        return self._resolve_user_managed_dir(user_id=user_id, library_id=library_id, name="md")
    def _resolve_user_managed_dir(self, *, user_id: str, library_id: str, name: str) -> Path:
        """Resolve one `.mw` managed directory inside the requested knowledge library."""

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        libraries = [dict(item) for item in profile.get("knowledge_libraries", [])]
        active_library = dict(profile["active_knowledge_library"])
        library = next((item for item in libraries if str(item.get("library_id")) == library_id), active_library)
        if str(library.get("library_id")) != library_id:
            raise ValueError("knowledge library not found")
        knowledge_root = Path(str(library["knowledge_dir"])).expanduser().resolve()
        return knowledge_root / ".mw" / name
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
        graph_status_by_document: dict[str, Any] | None = None,
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
        if not is_dir and not self._can_ingest_source_file(path):
            ignored = True
        source_id = FrontmatterBootstrapService._build_document_id(Path(relative_path)) if not is_dir else ""
        is_indexed = bool(source_id and source_id in (indexed_source_ids or set()))
        if is_indexed and ocr_enabled and frontmatter_root and self._source_needs_ocr_reindex(
            source_path=path,
            relative_path=relative_path,
            frontmatter_root=frontmatter_root,
        ):
            is_indexed = False
        index_status = "ignored" if ignored else ("indexed" if is_indexed else "dirty")
        graph_status = (
            "ignored"
            if ignored
            else self._graph_status_for_source(
                source_id=source_id,
                relative_path=relative_path,
                frontmatter_root=frontmatter_root,
                graph_status_by_document=graph_status_by_document,
                is_indexed=is_indexed,
            )
        )
        node = {
            "name": path.name,
            "path": relative_path,
            "isDir": is_dir,
            "mtime": self._format_mtime(path),
            "createdAt": self._format_ctime(path),
            "indexStatus": index_status,
            "graphStatus": graph_status,
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
                    graph_status_by_document=graph_status_by_document,
                    frontmatter_root=frontmatter_root,
                    ocr_enabled=ocr_enabled,
                )
                for child in sorted(path.iterdir(), key=self._sort_path)
                if child.name != ".git"
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
    def _graph_status_for_source(
        self,
        *,
        source_id: str,
        relative_path: str,
        frontmatter_root: Path | None,
        graph_status_by_document: dict[str, Any] | None,
        is_indexed: bool,
    ) -> str:
        """Return whether one source file has current graph extraction output."""

        if not source_id or not is_indexed or frontmatter_root is None:
            return "dirty"
        frontmatter_path = (frontmatter_root / relative_path).with_suffix(".json").resolve()
        if not self._is_relative_to(frontmatter_path, frontmatter_root) or not frontmatter_path.is_file():
            return "dirty"
        try:
            payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        except Exception:
            return "dirty"
        source_hash = str(payload.get("projection_hash") or payload.get("source_hash") or "")
        status = (graph_status_by_document or {}).get(source_id)
        if (
            status
            and str(getattr(status, "source_hash", "")) == source_hash
            and str(getattr(status, "status", "")) in {"completed", "skipped"}
        ):
            return "graphed"
        return "dirty"
    @staticmethod
    def _is_mw_managed_path(*, path: Path, root: Path) -> bool:
        """Return whether a path belongs to the knowledge library's `.mw` subtree."""

        try:
            relative_parts = path.resolve().relative_to(root.resolve()).parts
        except ValueError:
            return True
        return bool(relative_parts and relative_parts[0] == ".mw")
    @staticmethod
    def _safe_storage_name(value: str) -> str:
        """Return a filesystem-safe directory name for runtime metadata."""

        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "default"
    def _active_library_context(self, *, user_id: str) -> dict[str, Any]:
        """Return normalized user/library/root context for trash operations."""

        if hasattr(self.settings_service, "ensure_user_profile"):
            profile = self.settings_service.ensure_user_profile(user_id=user_id)
            active_library = dict(profile["active_knowledge_library"])
            normalized_user_id = str(profile["user_id"])
        else:
            active_library = dict(self.settings_service.get_active_knowledge_library(user_id=user_id))
            normalized_user_id = user_id
        library_id = str(active_library.get("library_id") or "default")
        root = Path(str(active_library["knowledge_dir"])).expanduser().resolve()
        return {"user_id": normalized_user_id, "library_id": library_id, "root": root}
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
    def _format_ctime(path: Path) -> str:
        """Format the filesystem creation time for frontend file metadata."""

        from datetime import datetime

        stat = path.stat()
        timestamp = getattr(stat, "st_birthtime", stat.st_ctime)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    @staticmethod
    def _format_datetime(value: datetime) -> str:
        """格式化数据库时间为前端展示时间。"""

        if value.tzinfo is None:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
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
