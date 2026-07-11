"""
知识源结构化文档模块。
功能说明:
本文件定义知识库预处理阶段使用的统一文档结构。`frontmatter_bootstrap` 会把原始 Markdown、TXT
等知识源先转换成这里定义的结构化 JSON,再由 `knowledge_bootstrap` 读取这些 JSON 执行切块、
Embedding 和向量入库。这样可以把“理解原始文档格式”和“灌库”两个职责拆开。
使用说明:
预处理层使用 `StructuredKnowledgeDocument.to_dict()` 输出 JSON,灌库层使用
`StructuredKnowledgeDocument.from_dict()` 读取 JSON。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class StructuredKnowledgeSection:
    """
    结构化知识章节。
    section_id: 当前章节的稳定标识,用于切片溯源。
    heading: 当前章节标题。
    title_path: 章节的层级标题路径,用于保留 Markdown 标题语义。
    content: 当前章节正文内容。
    start_char: 章节在源正文中的起始字符位置。
    end_char: 章节在源正文中的结束字符位置。
    """

    section_id: str
    heading: str
    title_path: list[str]
    content: str
    start_char: int
    end_char: int


@dataclass(slots=True)
class StructuredKnowledgeDocument:
    """
    结构化知识文档。
    document_id: 文档稳定标识,通常由原始相对路径推导。
    source_type: 原始知识源类型,例如 markdown 或 text。
    source_path: 原始知识源绝对路径。
    source_uri: 可溯源来源 URI,优先使用 frontmatter 提供的外部来源。
    source_hash: 原始知识源内容哈希,用于文件级去重。
    title: 文档标题。
    summary: 文档级摘要,当前阶段可为空字符串。
    tags: 文档标签列表。
    authority: 文档权威性分数。
    valid_from: 文档生效时间的 ISO 字符串,可为空。
    valid_until: 文档失效时间的 ISO 字符串,可为空。
    metadata: 结构化预处理阶段保留的扩展元数据。
    sections: 文档章节列表,后续灌库仅处理这些结构化章节。
    """

    document_id: str
    source_type: str
    source_path: str
    source_uri: str
    source_hash: str
    title: str
    summary: str
    tags: list[str]
    authority: float
    valid_from: str | None
    valid_until: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[StructuredKnowledgeSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """将结构化知识文档转换为可序列化字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StructuredKnowledgeDocument":
        """
        从 JSON 字典恢复结构化知识文档。
        payload: `frontmatter_bootstrap` 输出的结构化文档字典。
        """

        sections = [
            StructuredKnowledgeSection(
                section_id=str(section["section_id"]),
                heading=str(section["heading"]),
                title_path=[str(item) for item in section.get("title_path", [])],
                content=str(section["content"]),
                start_char=int(section.get("start_char", 0)),
                end_char=int(section.get("end_char", 0)),
            )
            for section in payload.get("sections", [])
        ]
        return cls(
            document_id=str(payload["document_id"]),
            source_type=str(payload["source_type"]),
            source_path=str(payload["source_path"]),
            source_uri=str(payload["source_uri"]),
            source_hash=str(payload["source_hash"]),
            title=str(payload["title"]),
            summary=str(payload.get("summary", "")),
            tags=[str(item) for item in payload.get("tags", [])],
            authority=float(payload.get("authority", 0.7)),
            valid_from=str(payload["valid_from"]) if payload.get("valid_from") else None,
            valid_until=str(payload["valid_until"]) if payload.get("valid_until") else None,
            metadata=dict(payload.get("metadata", {})),
            sections=sections,
        )
