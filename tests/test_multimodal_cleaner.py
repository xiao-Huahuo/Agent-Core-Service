"""
多模态知识源清洗测试。

功能说明:
验证多模态清洗器可以把表格、JSON 和 Office Open XML 文件转换为统一章节,
并能被 FrontmatterBootstrapService 写成结构化知识 JSON。
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.multimodal_cleaner import MultimodalDocumentCleaner


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
