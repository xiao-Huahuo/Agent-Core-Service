"""
知识源结构化预处理服务。
功能说明:
本文件负责把 `resources/knowledge` 下的原始 Markdown、TXT 文档转换为统一的结构化知识 JSON,
输出到 `runtime/frontmatter`。它只做文档理解、元数据拆分和章节结构化,不负责切块、Embedding
或入库。后续 `knowledge_bootstrap` 只消费这里生成的 JSON。
使用说明:
service = FrontmatterBootstrapService(config=config)
result = service.build_frontmatter_dir()
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_service.core.agent_config import AgentConfig

logger = logging.getLogger(__name__)
from agent_service.services.memory.rag.frontmatter_document import (
    StructuredKnowledgeDocument,
    StructuredKnowledgeSection,
)
from agent_service.services.memory.rag.image_ocr import ImageOcrService
from agent_service.services.memory.rag.multimodal_cleaner import MultimodalDocumentCleaner


@dataclass(slots=True)
class FrontmatterBootstrapResult:
    """
    结构化预处理结果。
    files_seen: 扫描到的原始知识文件数量。
    files_written: 实际写出的结构化 JSON 数量。
    files_skipped: 因内容未变化而跳过覆写的结构化 JSON 数量。
    """

    files_seen: int = 0
    files_written: int = 0
    files_skipped: int = 0


class FrontmatterBootstrapService:
    """
    原始知识源结构化服务。
    config: 全局配置对象,用于读取原始知识目录和结构化输出目录。
    """

    def __init__(self, *, config: AgentConfig, ocr_enabled: bool | None = None) -> None:
        """初始化原始知识源结构化服务。"""

        self.config = config
        self.ocr_enabled = config.ocr.enabled if ocr_enabled is None else bool(ocr_enabled)
        self.multimodal_cleaner = MultimodalDocumentCleaner(
            ocr_enabled=self.ocr_enabled,
            image_ocr_service=ImageOcrService(config=config) if self.ocr_enabled else None,
        )

    def build_frontmatter_dir(
        self,
        *,
        knowledge_dir: Path | None = None,
        frontmatter_dir: Path | None = None,
        supported_suffixes: set[str] | None = None,
        exclude_path: Callable[[Path], bool] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> FrontmatterBootstrapResult:
        """
        扫描原始知识目录并输出结构化 JSON。
        knowledge_dir: 可选原始知识库目录;为空时使用全局配置。
        frontmatter_dir: 可选结构化输出目录;为空时使用全局配置。
        supported_suffixes: 可选文件后缀白名单;为 None 时使用 {".md", ".txt"}。
        返回值仅描述结构化阶段,不包含后续灌库统计。
        """

        source_root = knowledge_dir or self.config.storage.knowledge_dir
        output_root = frontmatter_dir or self.config.storage.frontmatter_dir
        suffixes = supported_suffixes or set(self.config.constants.knowledge_supported_suffixes)
        result = FrontmatterBootstrapResult()
        source_files = [
            path for path in self._iter_source_files(source_root, suffixes)
            if not (exclude_path and exclude_path(path))
        ]
        logger.info("Frontmatter 结构化开始 | 扫描到 %d 个文件", len(source_files))
        total = len(source_files)
        for source_path in source_files:
            result.files_seen += 1
            rel_path = source_path.relative_to(source_root)
            self._emit_progress(
                progress_callback,
                status="started",
                source_path=source_path,
                relative_path=rel_path,
                processed=result.files_seen - 1,
                total=total,
                result=result,
            )
            try:
                source_hash = self._hash_file(source_path)
                document = self._build_document(
                    source_path=source_path,
                    source_hash=source_hash,
                    knowledge_dir=source_root,
                )
                output_path = self._resolve_output_path(
                    source_path=source_path,
                    knowledge_dir=source_root,
                    frontmatter_dir=output_root,
                )
                output_payload = json.dumps(document.to_dict(), ensure_ascii=False, indent=2)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.exists() and output_path.read_text(encoding="utf-8") == output_payload:
                    result.files_skipped += 1
                    self._emit_progress(
                        progress_callback,
                        status="skipped",
                        source_path=source_path,
                        relative_path=rel_path,
                        processed=result.files_seen,
                        total=total,
                        result=result,
                        message="frontmatter unchanged",
                    )
                    logger.debug("  [跳过] %s (未变更)", rel_path)
                    continue
                output_path.write_text(output_payload, encoding="utf-8")
                result.files_written += 1
                self._emit_progress(
                    progress_callback,
                    status="written",
                    source_path=source_path,
                    relative_path=rel_path,
                    processed=result.files_seen,
                    total=total,
                    result=result,
                    sections=len(document.sections),
                )
                logger.info("  [写入] %s → %d sections", rel_path, len(document.sections))
            except Exception as exc:
                result.files_skipped += 1
                self._emit_progress(
                    progress_callback,
                    status="failed",
                    source_path=source_path,
                    relative_path=rel_path,
                    processed=result.files_seen,
                    total=total,
                    result=result,
                    message=str(exc),
                )
                logger.warning("  [跳过] %s (结构化失败: %s)", rel_path, exc)
        logger.info(
            "Frontmatter 结构化完成 | %d 文件: %d 写入, %d 跳过",
            result.files_seen,
            result.files_written,
            result.files_skipped,
        )
        return result

    def build_frontmatter_file(
        self,
        *,
        source_path: Path,
        knowledge_dir: Path | None = None,
        frontmatter_dir: Path | None = None,
        supported_suffixes: set[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[FrontmatterBootstrapResult, Path]:
        """
        只结构化单个源文件。

        source_path: 原始知识文件绝对路径或相对路径。
        knowledge_dir: 当前知识库根目录。
        frontmatter_dir: 结构化 JSON 输出根目录。
        supported_suffixes: 可灌库后缀白名单。
        """

        source_root = (knowledge_dir or self.config.storage.knowledge_dir).resolve()
        output_root = frontmatter_dir or self.config.storage.frontmatter_dir
        suffixes = supported_suffixes or set(self.config.constants.knowledge_supported_suffixes)
        resolved_source = source_path.expanduser().resolve()
        result = FrontmatterBootstrapResult(files_seen=1)
        if not resolved_source.is_file():
            raise ValueError("source file not found")
        if resolved_source.suffix.lower() not in suffixes:
            raise ValueError(f"unsupported knowledge file suffix: {resolved_source.suffix.lower()}")
        try:
            relative_path = resolved_source.relative_to(source_root)
        except ValueError as exc:
            raise ValueError("source file escapes knowledge_dir") from exc
        self._emit_progress(
            progress_callback,
            status="started",
            source_path=resolved_source,
            relative_path=relative_path,
            processed=0,
            total=1,
            result=result,
        )

        source_hash = self._hash_file(resolved_source)
        document = self._build_document(
            source_path=resolved_source,
            source_hash=source_hash,
            knowledge_dir=source_root,
        )
        output_path = self._resolve_output_path(
            source_path=resolved_source,
            knowledge_dir=source_root,
            frontmatter_dir=output_root,
        )
        output_payload = json.dumps(document.to_dict(), ensure_ascii=False, indent=2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and output_path.read_text(encoding="utf-8") == output_payload:
            result.files_skipped = 1
            self._emit_progress(
                progress_callback,
                status="skipped",
                source_path=resolved_source,
                relative_path=relative_path,
                processed=1,
                total=1,
                result=result,
                message="frontmatter unchanged",
            )
            return result, output_path
        output_path.write_text(output_payload, encoding="utf-8")
        result.files_written = 1
        self._emit_progress(
            progress_callback,
            status="written",
            source_path=resolved_source,
            relative_path=relative_path,
            processed=1,
            total=1,
            result=result,
            sections=len(document.sections),
        )
        return result, output_path

    @staticmethod
    def _emit_progress(
        progress_callback: Callable[[dict[str, Any]], None] | None,
        *,
        status: str,
        source_path: Path,
        relative_path: Path,
        processed: int,
        total: int,
        result: FrontmatterBootstrapResult,
        message: str = "",
        sections: int | None = None,
    ) -> None:
        if not progress_callback:
            return
        payload: dict[str, Any] = {
            "phase": "frontmatter",
            "status": status,
            "path": relative_path.as_posix(),
            "name": source_path.name,
            "processed": processed,
            "total": total,
            "files_written": result.files_written,
            "files_skipped": result.files_skipped,
        }
        if message:
            payload["message"] = message
        if sections is not None:
            payload["sections"] = sections
        progress_callback(payload)

    def _build_document(
        self,
        *,
        source_path: Path,
        source_hash: str,
        knowledge_dir: Path,
    ) -> StructuredKnowledgeDocument:
        """
        将单个原始知识文件转换为统一结构化文档。
        source_path: 原始知识文件路径。
        source_hash: 原始知识文件内容哈希。
        knowledge_dir: 当前知识库根目录。
        """

        metadata: dict[str, Any] = {}
        title = self._resolve_title(source_path=source_path, metadata=metadata)
        if source_path.suffix.lower() == ".md":
            raw_text = source_path.read_text(encoding="utf-8")
            metadata, body_text = self._extract_frontmatter(raw_text)
            title = self._resolve_title(source_path=source_path, metadata=metadata)
            sections = self._build_sections(source_path=source_path, title=title, body_text=body_text)
            source_type = self._resolve_source_type(source_path)
            extra_metadata: dict[str, Any] = {"modality": "document"}
            summary = str(metadata.get("summary") or "")
        elif source_path.suffix.lower() == ".txt":
            body_text = source_path.read_text(encoding="utf-8")
            sections = self._build_sections(source_path=source_path, title=title, body_text=body_text)
            source_type = self._resolve_source_type(source_path)
            extra_metadata = {"modality": "text"}
            summary = ""
        else:
            cleaned = self.multimodal_cleaner.clean(
                source_path=source_path,
                title=self._resolve_title(source_path=source_path, metadata=metadata),
            )
            sections = cleaned.sections
            source_type = cleaned.source_type
            extra_metadata = cleaned.metadata
            summary = cleaned.summary
        relative_path = source_path.relative_to(knowledge_dir)
        document_metadata = {
            "file_suffix": source_path.suffix.lower(),
            "relative_path": relative_path.as_posix(),
            "frontmatter": metadata,
            **extra_metadata,
            "ocr_enabled": self.ocr_enabled,
        }
        return StructuredKnowledgeDocument(
            document_id=self._build_document_id(relative_path),
            source_type=source_type,
            source_path=str(source_path),
            source_uri=str(metadata.get("source_uri") or source_path),
            source_hash=source_hash,
            title=title,
            summary=summary,
            tags=self._normalize_tags(metadata.get("tags")),
            authority=self._parse_float(metadata.get("authority"), default=0.7),
            valid_from=self._normalize_optional_string(metadata.get("valid_from")),
            valid_until=self._normalize_optional_string(metadata.get("valid_until")),
            metadata=document_metadata,
            sections=sections,
        )

    def _build_sections(
        self,
        *,
        source_path: Path,
        title: str,
        body_text: str,
    ) -> list[StructuredKnowledgeSection]:
        """
        根据原始文件类型提取结构化章节。
        source_path: 原始知识文件路径。
        title: 文档标题。
        body_text: frontmatter 剥离后的正文。
        """

        if source_path.suffix.lower() == ".md":
            return self._build_markdown_sections(title=title, body_text=body_text)
        return self._build_text_sections(title=title, body_text=body_text)

    @staticmethod
    def _build_markdown_sections(*, title: str, body_text: str) -> list[StructuredKnowledgeSection]:
        """
        从 Markdown 正文中提取标题层级和章节内容。
        title: 文档标题。
        body_text: 已去除 frontmatter 的 Markdown 正文。
        """

        sections: list[StructuredKnowledgeSection] = []
        heading_stack: list[tuple[int, str]] = []
        current_heading = title
        current_title_path = [title]
        current_start = 0
        current_content_lines: list[str] = []
        current_cursor = 0

        def flush_section(end_char: int) -> None:
            content = "".join(current_content_lines).strip()
            if not content:
                return
            section_index = len(sections)
            sections.append(
                StructuredKnowledgeSection(
                    section_id=f"sec_{section_index:04d}",
                    heading=current_heading,
                    title_path=list(current_title_path),
                    content=content,
                    start_char=current_start,
                    end_char=end_char,
                )
            )

        for raw_line in body_text.splitlines(keepends=True):
            heading_match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", raw_line.strip("\n"))
            if heading_match:
                flush_section(current_cursor)
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                heading_stack = [(stack_level, stack_heading) for stack_level, stack_heading in heading_stack if stack_level < level]
                heading_stack.append((level, heading_text))
                current_heading = heading_text
                current_title_path = [title, *[stack_heading for _, stack_heading in heading_stack]]
                current_content_lines = []
                current_start = current_cursor + len(raw_line)
                current_cursor += len(raw_line)
                continue
            current_content_lines.append(raw_line)
            current_cursor += len(raw_line)

        flush_section(current_cursor)
        if sections:
            return sections
        content = body_text.strip()
        if not content:
            return []
        return [
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading=title,
                title_path=[title],
                content=content,
                start_char=0,
                end_char=len(body_text),
            )
        ]

    @staticmethod
    def _build_text_sections(*, title: str, body_text: str) -> list[StructuredKnowledgeSection]:
        """
        从 TXT 正文中提取结构化章节。
        title: 文档标题。
        body_text: TXT 正文。
        """

        content = body_text.strip()
        if not content:
            return []
        return [
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading=title,
                title_path=[title],
                content=content,
                start_char=0,
                end_char=len(body_text),
            )
        ]

    @staticmethod
    def _extract_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
        """
        从 Markdown 中提取最前部 frontmatter。
        raw_text: 原始 Markdown 文本。
        """

        if not raw_text.startswith("---\n"):
            return {}, raw_text
        lines = raw_text.splitlines()
        end_index = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_index = index
                break
        if end_index is None:
            return {}, raw_text
        frontmatter_lines = lines[1:end_index]
        body_text = "\n".join(lines[end_index + 1 :])
        return FrontmatterBootstrapService._parse_frontmatter_lines(frontmatter_lines), body_text

    @staticmethod
    def _parse_frontmatter_lines(lines: list[str]) -> dict[str, Any]:
        """
        解析简单 YAML 风格 frontmatter。
        lines: frontmatter 正文行列表。
        """

        payload: dict[str, Any] = {}
        current_list_key: str | None = None
        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- ") and current_list_key:
                payload.setdefault(current_list_key, []).append(stripped[2:].strip())
                continue
            if ":" not in line:
                current_list_key = None
                continue
            key, value = line.split(":", 1)
            normalized_key = key.strip()
            normalized_value = value.strip()
            if not normalized_value:
                payload[normalized_key] = []
                current_list_key = normalized_key
                continue
            payload[normalized_key] = normalized_value
            current_list_key = None
        return payload

    @staticmethod
    def _resolve_title(*, source_path: Path, metadata: dict[str, Any]) -> str:
        """
        解析文档标题。
        source_path: 原始知识文件路径。
        metadata: frontmatter 元数据。
        """

        return str(metadata.get("title") or source_path.stem.replace("_", " ").strip())

    @staticmethod
    def _resolve_source_type(source_path: Path) -> str:
        """
        推断原始知识源类型。
        source_path: 原始知识文件路径。
        """

        if source_path.suffix.lower() == ".md":
            return "markdown"
        return "text"

    @staticmethod
    def _normalize_tags(raw_tags: Any) -> list[str]:
        """
        归一化 tags 字段。
        raw_tags: frontmatter 中的 tags 原始值。
        """

        if raw_tags is None:
            return []
        if isinstance(raw_tags, list):
            return [str(item).strip() for item in raw_tags if str(item).strip()]
        if isinstance(raw_tags, str):
            return [item.strip() for item in raw_tags.split(",") if item.strip()]
        return [str(raw_tags).strip()]

    @staticmethod
    def _normalize_optional_string(value: Any) -> str | None:
        """
        将可选值归一化为字符串或 None。
        value: 原始 frontmatter 值。
        """

        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _parse_float(value: Any, *, default: float) -> float:
        """
        解析浮点数字段。
        value: 原始 frontmatter 值。
        default: 解析失败时返回的默认值。
        """

        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _resolve_output_path(
        self,
        *,
        source_path: Path,
        knowledge_dir: Path,
        frontmatter_dir: Path,
    ) -> Path:
        """
        根据原始知识源路径计算结构化 JSON 输出路径。
        source_path: 原始知识文件路径。
        knowledge_dir: 当前知识库根目录。
        frontmatter_dir: 当前结构化输出目录。
        """

        relative_path = source_path.relative_to(knowledge_dir)
        return (frontmatter_dir / relative_path).with_suffix(".json")

    @staticmethod
    def _build_document_id(relative_path: Path) -> str:
        """
        根据相对路径构建稳定文档 ID。
        relative_path: 原始知识文件相对知识库根目录的路径。
        """

        normalized_path = relative_path.as_posix()
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", normalized_path).strip("_").lower()
        path_hash = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:12]
        if not slug:
            slug = "file"
        return f"doc_{slug}_{path_hash}"

    @staticmethod
    def _iter_source_files(knowledge_dir: Path, suffixes: set[str]) -> list[Path]:
        """
        扫描可结构化的原始知识文件。
        knowledge_dir: 原始知识库根目录。
        suffixes: 文件后缀白名单,例如 {".md", ".txt"}。
                  请确保与 AgentConfig.constants.knowledge_supported_suffixes 保持一致;
                  添加新格式(如 .pdf)时需在此处加入对应的文档解析分支。
        """

        if not knowledge_dir.exists():
            return []
        return sorted(
            path
            for path in knowledge_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in suffixes
        )

    @staticmethod
    def _hash_file(source_path: Path) -> str:
        """
        计算原始知识文件内容哈希。
        source_path: 原始知识文件路径。
        """

        digest = hashlib.sha256()
        digest.update(source_path.read_bytes())
        return digest.hexdigest()
