"""
多模态知识源清洗测试。

功能说明:
验证多模态清洗器可以把表格、JSON 和 Office Open XML 文件转换为统一章节,
并能被 FrontmatterBootstrapService 写成结构化知识 JSON。
"""

from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeDocument, StructuredKnowledgeSection
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService
from agent_service.services.memory.rag.image_ocr import ImageOcrResult
from agent_service.services.memory.rag.multimodal_cleaner import MultimodalDocumentCleaner
from agent_service.services.knowledge_library_service import KnowledgeIgnoreMatcher


def test_cleaner_extracts_csv_and_json_sections(tmp_path: Path) -> None:
    """CSV 和 JSON 应清洗为可检索文本章节。"""

    csv_path = tmp_path / "people.csv"
    csv_path.write_text("name,role\nAlice,Engineer\nBob,Designer\n", encoding="utf-8")
    json_path = tmp_path / "profile.json"
    json_path.write_text(json.dumps({"project": "MetaWeave", "owner": "Alice"}), encoding="utf-8")
    cleaner = MultimodalDocumentCleaner()

    csv_doc = cleaner.clean(source_path=csv_path, title="people")
    json_doc = cleaner.clean(source_path=json_path, title="profile")

    assert csv_doc.source_type == "table"
    assert "Alice | Engineer" in csv_doc.sections[0].content
    assert json_doc.source_type == "json"
    assert '"project": "MetaWeave"' in json_doc.sections[0].content


def test_cleaner_extracts_docx_and_xlsx_sections(tmp_path: Path) -> None:
    """DOCX 段落/表格和 XLSX 工作表应被抽取为章节文本。"""

    docx_path = tmp_path / "demo.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>项目说明段落</w:t></w:r></w:p>
                <w:tbl>
                  <w:tr><w:tc><w:p><w:r><w:t>列A</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>列B</w:t></w:r></w:p></w:tc></w:tr>
                  <w:tr><w:tc><w:p><w:r><w:t>值1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>值2</w:t></w:r></w:p></w:tc></w:tr>
                </w:tbl>
              </w:body>
            </w:document>
            """,
        )
    xlsx_path = tmp_path / "book.xlsx"
    with zipfile.ZipFile(xlsx_path, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row><c t="inlineStr"><is><t>城市</t></is></c><c t="inlineStr"><is><t>分数</t></is></c></row>
                <row><c t="inlineStr"><is><t>璃月</t></is></c><c><v>95</v></c></row>
              </sheetData>
            </worksheet>
            """,
        )
    cleaner = MultimodalDocumentCleaner()

    docx_doc = cleaner.clean(source_path=docx_path, title="demo")
    xlsx_doc = cleaner.clean(source_path=xlsx_path, title="book")

    assert docx_doc.source_type == "docx"
    assert any("项目说明段落" in section.content for section in docx_doc.sections)
    assert any("值1 | 值2" in section.content for section in docx_doc.sections)
    assert xlsx_doc.source_type == "spreadsheet"
    assert "璃月 | 95" in xlsx_doc.sections[0].content


def test_cleaner_extracts_text_layer_pdf(tmp_path: Path) -> None:
    """非扫描型 PDF 应优先提取文本层进入可检索章节。"""

    import fitz  # type: ignore[import-untyped]

    pdf_path = tmp_path / "demo.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF text layer content with enough searchable characters")
    document.save(pdf_path)
    document.close()

    cleaned = MultimodalDocumentCleaner().clean(source_path=pdf_path, title="demo")

    assert cleaned.source_type == "pdf"
    assert cleaned.metadata["pdf_scanned"] is False
    assert "PDF text layer content" in cleaned.sections[0].content


def test_cleaner_preserves_pdf_image_refs(tmp_path: Path) -> None:
    """PDF images should be kept as page-relative refs without OCR."""

    import fitz  # type: ignore[import-untyped]

    pdf_path = tmp_path / "image.pdf"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF image order")
    page.insert_image(fitz.Rect(72, 96, 120, 144), stream=png_bytes)
    document.save(pdf_path)
    document.close()

    cleaned = MultimodalDocumentCleaner().clean(source_path=pdf_path, title="image")

    assert cleaned.source_type == "pdf"
    assert cleaned.metadata["image_count"] == 1
    assert cleaned.metadata["image_refs"][0]["page"] == 1
    assert cleaned.metadata["image_refs"][0]["bbox"] == [72.0, 96.0, 120.0, 144.0]
    assert "[PDF 图片引用: image 1" in cleaned.sections[0].content


def test_frontmatter_bootstrap_writes_pdf_image_markdown(tmp_path: Path) -> None:
    """PDF images should be exported as assets and rendered through Markdown."""

    import fitz  # type: ignore[import-untyped]

    knowledge_dir = tmp_path / "knowledge"
    frontmatter_dir = tmp_path / "frontmatter"
    runtime_dir = tmp_path / "runtime"
    knowledge_dir.mkdir()
    pdf_path = knowledge_dir / "scan.pdf"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    document = fitz.open()
    page = document.new_page()
    page.insert_image(fitz.Rect(0, 0, 72, 72), stream=png_bytes)
    document.save(pdf_path)
    document.close()
    config = AgentConfig.load_config(
        {
            "storage": {
                "base_data_dir": runtime_dir,
                "knowledge_dir": knowledge_dir,
                "frontmatter_dir": frontmatter_dir,
            }
        },
        load_env=False,
        ensure_directories=True,
        ensure_models=False,
    )
    service = FrontmatterBootstrapService(config=config)

    result, output_path = service.build_frontmatter_file(source_path=pdf_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    image_ref = payload["metadata"]["image_refs"][0]
    assert result.files_written == 1
    assert payload["metadata"]["pdf_scanned"] is True
    assert payload["sections"][0]["content"].startswith("## Page 1")
    assert "[PDF 图片引用: image 1" in payload["sections"][0]["content"]
    assert image_ref["index"] == 1
    assert image_ref["page"] == 1
    assert image_ref["xref"] == 5
    assert image_ref["ext"] == "png"


def test_cleaner_extracts_image_ocr_text(tmp_path: Path) -> None:
    """图片 OCR 命中文本时应生成可检索章节。"""

    class FakeOcrService:
        def extract_image_text(self, source_path: Path) -> ImageOcrResult:
            assert source_path.name == "table.png"
            return ImageOcrResult(
                content="姓名 | 分数\nAlice | 98",
                has_text=True,
                word_count=4,
                average_confidence=91.0,
                engine_available=True,
            )

    image_path = tmp_path / "table.png"
    image_path.write_bytes(b"fake image bytes")
    cleaner = MultimodalDocumentCleaner(ocr_enabled=True, image_ocr_service=FakeOcrService())

    cleaned = cleaner.clean(source_path=image_path, title="table")

    assert cleaned.source_type == "image"
    assert cleaned.metadata["ocr_status"] == "completed"
    assert "Alice | 98" in cleaned.sections[0].content


def test_cleaner_skips_image_without_ocr_text(tmp_path: Path) -> None:
    """图片没有 OCR 文本时不应生成语义章节。"""

    class FakeOcrService:
        def extract_image_text(self, source_path: Path) -> ImageOcrResult:
            return ImageOcrResult(has_text=False, engine_available=True)

    image_path = tmp_path / "photo.png"
    image_path.write_bytes(b"fake image bytes")
    cleaner = MultimodalDocumentCleaner(ocr_enabled=True, image_ocr_service=FakeOcrService())

    cleaned = cleaner.clean(source_path=image_path, title="photo")

    assert cleaned.source_type == "image"
    assert cleaned.metadata["ocr_status"] == "no_text"
    assert cleaned.sections == []


def test_frontmatter_bootstrap_writes_multimodal_json(tmp_path: Path) -> None:
    """结构化预处理应扫描配置白名单内的多模态文件并输出 JSON。"""

    knowledge_dir = tmp_path / "knowledge"
    frontmatter_dir = tmp_path / "frontmatter"
    knowledge_dir.mkdir()
    (knowledge_dir / "table.csv").write_text("k,v\nalpha,beta\n", encoding="utf-8")
    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    service = FrontmatterBootstrapService(config=config)

    result = service.build_frontmatter_dir(
        knowledge_dir=knowledge_dir,
        frontmatter_dir=frontmatter_dir,
        supported_suffixes={".csv"},
    )

    payload = json.loads((frontmatter_dir / "table.json").read_text(encoding="utf-8"))
    assert result.files_seen == 1
    assert result.files_written == 1
    assert payload["source_type"] == "table"
    assert payload["metadata"]["modality"] == "table"
    assert "alpha | beta" in payload["sections"][0]["content"]


def test_global_frontmatter_bootstrap_excludes_user_library_subtree(tmp_path: Path) -> None:
    """启动全局结构化不应重复扫描 editor 用户知识库子树。"""

    knowledge_dir = tmp_path / "knowledge"
    frontmatter_dir = tmp_path / "frontmatter"
    user_library_dir = knowledge_dir / "1" / "1"
    user_library_dir.mkdir(parents=True)
    (knowledge_dir / "global.md").write_text("global content", encoding="utf-8")
    (user_library_dir / "local.md").write_text("local content", encoding="utf-8")
    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    service = FrontmatterBootstrapService(config=config)

    result = service.build_frontmatter_dir(
        knowledge_dir=knowledge_dir,
        frontmatter_dir=frontmatter_dir,
        supported_suffixes={".md"},
        exclude_path=lambda path: path.resolve().is_relative_to(user_library_dir.resolve()),
    )

    assert result.files_seen == 1
    assert result.files_written == 1
    assert (frontmatter_dir / "global.json").is_file()
    assert not (frontmatter_dir / "1" / "1" / "local.json").exists()


def test_global_ingestion_excludes_stale_user_frontmatter_subtree(tmp_path: Path) -> None:
    """历史误写入全局 frontmatter 的用户库 JSON 不应在启动入库时被消费。"""

    class FakeEmbeddingService:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] for _ in texts]

    class FakeMemoryService:
        def __init__(self) -> None:
            self.created: list[object] = []

        def has_source_hash(self, **kwargs: object) -> bool:
            return False

        def delete_memories_for_source(self, **kwargs: object) -> int:
            return 0

        def create_memory(self, memory_create: object) -> None:
            self.created.append(memory_create)

    frontmatter_dir = tmp_path / "frontmatter"
    global_json = frontmatter_dir / "global.json"
    stale_user_json = frontmatter_dir / "1" / "1" / "local.json"
    global_json.parent.mkdir(parents=True)
    stale_user_json.parent.mkdir(parents=True)

    def write_doc(path: Path, document_id: str, title: str) -> None:
        doc = StructuredKnowledgeDocument(
            document_id=document_id,
            source_type="markdown",
            source_path=str(path),
            source_uri=str(path),
            source_hash=document_id,
            title=title,
            summary="",
            tags=[],
            authority=0.7,
            valid_from=None,
            valid_until=None,
            sections=[
                StructuredKnowledgeSection(
                    section_id="sec_0000",
                    heading=title,
                    title_path=[title],
                    content=f"{title} content",
                    start_char=0,
                    end_char=len(f"{title} content"),
                )
            ],
        )
        path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False), encoding="utf-8")

    write_doc(global_json, "global", "global")
    write_doc(stale_user_json, "local", "local")
    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    service = KnowledgeIngestionService(
        config=config,
        embedding_service=FakeEmbeddingService(),
        memory_service=FakeMemoryService(),
    )

    result = service.ingest_frontmatter_dir(
        frontmatter_dir=frontmatter_dir,
    )

    assert result.files_seen == 2
    assert result.files_ingested == 2
    assert result.source_ids_seen == {"global", "local"}


def test_global_ingestion_scan_skips_user_frontmatter_subtree(tmp_path: Path) -> None:
    """启动全局灌库不应递归吃掉用户隔离 frontmatter 输出。"""

    frontmatter_dir = tmp_path / "frontmatter"
    global_json = frontmatter_dir / "global.json"
    user_json = frontmatter_dir / "users" / "1" / "kb_demo" / "local.json"
    global_json.parent.mkdir(parents=True)
    user_json.parent.mkdir(parents=True)
    global_json.write_text("{}", encoding="utf-8")
    user_json.write_text("{}", encoding="utf-8")

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    config.storage.frontmatter_dir = frontmatter_dir
    service = object.__new__(KnowledgeIngestionService)
    service.config = config

    global_scan = service._iter_frontmatter_files(frontmatter_dir)
    user_scan = service._iter_frontmatter_files(user_json.parent)

    assert global_scan == [global_json.resolve()]
    assert user_scan == [user_json.resolve()]


def test_document_id_keeps_chinese_filename_paths_distinct() -> None:
    """中文文件名不能因 slug 清洗而生成相同 document_id。"""

    first = FrontmatterBootstrapService._build_document_id(Path("1/2/test/带图word.docx"))
    second = FrontmatterBootstrapService._build_document_id(Path("1/2/test/简单word.docx"))

    assert first != second
    assert first.startswith("doc_")
    assert second.startswith("doc_")


def test_knowledge_ignore_matcher_supports_gitignore_subset() -> None:
    """屏蔽规则支持目录、通配符和反向取消。"""

    matcher = KnowledgeIgnoreMatcher(
        """
        # private data
        private/
        *.tmp
        !private/keep.md
        """
    )

    assert matcher.is_ignored("private/a.pdf")
    assert matcher.is_ignored("nested/file.tmp")
    assert not matcher.is_ignored("private/keep.md")
    assert not matcher.is_ignored("docs/readme.md")
