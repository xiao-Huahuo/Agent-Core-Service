"""
知识库结构化文档入库服务。
功能说明:
本文件负责读取 `frontmatter_bootstrap` 生成的结构化知识 JSON,按章节切块、生成 Embedding,
并以 `tag=Knowledge`、`memory_type=knowledge_chunk` 的统一长期记忆格式写入数据库。它不再
直接解析原始 Markdown/TXT,而是只消费 `runtime/frontmatter` 中的结构化文档。
使用说明:
service = KnowledgeIngestionService(config=config)
result = service.ingest_frontmatter_dir()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent_service.core.agent_config import AgentConfig

logger = logging.getLogger(__name__)
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.chunk import chunk_text
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeDocument


@dataclass(slots=True)
class KnowledgeIngestionResult:
    """
    知识库入库结果。
    files_seen: 扫描到的结构化知识文档数量。
    files_ingested: 实际入库的结构化知识文档数量。
    files_skipped: 因哈希锁跳过的结构化知识文档数量。
    chunks_created: 创建的知识切片数量。
    """

    files_seen: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    chunks_created: int = 0


class KnowledgeIngestionService:
    """
    结构化知识文档入库服务。
    config: 全局配置对象。
    embedding_service: 可选 Embedding 服务,测试时可注入假向量。
    memory_service: 可选长期记忆服务,测试时可注入 SQLite 版本。
    """

    def __init__(
        self,
        *,
        config: AgentConfig,
        embedding_service: EmbeddingService | None = None,
        memory_service: LongTermMemoryService | None = None,
    ) -> None:
        """初始化结构化知识文档入库服务。"""

        self.config = config
        self.embedding_service = embedding_service or EmbeddingService(config=config)
        self.memory_service = memory_service or LongTermMemoryService(config=config)

    def ingest_frontmatter_dir(self) -> KnowledgeIngestionResult:
        """
        扫描并入库结构化知识文档目录。
        返回值描述结构化文档与 chunk 的处理统计。
        """

        result = KnowledgeIngestionResult()
        frontmatter_files = self._iter_frontmatter_files(self.config.storage.frontmatter_dir)
        logger.info("知识库向量灌库开始 | 扫描到 %d 个结构化文档", len(frontmatter_files))
        for frontmatter_path in frontmatter_files:
            result.files_seen += 1
            rel_path = frontmatter_path.relative_to(self.config.storage.frontmatter_dir)
            document = self._load_document(frontmatter_path)
            if self.config.memory.knowledge_hash_lock_enabled and self.memory_service.has_source_hash(
                source_hash=document.source_hash,
                memory_type="knowledge_chunk",
            ):
                result.files_skipped += 1
                logger.debug("  [跳过] %s (哈希未变更)", rel_path)
                continue
            chunks_created = self._ingest_document(document=document)
            if chunks_created == 0:
                result.files_skipped += 1
                logger.warning("  [跳过] %s (0 chunk)", rel_path)
                continue
            result.files_ingested += 1
            result.chunks_created += chunks_created
            logger.info("  [入库] %s → %d chunks", document.title, chunks_created)
        logger.info(
            "知识库向量灌库完成 | %d 文档: %d 入库, %d 跳过, 共 %d chunks",
            result.files_seen,
            result.files_ingested,
            result.files_skipped,
            result.chunks_created,
        )
        return result

    def _ingest_document(self, *, document: StructuredKnowledgeDocument) -> int:
        """
        将单个结构化知识文档切块并写入长期记忆。
        document: 由 frontmatter_bootstrap 生成的结构化知识文档。
        """

        total_chunks = 0
        for section in document.sections:
            chunk_inputs = chunk_text(
                text=section.content,
                chunk_size=self.config.memory.chunk_size,
                chunk_overlap=self.config.memory.chunk_overlap,
            )
            if not chunk_inputs:
                continue
            chunk_contents = [
                self._build_chunk_content(
                    document=document,
                    section_heading=section.heading,
                    chunk_text=chunk_input.content,
                )
                for chunk_input in chunk_inputs
            ]
            logger.debug("    Embedding %d chunks for '%s'...", len(chunk_contents), section.heading)
            vectors = self.embedding_service.embed_texts(chunk_contents)
            for chunk_input, chunk_content, vector in zip(chunk_inputs, chunk_contents, vectors, strict=True):
                self.memory_service.create_memory(
                    LongTermMemorySpecCreate(
                        user_id="system",
                        session_id=None,
                        tag=self.config.constants.knowledge_tag,
                        memory_type="knowledge_chunk",
                        content=chunk_content,
                        source_type=document.source_type,
                        source_id=document.document_id,
                        source_uri=document.source_uri,
                        source_hash=document.source_hash,
                        source_range_json={
                            "section_id": section.section_id,
                            "chunk_index": chunk_input.index,
                            "section_start_char": section.start_char,
                            "section_end_char": section.end_char,
                            "chunk_start_char": chunk_input.start_char,
                            "chunk_end_char": chunk_input.end_char,
                        },
                        metadata_json={
                            "title": document.title,
                            "summary": document.summary,
                            "tags": document.tags,
                            "section_heading": section.heading,
                            "title_path": section.title_path,
                            **document.metadata,
                        },
                        valid_from=self._parse_optional_datetime(document.valid_from),
                        valid_until=self._parse_optional_datetime(document.valid_until),
                        confidence=1.0,
                        importance=0.5,
                        authority=document.authority,
                        embedding_model=self.config.model.embedding_model_name,
                        embedding_vector_json=vector,
                    )
                )
                total_chunks += 1
        return total_chunks

    @staticmethod
    def _build_chunk_content(
        *,
        document: StructuredKnowledgeDocument,
        section_heading: str,
        chunk_text: str,
    ) -> str:
        """
        组合真正参与检索和入库的知识片文本。
        document: 结构化知识文档。
        section_heading: 当前章节标题。
        chunk_text: 当前 chunk 正文。
        """

        title_line = f"文档标题: {document.title}"
        section_line = f"章节标题: {section_heading}"
        return f"{title_line}\n{section_line}\n\n{chunk_text}".strip()

    @staticmethod
    def _parse_optional_datetime(value: str | None) -> datetime | None:
        """
        解析 frontmatter 中的 ISO 时间字符串。
        value: 结构化知识文档中的时间字符串。
        """

        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    @staticmethod
    def _load_document(frontmatter_path: Path) -> StructuredKnowledgeDocument:
        """
        从结构化知识 JSON 文件加载统一文档对象。
        frontmatter_path: 结构化知识 JSON 文件路径。
        """

        payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        return StructuredKnowledgeDocument.from_dict(payload)

    @staticmethod
    def _iter_frontmatter_files(frontmatter_dir: Path) -> list[Path]:
        """
        扫描可入库的结构化知识 JSON。
        frontmatter_dir: 结构化知识文档根目录。
        """

        if not frontmatter_dir.exists():
            return []
        return sorted(path for path in frontmatter_dir.rglob("*.json") if path.is_file())
