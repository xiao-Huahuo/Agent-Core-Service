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
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeSection
from agent_service.services.memory.rag.image_ocr import ImageOcrService
from agent_service.services.memory.rag.pdf_cleaner import extract_pdf_text


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

    def __init__(
        self,
        *,
        max_table_rows: int = 80,
        ocr_enabled: bool = False,
        image_ocr_service: ImageOcrService | None = None,
    ) -> None:
        """保存清洗参数。"""

        self.max_table_rows = max_table_rows
        self.ocr_enabled = ocr_enabled
        self.image_ocr_service = image_ocr_service

    def clean(
        self,
        *,
        source_path: Path,
        title: str,
        asset_output_dir: Path | None = None,
        asset_public_prefix: str = "",
    ) -> CleanedDocument:
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
            return self._clean_pdf(
                source_path=source_path,
                title=title,
                asset_output_dir=asset_output_dir,
                asset_public_prefix=asset_public_prefix,
            )
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return self._clean_image(source_path=source_path, title=title)
        return self._clean_binary_placeholder(source_path=source_path, title=title, source_type="asset")

    def _clean_json(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 JSON 清洗为格式化文本章节。"""

        payload = json.loads(_read_text_with_fallback(source_path))
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        return _single_section_document(source_type="json", title=title, content=content, metadata={"modality": "structured_data"})

    def _clean_jsonl(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 JSONL 每行对象清洗为结构化样例文本。"""

        rows: list[str] = []
        for index, line in enumerate(_read_text_with_fallback(source_path).splitlines(), start=1):
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
        with _open_text_with_fallback(source_path, newline="") as handle:
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
        parser.feed(_read_text_with_fallback(source_path))
        return _single_section_document(source_type="html", title=title, content=parser.text(), metadata={"modality": "document"})

    def _clean_xml(self, *, source_path: Path, title: str) -> CleanedDocument:
        """将 XML 清洗为节点路径和值的文本摘要。"""

        root = ElementTree.fromstring(_read_text_with_fallback(source_path))
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
        """从 DOCX 中按文档流顺序抽取段落、标题、表格文本与图片引用。

        只遍历 w:body 的直接子元素而非整棵 document.xml:表格单元格内部的
        w:p 不会被重复计入段落流,段落与表格的原文交替顺序得以保留;带
        Heading1-6 样式时按标题层级切分章节,否则段落聚成单章节。图片引用
        通过 word/_rels/document.xml.rels 解析为真实媒体路径。
        """

        sections: list[StructuredKnowledgeSection] = []
        with zipfile.ZipFile(source_path) as archive:
            document_xml = _read_zip_text(archive, "word/document.xml")
            if not document_xml:
                return _single_section_document(source_type="docx", title=title, content="", metadata={"modality": "document"})
            root = ElementTree.fromstring(document_xml)
            body = _find_body(root)
            if body is None:
                return _single_section_document(source_type="docx", title=title, content="", metadata={"modality": "document"})
            rels_map = _read_docx_relationship_map(archive)
            blocks, image_refs = _extract_docx_blocks(body=body, title=title, rels_map=rels_map)
            if any(kind == "h" for kind, *_ in blocks):
                sections = _build_docx_heading_sections(blocks=blocks, title=title)
            else:
                sections = _build_docx_flat_sections(blocks=blocks, title=title)
        return CleanedDocument(
            source_type="docx",
            sections=sections,
            metadata={"modality": "document", "image_refs": image_refs, "ocr_enabled": self.ocr_enabled},
        )

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

    def _clean_pdf(
        self,
        *,
        source_path: Path,
        title: str,
        asset_output_dir: Path | None = None,
        asset_public_prefix: str = "",
    ) -> CleanedDocument:
        """优先从非扫描型 PDF 提取文本层;扫描型 PDF 暂登记为待 OCR。"""

        try:
            extracted = extract_pdf_text(
                source_path,
                image_output_dir=asset_output_dir,
                image_public_prefix=asset_public_prefix,
            )
        except Exception:
            return self._clean_binary_placeholder(source_path=source_path, title=title, source_type="pdf")
        metadata = {
            "modality": "document",
            "ocr_enabled": self.ocr_enabled,
            "pdf_scanned": extracted.is_scanned,
            "page_count": extracted.page_count,
            "image_count": extracted.image_count,
            "image_refs": extracted.image_refs,
            "table_count": extracted.table_count,
            "ocr_status": "pending" if extracted.is_scanned else "not_required",
        }
        if not extracted.content.strip():
            return _single_section_document(
                source_type="pdf",
                title=title,
                content=(
                    f"文件名: {source_path.name}\n"
                    f"文件类型: {source_path.suffix.lower()}\n"
                    f"页数: {extracted.page_count}\n"
                    "状态: 未检测到可用文本层,需要 OCR 后才能提取正文。"
                ),
                metadata=metadata,
            )
        return _single_section_document(
            source_type="pdf",
            title=title,
            content=extracted.content,
            metadata=metadata,
        )

    def _clean_image(self, *, source_path: Path, title: str) -> CleanedDocument:
        """对普通图片执行 OCR,无文本时仅登记为图片资产。"""

        if not self.image_ocr_service:
            return self._clean_binary_placeholder(source_path=source_path, title=title, source_type="image")
        result = self.image_ocr_service.extract_image_text(source_path)
        metadata = {
            "modality": "image",
            "ocr_enabled": self.ocr_enabled,
            "ocr_status": "completed" if result.has_text else ("no_text" if result.engine_available else "engine_unavailable"),
            "ocr_engine_available": result.engine_available,
            "ocr_word_count": result.word_count,
            "ocr_average_confidence": result.average_confidence,
            "file_size": source_path.stat().st_size,
        }
        if not result.has_text:
            return CleanedDocument(source_type="image", sections=[], metadata=metadata)
        return _single_section_document(
            source_type="image",
            title=title,
            content=result.content,
            metadata=metadata,
        )

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
            metadata={
                "modality": source_type,
                "ocr_enabled": self.ocr_enabled,
                "ocr_status": "pending",
                "file_size": stat.st_size,
            },
        )


def _single_section_document(*, source_type: str, title: str, content: str, metadata: dict[str, Any]) -> CleanedDocument:
    """构建单章节清洗结果。"""

    section = _make_section(index=0, heading=title, content=content)
    return CleanedDocument(source_type=source_type, sections=[section] if content.strip() else [], metadata=metadata)


def _read_text_with_fallback(path: Path) -> str:
    """按常见编码读取文本文件,避免 GBK/UTF-8-SIG CSV 阻断整轮灌库。"""

    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _open_text_with_fallback(path: Path, *, newline: str | None = None) -> io.StringIO:
    """以 fallback 编码打开文本文件,用于 csv.reader 这类需要 file object 的解析器。"""

    _ = newline
    return io.StringIO(_read_text_with_fallback(path))


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


def _find_body(root: ElementTree.Element) -> ElementTree.Element | None:
    """定位 w:document 下的 w:body 节点,用于按文档流顺序遍历块级元素。"""

    for child in root:
        if _local_name(child.tag) == "body":
            return child
    return None


def _attr_text(element: ElementTree.Element, local_name: str) -> str:
    """按本地名读取 XML 属性值,兼容带/不带命名空间前缀的属性。"""

    for key, value in element.attrib.items():
        if _local_name(key) == local_name and value:
            return value
    return ""


def _extract_docx_blocks(
    *,
    body: ElementTree.Element,
    title: str,
    rels_map: dict[str, str],
) -> tuple[list[tuple[Any, ...]], list[str]]:
    """把 w:body 直接子元素拆成带类型标签的块列表。

    块类型:
      ("h", level, text)      标题段落
      ("p", text)             普通段落
      ("table", heading, text) 表格
      ("img", line)           图片引用行
    返回 (blocks, image_refs):image_refs 为全部解析后的图片引用行。
    只遍历 body 的直接子元素,表格内部的单元格段落不会重复计入段落流,
    同时段落/表格的原文交替顺序得以保留。
    """

    blocks: list[tuple[Any, ...]] = []
    image_refs: list[str] = []
    table_index = 0
    for element in body:
        name = _local_name(element.tag)
        if name == "tbl":
            rows = _extract_docx_table(element)
            if rows:
                table_index += 1
                blocks.append(("table", f"{title} 表格 {table_index}", _format_table_rows(rows)))
            continue
        if name != "p":
            continue
        heading_level = _docx_heading_level(element)
        if heading_level is not None:
            heading_text = _join_text_nodes(element)
            if heading_text:
                blocks.append(("h", heading_level, heading_text))
            continue
        text = _join_text_nodes(element)
        if text:
            blocks.append(("p", text))
        for ref in _resolve_docx_image_refs(element, rels_map):
            image_refs.append(ref)
            blocks.append(("img", ref))
    return blocks, image_refs


def _build_docx_flat_sections(*, blocks: list[tuple[Any, ...]], title: str) -> list[StructuredKnowledgeSection]:
    """无标题样式的 DOCX:按文档顺序把段落/图片聚成章节,表格独立成章。

    段落块和图片块累积进同一章节,遇到表格先冲刷当前章节再开启新章节,
    从而保留"段落-表格-段落"的原文顺序。
    """

    sections: list[StructuredKnowledgeSection] = []
    paragraph_lines: list[str] = []

    def flush_paragraphs() -> None:
        if paragraph_lines:
            sections.append(_make_section(index=len(sections), heading=title, content="\n\n".join(paragraph_lines)))
            paragraph_lines.clear()

    for block in blocks:
        kind = block[0]
        if kind in {"p", "img"}:
            paragraph_lines.append(block[1])
        elif kind == "table":
            flush_paragraphs()
            sections.append(_make_section(index=len(sections), heading=block[1], content=block[2]))
    flush_paragraphs()
    return _renumber_sections(sections)


def _build_docx_heading_sections(*, blocks: list[tuple[Any, ...]], title: str) -> list[StructuredKnowledgeSection]:
    """按标题层级把 DOCX 块流切分为章节。

    命中 Heading1-6 时开启新章节,并依据标题层级堆栈生成 title_path
    ([title, h1, h2, ...]),与 Markdown 章节结构对齐;标题以下的段落、
    表格与图片并入该章节,直到下一个同级或更高级标题出现。
    """

    sections: list[StructuredKnowledgeSection] = []
    heading_stack: list[tuple[int, str]] = []
    current_heading = title
    current_title_path = [title]
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            content = "\n\n".join(current_lines).strip()
            sections.append(
                StructuredKnowledgeSection(
                    section_id=f"sec_{len(sections):04d}",
                    heading=current_heading,
                    title_path=list(current_title_path),
                    content=content,
                    start_char=0,
                    end_char=len(content),
                )
            )
            current_lines.clear()

    for block in blocks:
        kind = block[0]
        if kind == "h":
            level, heading_text = block[1], block[2]
            flush()
            heading_stack = [(stack_level, stack_heading) for stack_level, stack_heading in heading_stack if stack_level < level]
            heading_stack.append((level, heading_text))
            current_heading = heading_text
            current_title_path = [title, *[stack_heading for _, stack_heading in heading_stack]]
        elif kind in {"p", "img"}:
            current_lines.append(block[1])
        elif kind == "table":
            current_lines.append(f"{block[1]}\n{block[2]}")
    flush()
    return _renumber_sections(sections)


def _docx_heading_level(element: ElementTree.Element) -> int | None:
    """识别 w:p 的标题样式,命中 Heading1-6 时返回对应层级。

    兼容 "Heading1"/"Heading 1"/"1"/"标题 1" 等常见样式 ID 写法,
    未命中时返回 None。
    """

    for node in element.iter():
        if _local_name(node.tag) != "pPr":
            continue
        for child in node:
            if _local_name(child.tag) != "pStyle":
                continue
            value = _attr_text(child, "val")
            if not value:
                continue
            match = re.search(r"(?i)(?:heading|标题)?\s*([1-6])\b", value)
            if match:
                return int(match.group(1))
    return None


def _read_docx_relationship_map(archive: zipfile.ZipFile) -> dict[str, str]:
    """读取 DOCX 文档级关系表,返回 rId -> 图片资源路径 的映射。

    只保留图片类关系(media/imageN.png),Target 中多余的 ../ 前缀会被
    归一化,使图片引用可从裸 rId 升级为真实资源路径。
    """

    rels_xml = _read_zip_text(archive, "word/_rels/document.xml.rels")
    if not rels_xml:
        return {}
    try:
        rels_root = ElementTree.fromstring(rels_xml)
    except ElementTree.ParseError:
        return {}
    rels_map: dict[str, str] = {}
    for rel in rels_root:
        rel_id = _attr_text(rel, "Id")
        target = _attr_text(rel, "Target")
        rel_type = _attr_text(rel, "Type")
        if not rel_id or not target or "image" not in rel_type:
            continue
        normalized = target.replace("\\", "/")
        while normalized.startswith("../"):
            normalized = normalized[3:]
        rels_map[rel_id] = normalized
    return rels_map


def _resolve_docx_image_refs(element: ElementTree.Element, rels_map: dict[str, str]) -> list[str]:
    """解析 w:p 中嵌入的图片引用,把 rId 升级为可读的媒体资源路径。

    rels_map: _read_docx_relationship_map 解析出的 rId -> 路径 映射。
    映射未命中时回退为原来的裸 rId 表示,保证缺 rels 文件的 DOCX 仍可解析。
    """

    refs: list[str] = []
    for node in element.iter():
        for key, value in node.attrib.items():
            if _local_name(key) not in {"embed", "link"} or not value:
                continue
            target = rels_map.get(value)
            refs.append(f"[DOCX 图片引用: {target}]" if target else f"image relationship: {value}")
    return refs


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
