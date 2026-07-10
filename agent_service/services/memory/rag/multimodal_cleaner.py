"""
多模态知识源清洗模块。

功能说明:
本文件将 Markdown/TXT 之外的常见知识库文件清洗为统一章节文本,供
`frontmatter_bootstrap` 写入 StructuredKnowledgeDocument。第一版只使用 Python
标准库,优先保证离线可运行和灌库链路稳定;OCR、视觉描述和高级表格识别可在本模块
内替换为更强解析器,不会影响后续切块和向量入库。

使用说明:
cleaner = MultimodalDocumentCleaner()
result = cleaner.clean(source_path=Path("demo.docx"), title="demo")
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeSection


@dataclass(slots=True)
class CleanedDocument:
    """
    多模态清洗后的文档。

    source_type: 原始文件类型。
    sections: 可直接进入 StructuredKnowledgeDocument 的章节列表。
    metadata: 清洗阶段生成的扩展元数据。
    summary: 可选文档摘要,第一版默认为空。
    """

    source_type: str
    sections: list[StructuredKnowledgeSection]
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class _HtmlTextExtractor(HTMLParser):
    """轻量 HTML 正文提取器,忽略 script/style 并保留块级换行。"""

    _block_tags = {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        """初始化 HTML 解析状态。"""

        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """记录块级标签换行,并跳过脚本和样式内容。"""

        _ = attrs
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if tag in self._block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """结束块级标签时补充换行。"""

        if tag in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """追加正文文本。"""

        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        """返回规整后的 HTML 文本。"""

        return _normalize_text(" ".join(self.parts))


class MultimodalDocumentCleaner:
    """
    多模态文件清洗器。

    max_table_rows: 表格类文件最多写入语义索引的样例行数。
    """

    def __init__(self, *, max_table_rows: int = 80) -> None:
        """保存清洗参数。"""

        self.max_table_rows = max_table_rows

    def clean(self, *, source_path: Path, title: str) -> CleanedDocument:
        """
        按文件后缀清洗知识源。

        source_path: 原始文件路径。
        title: 上层解析得到的文档标题。
        """

        suffix = source_path.suffix.lower()
        if suffix == ".json":
            return self._clean_json(source_path=source_path, title=title)
        if suffix == ".jsonl":
            return self._clean_jsonl(source_path=source_path, title=title)
        if suffix in {".csv", ".tsv"}:
            return self._clean_delimited_table(source_path=source_path, title=title, delimiter="\t" if suffix == ".tsv" else ",")
        if suffix in {".html", ".htm"}:
            return self._clean_html(source_path=source_path, title=title)
        if suffix == ".xml":
            return self._clean_xml(source_path=source_path, title=title)
        if suffix == ".docx":
            return self._clean_docx(source_path=source_path, title=title)
        if suffix == ".xlsx":
            return self._clean_xlsx(source_path=source_path, title=title)
        if suffix == ".pptx":
            return self._clean_pptx(source_path=source_path, title=title)
        if suffix == ".pdf":
            return self._clean_binary_placeholder(source_path=source_path, title=title, source_type="pdf")
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            return self._clean_binary_placeholder(source_path=source_path, title=title, source_type="image")
        return self._clean_binary_placeholder(source_path=source_path, title=title, source_type="asset")

    def _clean_json(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 JSON 清洗为格式化文本章节。"""

        payload = json.loads(source_path.read_text(encoding="utf-8"))
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        return _single_section_document(source_type="json", title=title, content=content, metadata={"modality": "structured_data"})

    def _clean_jsonl(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 JSONL 每行对象清洗为结构化样例文本。"""

        rows: list[str] = []
        for index, line in enumerate(source_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(f"row {index}: {json.dumps(json.loads(line), ensure_ascii=False)}")
            except json.JSONDecodeError:
                rows.append(f"row {index}: {line.strip()}")
            if len(rows) >= self.max_table_rows:
                break
        return _single_section_document(
            source_type="jsonl",
            title=title,
            content="\n".join(rows),
            metadata={"modality": "structured_data", "sample_rows": len(rows)},
        )

    def _clean_delimited_table(self, *, source_path: Path, title: str, delimiter: str) -> CleanedDocument:
        """将 CSV/TSV 清洗为保留表头和样例行的表格章节。"""

        rows: list[list[str]] = []
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            for row in reader:
                rows.append([cell.strip() for cell in row])
                if len(rows) >= self.max_table_rows + 1:
                    break
        content = _format_table_rows(rows)
        header = rows[0] if rows else []
        return _single_section_document(
            source_type="table",
            title=title,
            content=content,
            metadata={"modality": "table", "columns": header, "sample_rows": max(0, len(rows) - 1)},
        )

    def _clean_html(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 HTML 清洗为可检索正文。"""

        parser = _HtmlTextExtractor()
        parser.feed(source_path.read_text(encoding="utf-8"))
        return _single_section_document(source_type="html", title=title, content=parser.text(), metadata={"modality": "document"})

    def _clean_xml(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 XML 清洗为节点路径和值的文本摘要。"""

        root = ElementTree.fromstring(source_path.read_text(encoding="utf-8"))
        lines: list[str] = []

        def visit(node: ElementTree.Element, path: list[str]) -> None:
            node_path = [*path, _local_name(node.tag)]
            text = _normalize_text(node.text or "")
            if text:
                lines.append(f"{'/'.join(node_path)}: {text}")
            for child in list(node):
                visit(child, node_path)

        visit(root, [])
        return _single_section_document(source_type="xml", title=title, content="\n".join(lines), metadata={"modality": "structured_data"})

    def _clean_docx(self, *, source_path: Path, title: str) -> CleanedDocument:
        """从 DOCX 中抽取段落、表格文本和图片引用。"""

        sections: list[StructuredKnowledgeSection] = []
        with zipfile.ZipFile(source_path) as archive:
            document_xml = _read_zip_text(archive, "word/document.xml")
            if not document_xml:
                return _single_section_document(source_type="docx", title=title, content="", metadata={"modality": "document"})
            root = ElementTree.fromstring(document_xml)
            paragraph_lines: list[str] = []
            table_index = 0
            image_refs: list[str] = []
            for element in root.iter():
                name = _local_name(element.tag)
                if name == "p":
                    text = _join_text_nodes(element)
                    if text:
                        paragraph_lines.append(text)
                    image_refs.extend(_collect_relationship_ids(element))
                elif name == "tbl":
                    rows = _extract_docx_table(element)
                    if rows:
                        table_index += 1
                        sections.append(_make_section(index=len(sections), heading=f"{title} 表格 {table_index}", content=_format_table_rows(rows)))
            if paragraph_lines:
                sections.insert(0, _make_section(index=0, heading=title, content="\n\n".join(paragraph_lines)))
                sections = _renumber_sections(sections)
            if image_refs:
                sections.append(_make_section(index=len(sections), heading=f"{title} 图片引用", content="\n".join(f"image relationship: {item}" for item in image_refs)))
        return CleanedDocument(source_type="docx", sections=sections, metadata={"modality": "document", "image_refs": image_refs})

    def _clean_xlsx(self, *, source_path: Path, title: str) -> CleanedDocument:
        """从 XLSX 中抽取工作表样例行。"""

        sections: list[StructuredKnowledgeSection] = []
        with zipfile.ZipFile(source_path) as archive:
            shared_strings = _read_xlsx_shared_strings(archive)
            sheet_paths = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
            for sheet_index, sheet_path in enumerate(sheet_paths, start=1):
                rows = _extract_xlsx_rows(archive=archive, sheet_path=sheet_path, shared_strings=shared_strings, max_rows=self.max_table_rows)
                if not rows:
                    continue
                heading = f"{title} Sheet {sheet_index}"
                sections.append(_make_section(index=len(sections), heading=heading, content=_format_table_rows(rows)))
        return CleanedDocument(source_type="spreadsheet", sections=sections, metadata={"modality": "table", "sheet_count": len(sections)})

    def _clean_pptx(self, *, source_path: Path, title: str) -> CleanedDocument:
        """从 PPTX 中按 slide 抽取文本。"""

        sections: list[StructuredKnowledgeSection] = []
        with zipfile.ZipFile(source_path) as archive:
            slide_paths = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
            for slide_index, slide_path in enumerate(slide_paths, start=1):
                xml_text = _read_zip_text(archive, slide_path)
                if not xml_text:
                    continue
                text = _normalize_text("\n".join(ElementTree.fromstring(xml_text).itertext()))
                if text:
                    sections.append(_make_section(index=len(sections), heading=f"{title} Slide {slide_index}", content=text))
        return CleanedDocument(source_type="presentation", sections=sections, metadata={"modality": "slide", "slide_count": len(sections)})

    def _clean_binary_placeholder(self, *, source_path: Path, title: str, source_type: str) -> CleanedDocument:
        """为 PDF/图片等待 OCR 的二进制文件生成轻量元信息章节。"""

        stat = source_path.stat()
        content = (
            f"文件名: {source_path.name}\n"
            f"文件类型: {source_path.suffix.lower()}\n"
            f"文件大小: {stat.st_size} bytes\n"
            "状态: 已登记为多模态资产,当前版本尚未启用 OCR/视觉描述。"
        )
        return _single_section_document(
            source_type=source_type,
            title=title,
            content=content,
            metadata={"modality": source_type, "ocr_status": "pending", "file_size": stat.st_size},
        )


def _single_section_document(*, source_type: str, title: str, content: str, metadata: dict[str, Any]) -> CleanedDocument:
    """构建单章节清洗结果。"""

    section = _make_section(index=0, heading=title, content=content)
    return CleanedDocument(source_type=source_type, sections=[section] if content.strip() else [], metadata=metadata)


def _make_section(*, index: int, heading: str, content: str) -> StructuredKnowledgeSection:
    """构建一个结构化章节。"""

    normalized = content.strip()
    return StructuredKnowledgeSection(
        section_id=f"sec_{index:04d}",
        heading=heading,
        title_path=[heading],
        content=normalized,
        start_char=0,
        end_char=len(normalized),
    )


def _renumber_sections(sections: list[StructuredKnowledgeSection]) -> list[StructuredKnowledgeSection]:
    """按当前位置重写 section_id,避免插入段落后 ID 重复。"""

    return [
        StructuredKnowledgeSection(
            section_id=f"sec_{index:04d}",
            heading=section.heading,
            title_path=section.title_path,
            content=section.content,
            start_char=section.start_char,
            end_char=section.end_char,
        )
        for index, section in enumerate(sections)
    ]


def _format_table_rows(rows: list[list[str]]) -> str:
    """将表格行转换为 Markdown 风格文本,保留列语义。"""

    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    lines = [" | ".join(row).strip() for row in padded]
    return "\n".join(line for line in lines if line)


def _read_zip_text(archive: zipfile.ZipFile, name: str) -> str:
    """从 zip 容器读取 UTF-8 XML 文本,不存在时返回空字符串。"""

    try:
        return archive.read(name).decode("utf-8", errors="ignore")
    except KeyError:
        return ""


def _local_name(tag: str) -> str:
    """去掉 XML namespace,返回本地标签名。"""

    return tag.rsplit("}", 1)[-1]


def _normalize_text(text: str) -> str:
    """压缩多余空白并保留段落换行。"""

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _join_text_nodes(element: ElementTree.Element) -> str:
    """连接一个 OOXML 节点下的文本内容。"""

    return _normalize_text("".join(element.itertext()))


def _collect_relationship_ids(element: ElementTree.Element) -> list[str]:
    """收集 OOXML 图片等对象使用的关系 ID。"""

    ids: list[str] = []
    for node in element.iter():
        for key, value in node.attrib.items():
            if _local_name(key) in {"embed", "link"} and value:
                ids.append(value)
    return ids


def _extract_docx_table(table: ElementTree.Element) -> list[list[str]]:
    """从 DOCX 表格节点抽取行列文本。"""

    rows: list[list[str]] = []
    for row in table:
        if _local_name(row.tag) != "tr":
            continue
        cells: list[str] = []
        for cell in row:
            if _local_name(cell.tag) == "tc":
                cells.append(_join_text_nodes(cell))
        if any(cells):
            rows.append(cells)
    return rows


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """读取 XLSX sharedStrings 表。"""

    xml_text = _read_zip_text(archive, "xl/sharedStrings.xml")
    if not xml_text:
        return []
    root = ElementTree.fromstring(xml_text)
    return [_normalize_text("".join(item.itertext())) for item in root if _local_name(item.tag) == "si"]


def _extract_xlsx_rows(
    *,
    archive: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
    max_rows: int,
) -> list[list[str]]:
    """从 XLSX 工作表 XML 抽取样例行。"""

    root = ElementTree.fromstring(_read_zip_text(archive, sheet_path))
    rows: list[list[str]] = []
    for row in root.iter():
        if _local_name(row.tag) != "row":
            continue
        values: list[str] = []
        for cell in row:
            if _local_name(cell.tag) != "c":
                continue
            values.append(_xlsx_cell_value(cell=cell, shared_strings=shared_strings))
        if any(values):
            rows.append(values)
        if len(rows) >= max_rows:
            break
    return rows


def _xlsx_cell_value(*, cell: ElementTree.Element, shared_strings: list[str]) -> str:
    """解析 XLSX 单元格文本。"""

    cell_type = cell.attrib.get("t")
    value = ""
    for child in cell:
        if _local_name(child.tag) == "v":
            value = child.text or ""
            break
        if _local_name(child.tag) == "is":
            value = "".join(child.itertext())
            break
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    return value
