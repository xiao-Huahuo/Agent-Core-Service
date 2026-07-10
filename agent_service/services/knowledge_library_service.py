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

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.settings_service import SettingsService


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
    ) -> None:
        """保存依赖服务。"""

        self.config = config
        self.memory_service = memory_service
        self.settings_service = settings_service
        self.embedding_service = embedding_service

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

        frontmatter_result = FrontmatterBootstrapService(config=self.config).build_frontmatter_dir(
            knowledge_dir=source_root,
            frontmatter_dir=frontmatter_root,
            supported_suffixes=self.supported_suffixes,
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

    def write_uploaded_file(
        self,
        *,
        user_id: str,
        filename: str,
        content: bytes,
        relative_dir: str = "",
    ) -> Path:
        """
        将前端上传的文件写入用户知识库目录。

        user_id: 用户 ID。
        filename: 上传文件名。
        content: 文件二进制内容。
        relative_dir: 可选目标子目录,必须位于知识库根目录内。
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
        target_path.write_bytes(content)
        return target_path

    def list_files(self, *, user_id: str) -> list[dict]:
        """
        列出当前 active 知识库的递归文件树。

        user_id: 用户 ID。
        """

        root = self._get_active_root(user_id=user_id)
        root.mkdir(parents=True, exist_ok=True)
        return [self._path_to_node(path=path, root=root) for path in sorted(root.iterdir(), key=self._sort_path)]

    def get_active_root_path(self, *, user_id: str) -> Path:
        """
        返回当前 active 知识库根目录并确保目录存在。

        user_id: 用户 ID。
        """

        root = self._get_active_root(user_id=user_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

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
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
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

    def _path_to_node(self, *, path: Path, root: Path) -> dict:
        """
        将文件系统路径转换为前端文件树节点。

        path: 文件或文件夹绝对路径。
        root: 知识库根目录。
        """

        is_dir = path.is_dir()
        stat = path.stat()
        node = {
            "name": path.name,
            "path": self._relative_path(path=path, root=root),
            "isDir": is_dir,
            "mtime": self._format_mtime(path),
            "indexStatus": "dirty",
        }
        if is_dir:
            node["children"] = [
                self._path_to_node(path=child, root=root)
                for child in sorted(path.iterdir(), key=self._sort_path)
            ]
        else:
            node["size"] = stat.st_size
        return node

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
