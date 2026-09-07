"""KnowledgeLibraryService 的 trash 职责。

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

class KnowledgeTrashMixin:
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
        chunks_deleted = self._delete_index_artifacts(user_id=user_id, relative_paths=affected_paths)
        return self._move_path_to_trash(user_id=user_id, root=root, target=target, chunks_deleted=chunks_deleted)
    def list_deleted_paths(self, *, user_id: str) -> list[dict[str, Any]]:
        """List non-expired trash entries for the current active knowledge library."""

        context = self._active_library_context(user_id=user_id)
        self.purge_expired_trash(user_id=user_id)
        trash_root = self._trash_root_for(user_id=context["user_id"], library_id=context["library_id"])
        if not trash_root.exists():
            return []
        entries: list[dict[str, Any]] = []
        for entry_dir in sorted(trash_root.iterdir(), key=lambda item: item.name, reverse=True):
            if not entry_dir.is_dir():
                continue
            metadata = self._read_trash_metadata(entry_dir)
            if metadata:
                entries.append(metadata)
        return sorted(entries, key=lambda item: str(item.get("deleted_at") or ""), reverse=True)
    def restore_deleted_path(self, *, user_id: str, trash_id: str) -> dict[str, Any]:
        """Restore one trash entry back into the active knowledge library."""

        context = self._active_library_context(user_id=user_id)
        self.purge_expired_trash(user_id=user_id)
        entry_dir = self._resolve_trash_entry_dir(
            user_id=context["user_id"],
            library_id=context["library_id"],
            trash_id=trash_id,
        )
        metadata = self._read_trash_metadata(entry_dir)
        if not metadata:
            raise ValueError("trash entry not found")
        content_path = self._trash_content_path(entry_dir=entry_dir, metadata=metadata)
        if not content_path.exists():
            raise ValueError("trash content not found")
        root = context["root"]
        original_path = str(metadata.get("original_relative_path") or "").strip()
        target = self._resolve_child_path(root=root, relative_path=original_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = self._unique_child_path(target_dir=target.parent, preferred_name=target.name)
        shutil.move(str(content_path), str(target))
        shutil.rmtree(entry_dir, onerror=KnowledgeTrashMixin._remove_readonly)
        restored_path = self._relative_path(path=target.resolve(), root=root)
        artifact_result = self._restore_index_artifacts(
            user_id=user_id,
            root=root,
            target=target,
            restored_path=restored_path,
        )
        return {
            "ok": True,
            "trash_id": str(metadata.get("trash_id") or trash_id),
            "restored_path": restored_path,
            "node": self._path_to_node(path=target.resolve(), root=root),
            **artifact_result,
        }
    def delete_trash_entry(self, *, user_id: str, trash_id: str) -> dict[str, Any]:
        """Permanently delete one trash entry."""

        context = self._active_library_context(user_id=user_id)
        entry_dir = self._resolve_trash_entry_dir(
            user_id=context["user_id"],
            library_id=context["library_id"],
            trash_id=trash_id,
        )
        if not entry_dir.exists():
            raise ValueError("trash entry not found")
        shutil.rmtree(entry_dir, onerror=KnowledgeTrashMixin._remove_readonly)
        return {"ok": True, "trash_id": trash_id}
    def purge_expired_trash(self, *, user_id: str | None = None) -> dict[str, int]:
        """Remove trash entries whose expires_at timestamp is in the past."""

        roots: list[Path]
        if user_id:
            context = self._active_library_context(user_id=user_id)
            roots = [self._trash_root_for(user_id=context["user_id"], library_id=context["library_id"])]
        else:
            base_root = self._trash_base_root()
            roots = [path for path in base_root.glob("*/*") if path.is_dir()] if base_root.exists() else []
        now = _utcnow_naive()
        removed = 0
        seen = 0
        for root in roots:
            if not root.exists():
                continue
            for entry_dir in root.iterdir():
                if not entry_dir.is_dir():
                    continue
                seen += 1
                metadata = self._read_trash_metadata(entry_dir)
                expires_at = self._parse_iso_datetime(str((metadata or {}).get("expires_at") or ""))
                if expires_at and expires_at <= now:
                    shutil.rmtree(entry_dir, onerror=KnowledgeTrashMixin._remove_readonly)
                    removed += 1
        return {"entries_seen": seen, "entries_removed": removed}
    def _trash_base_root(self) -> Path:
        """Return the runtime trash root."""

        return Path(self.config.storage.trash_dir).expanduser().resolve()
    def _trash_root_for(self, *, user_id: str, library_id: str) -> Path:
        """Return the isolated trash root for one user/library pair."""

        return (
            self._trash_base_root()
            / self._safe_storage_name(user_id)
            / self._safe_storage_name(library_id)
        )
    def _resolve_trash_entry_dir(self, *, user_id: str, library_id: str, trash_id: str) -> Path:
        """Resolve and validate a trash entry directory."""

        trash_root = self._trash_root_for(user_id=user_id, library_id=library_id).resolve()
        entry_dir = (trash_root / self._safe_storage_name(trash_id)).resolve()
        if not self._is_relative_to(entry_dir, trash_root):
            raise ValueError("trash_id escapes trash root")
        return entry_dir
    def _move_path_to_trash(self, *, user_id: str, root: Path, target: Path, chunks_deleted: int) -> dict[str, Any]:
        """Move a knowledge path into runtime trash after index artifacts are removed."""

        context = self._active_library_context(user_id=user_id)
        self.purge_expired_trash(user_id=user_id)
        trash_id = f"{_utcnow_naive().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:12]}"
        entry_dir = self._resolve_trash_entry_dir(
            user_id=context["user_id"],
            library_id=context["library_id"],
            trash_id=trash_id,
        )
        content_dir = entry_dir / "content"
        content_dir.mkdir(parents=True, exist_ok=False)
        deleted_at = _utcnow_naive()
        expires_at = deleted_at + timedelta(days=self.limits.knowledge_trash_retention_days)
        target = target.resolve()
        stored_name = target.name
        metadata = {
            "trash_id": trash_id,
            "user_id": context["user_id"],
            "library_id": context["library_id"],
            "original_relative_path": self._relative_path(path=target, root=root),
            "name": target.name,
            "stored_name": stored_name,
            "is_dir": target.is_dir(),
            "size": self._path_size(target),
            "deleted_at": deleted_at.isoformat(timespec="seconds"),
            "expires_at": expires_at.isoformat(timespec="seconds"),
            "chunks_deleted": chunks_deleted,
        }
        self._write_trash_metadata(entry_dir=entry_dir, metadata=metadata)
        shutil.move(str(target), str(content_dir / stored_name))
        return {"ok": True, **metadata}
    def _write_trash_metadata(self, *, entry_dir: Path, metadata: dict[str, Any]) -> None:
        """Persist trash metadata next to the moved content."""

        metadata_path = entry_dir / "metadata.json"
        temp_path = entry_dir / "metadata.tmp"
        temp_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(metadata_path)
    def _read_trash_metadata(self, entry_dir: Path) -> dict[str, Any] | None:
        """Read a trash metadata file and enrich it with current content size."""

        metadata_path = entry_dir / "metadata.json"
        if not metadata_path.is_file():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(metadata, dict):
            return None
        content_path = self._trash_content_path(entry_dir=entry_dir, metadata=metadata)
        metadata["size"] = self._path_size(content_path) if content_path.exists() else int(metadata.get("size") or 0)
        return metadata
    @staticmethod
    def _trash_content_path(*, entry_dir: Path, metadata: dict[str, Any]) -> Path:
        """Return the content path inside one trash entry."""

        stored_name = Path(str(metadata.get("stored_name") or metadata.get("name") or "")).name
        return entry_dir / "content" / stored_name
    @classmethod
    def _path_size(cls, path: Path) -> int:
        """Return a file or directory subtree size in bytes."""

        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())
        return 0
    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime | None:
        """Parse a stored ISO datetime value."""

        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
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
        """删除给定来源文件对应的 frontmatter、向量切片和图谱点边。"""

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
        markdown_root = self._resolve_user_markdown_dir(normalized_user_id, library_id).resolve()
        assets_root = (Path(str(active_library["knowledge_dir"])).expanduser().resolve() / ".mw" / "assets").resolve()
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
            markdown_path = (markdown_root / normalized_path).with_suffix(".md").resolve()
            if self._is_relative_to(markdown_path, markdown_root) and markdown_path.exists():
                markdown_path.unlink()
            asset_path = (assets_root / normalized_path).resolve()
            if self._is_relative_to(asset_path, assets_root) and asset_path.exists():
                if asset_path.is_dir():
                    shutil.rmtree(asset_path, onerror=KnowledgeTrashMixin._remove_readonly)
                else:
                    self._force_unlink(asset_path)
            # 同时删除该文档产生的图谱点边和状态记录
            delete_document_graph = getattr(self.knowledge_graph_service, "delete_document_graph", None)
            if callable(delete_document_graph):
                delete_document_graph(
                    user_id=normalized_user_id,
                    library_id=library_id,
                    document_id=source_id,
                )
        return chunks_deleted

    def _restore_index_artifacts(
        self,
        *,
        user_id: str,
        root: Path,
        target: Path,
        restored_path: str,
    ) -> dict[str, Any]:
        """恢复源文件后重建 `.mw`、向量切片和文档图谱。"""

        try:
            ingestion_result = self.ingest_path(user_id=user_id, path=restored_path)
        except Exception:
            logger.exception("恢复文件后重新灌库失败 | path=%s", restored_path)
            return {"artifacts_restored": False, "files_reingested": 0, "graphs_restored": 0}

        profile = self.settings_service.ensure_user_profile(user_id=user_id)
        normalized_user_id = str(profile["user_id"])
        library_id = str(dict(profile["active_knowledge_library"])["library_id"])
        frontmatter_root = self._resolve_user_frontmatter_dir(normalized_user_id, library_id).resolve()
        get_llm_config = getattr(self.settings_service, "get_llm_config", None)
        llm_config = get_llm_config(user_id=normalized_user_id) if callable(get_llm_config) else None
        graph_failures = 0
        graphs_restored = 0
        ignore_matcher = self._build_ignore_matcher(user_id=normalized_user_id)
        for relative_path in self._collect_relative_file_paths(target=target, root=root):
            source_path = self._resolve_child_path(root=root, relative_path=relative_path)
            if not self._can_ingest_source_file(source_path):
                continue
            if ignore_matcher.is_ignored(relative_path, is_dir=False) and not self._is_managed_ingest_source(relative_path):
                continue
            frontmatter_path = (frontmatter_root / relative_path).with_suffix(".json").resolve()
            if not self._is_relative_to(frontmatter_path, frontmatter_root) or not frontmatter_path.is_file():
                graph_failures += 1
                logger.error("恢复文件后缺少 frontmatter | path=%s", relative_path)
                continue
            try:
                graph_result = self.knowledge_graph_service.extract_frontmatter_file(
                    user_id=normalized_user_id,
                    library_id=library_id,
                    frontmatter_path=frontmatter_path,
                    llm_config=llm_config,
                )
                if int(getattr(graph_result, "files_failed", 0)) > 0:
                    graph_failures += 1
                else:
                    graphs_restored += 1
            except Exception:
                graph_failures += 1
                logger.exception("恢复文件后重建图谱失败 | path=%s", relative_path)
        return {
            "artifacts_restored": graph_failures == 0,
            "files_reingested": int(getattr(ingestion_result, "files_ingested", 0)),
            "graphs_restored": graphs_restored,
        }
