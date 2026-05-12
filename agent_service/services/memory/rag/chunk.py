"""
RAG 文本切片工具。

功能说明:
本文件提供知识库和摘要入库前的轻量切片能力。第一版不做复杂语义解析,
而是按段落优先、固定窗口兜底的方式生成重叠 chunk,用于后续 Embedding 和
pgvector 入库。

使用说明:
业务层调用 `chunk_text(text=..., chunk_size=..., chunk_overlap=...)` 获取
`TextChunk` 列表。chunk 的 `start_char` 和 `end_char` 用于写入长期记忆的
`source_range_json`,保证知识库记忆可以回溯到原始文件位置。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TextChunk:
    """
    文本切片结构。

    index: 当前切片在原文中的顺序。
    content: 切片正文。
    start_char: 切片在原文中的起始字符位置。
    end_char: 切片在原文中的结束字符位置。
    """

    index: int
    content: str
    start_char: int
    end_char: int


def chunk_text(*, text: str, chunk_size: int, chunk_overlap: int) -> list[TextChunk]:
    """
    将文本切成带重叠窗口的 chunk。

    text: 原始文本。
    chunk_size: 每个切片目标字符数。
    chunk_overlap: 相邻切片重叠字符数。
    """

    normalized_text = text.strip()
    if not normalized_text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0。")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap 不能小于 0。")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size。")

    chunks: list[TextChunk] = []
    cursor = 0
    index = 0
    text_length = len(normalized_text)
    while cursor < text_length:
        end = min(cursor + chunk_size, text_length)
        if end < text_length:
            paragraph_break = normalized_text.rfind("\n\n", cursor, end)
            if paragraph_break > cursor + max(80, chunk_size // 3):
                end = paragraph_break
        content = normalized_text[cursor:end].strip()
        if content:
            chunks.append(TextChunk(index=index, content=content, start_char=cursor, end_char=end))
            index += 1
        if end >= text_length:
            break
        cursor = max(end - chunk_overlap, cursor + 1)
    return chunks
