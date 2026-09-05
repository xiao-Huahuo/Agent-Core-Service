"""
知识库多模态预览回归测试。

功能说明:
本文件覆盖图片 OCR 预览、PDF 预览 asset 响应以及单文件入库状态说明,避免
多模态预览链路退化为 500、破图或误报 OCR 无切片。
"""

import json
from pathlib import Path
from types import SimpleNamespace

import fitz

from agent_service.api.rest import debug as debug_api
import agent_service.services.knowledge_library.preview as knowledge_library_module
from agent_service.services.knowledge_library import KnowledgeLibraryService
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.image_ocr import ImageOcrService
from agent_service.services.memory.rag.pdf_cleaner import PdfExtractionResult


class _SettingsServiceStub:
    """测试用设置服务,只提供知识库根目录和 OCR 用户开关。"""

    def __init__(self, *, knowledge_dir: Path, ocr_enabled: bool = True) -> None:
        """保存当前测试知识库根目录。"""

        self.knowledge_dir = str(knowledge_dir)
        self.ocr_enabled = ocr_enabled
        self.user_id = "user-1"
        self.library_id = "library-1"

    def ensure_user_profile(self, *, user_id: str) -> dict:
        """返回包含 active library 的用户配置。"""

        return {
            "user_id": self.user_id,
            "active_knowledge_library": {
                "library_id": self.library_id,
                "knowledge_dir": self.knowledge_dir,
            },
        }

    def get_active_knowledge_library(self, *, user_id: str) -> dict[str, str]:
        """返回当前 active 知识库目录。"""

        return {"knowledge_dir": self.knowledge_dir}

    def build_knowledge_owner_id(self, *, user_id: str, library_id: str) -> str:
        """返回文件树读取索引状态所需的稳定知识库所有者 ID。"""

        return f"{user_id}:{library_id}"

    def is_ocr_enabled_for_user(self, *, user_id: str) -> bool:
        """返回测试指定的用户级 OCR 开关。"""

        return self.ocr_enabled

    def get_knowledge_ingestion_config(self, *, user_id: str) -> dict[str, str]:
        """返回空忽略规则，使测试只覆盖 `.mw` 的文件树可见性。"""

        return {"knowledge_ignore_patterns": ""}


def _service(tmp_path: Path, knowledge_dir: Path, *, ocr_enabled: bool = True) -> KnowledgeLibraryService:
    """构造只覆盖预览路径所需依赖的 KnowledgeLibraryService。"""

    config = SimpleNamespace(
        constants=SimpleNamespace(knowledge_supported_suffixes=[".md", ".txt", ".png", ".pdf", ".docx"], knowledge_tag="knowledge"),
        storage=SimpleNamespace(
            assets_dir=tmp_path / "assets",
            frontmatter_dir=tmp_path / "frontmatter",
        ),
    )
    return KnowledgeLibraryService(
        config=config,
        memory_service=SimpleNamespace(),
        settings_service=_SettingsServiceStub(knowledge_dir=knowledge_dir, ocr_enabled=ocr_enabled),
        knowledge_graph_service=SimpleNamespace(),
    )


def _write_frontmatter(service: KnowledgeLibraryService, *, relative_path: str, content: str) -> None:
    """写入测试用用户级 frontmatter JSON。"""

    frontmatter_path = service._resolve_user_frontmatter_dir("user-1", "library-1") / relative_path
    frontmatter_path = frontmatter_path.with_suffix(".json")
    frontmatter_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "markdown": f"# test\n\n{content}\n",
                "projection_hash": "projection-1",
                "metadata": {"ocr_status": "completed"},
                "sections": [{"section_id": "sec_0000", "heading": "test", "content": content}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_preview_image_does_not_run_ocr_before_ingestion(tmp_path: Path, monkeypatch) -> None:
    """图片点击预览只应返回原图 URL,不能现场执行慢速 OCR。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    image_path = knowledge_dir / "note.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    def fail_extract(self: ImageOcrService, source_path: Path) -> None:
        raise AssertionError("preview must not run OCR")

    monkeypatch.setattr(ImageOcrService, "extract_image_text", fail_extract)
    service = _service(tmp_path, knowledge_dir, ocr_enabled=True)

    preview = service.preview_file(user_id="user-1", path="note.png")

    assert preview["kind"] == "image"
    assert preview["content"] == ""
    assert preview["raw_url"].endswith("/knowledge/files/raw?user_id=user-1&path=note.png")
    assert preview["ocr_status"] == "not_ingested"


def test_file_tree_shows_managed_mw_directory_without_indexing_it(tmp_path: Path) -> None:
    """`.mw` 应在树中可见；入库管线仍由独立路径过滤管理。"""

    knowledge_dir = tmp_path / "knowledge"
    (knowledge_dir / ".mw" / "library").mkdir(parents=True)
    (knowledge_dir / ".mw" / "library" / "book.md").write_text("# book", encoding="utf-8")
    service = _service(tmp_path, knowledge_dir)
    service.memory_service = SimpleNamespace(
        list_source_ids=lambda **kwargs: set(),
        list_source_updated_at=lambda **kwargs: {},
    )

    nodes = service.list_files(user_id="user-1")

    assert [node["name"] for node in nodes] == [".mw"]
    assert nodes[0]["children"][0]["name"] == "library"


def test_file_tree_hides_git_metadata_directory(tmp_path: Path) -> None:
    """文件树不得向前端暴露 Git 内部对象和引用目录。"""

    knowledge_dir = tmp_path / "knowledge"
    (knowledge_dir / ".git" / "objects").mkdir(parents=True)
    (knowledge_dir / ".git" / "objects" / "object-id").write_text("git metadata", encoding="utf-8")
    (knowledge_dir / "project" / ".git" / "refs").mkdir(parents=True)
    (knowledge_dir / "project" / ".git" / "refs" / "main").write_text("commit-id", encoding="utf-8")
    (knowledge_dir / "project" / "README.md").write_text("# project", encoding="utf-8")
    (knowledge_dir / "visible.md").write_text("# visible", encoding="utf-8")
    service = _service(tmp_path, knowledge_dir)
    service.memory_service = SimpleNamespace(
        list_source_ids=lambda **kwargs: set(),
        list_source_updated_at=lambda **kwargs: {},
    )

    nodes = service.list_files(user_id="user-1")

    assert ".git" not in {node["name"] for node in nodes}
    assert "visible.md" in {node["name"] for node in nodes}
    project = next(node for node in nodes if node["name"] == "project")
    assert [child["name"] for child in project["children"]] == ["README.md"]


def test_preview_image_uses_existing_ocr_frontmatter_text(tmp_path: Path) -> None:
    """图片已灌库产生 OCR sections 后,预览 payload 才暴露 edit/split 可显示文本。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    image_path = knowledge_dir / "note.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    service = _service(tmp_path, knowledge_dir, ocr_enabled=True)
    frontmatter_root = service._resolve_user_frontmatter_dir("user-1", "library-1")
    frontmatter_path = frontmatter_root / "note.json"
    frontmatter_path.parent.mkdir(parents=True)
    frontmatter_path.write_text(
        (
            '{"metadata":{"ocr_status":"completed","ocr_word_count":2,'
            '"ocr_engine_available":true,"ocr_average_confidence":0.97},'
            '"sections":[{"section_id":"sec_0000","heading":"note","content":"OCR text"}]}'
        ),
        encoding="utf-8",
    )

    preview = service.preview_file(user_id="user-1", path="note.png")

    assert preview["content"] == "OCR text"
    assert preview["ocr_status"] == "completed"
    assert preview["ocr_word_count"] == 2


def test_preview_docx_exposes_text_only_after_ingestion(tmp_path: Path, monkeypatch) -> None:
    """DOCX 默认走预览;只有已有 frontmatter 时才向编辑区暴露全文文本。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    docx_path = knowledge_dir / "report.docx"
    docx_path.write_bytes(b"fake docx")
    monkeypatch.setattr(KnowledgeLibraryService, "_preview_docx_html", lambda self, path: "<p>docx preview</p>")
    service = _service(tmp_path, knowledge_dir)

    before = service.preview_file(user_id="user-1", path="report.docx")
    _write_frontmatter(service, relative_path="report.docx", content="段落文字\n\n图片 OCR 文字")
    after = service.preview_file(user_id="user-1", path="report.docx")

    assert before["kind"] == "document"
    assert before["html"] == "<p>docx preview</p>"
    assert before["content"] == ""
    assert before["text_status"] == "not_ingested"
    assert after["content"] == "段落文字\n\n图片 OCR 文字"
    assert after["semantic_markdown"] == "# test\n\n段落文字\n\n图片 OCR 文字"
    assert after["text_status"] == "ready"


def test_preview_pdf_separates_render_content_from_ingested_text(tmp_path: Path, monkeypatch) -> None:
    """PDF render 模式使用即时 Markdown,文本模式只使用已灌库 frontmatter。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    pdf_path = knowledge_dir / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_extract_pdf_text(*args: object, **kwargs: object) -> PdfExtractionResult:
        return PdfExtractionResult(
            content="## Page 1\n\n![PDF page 1 image 1](/knowledge/assets/pdf_preview/demo/image-1.png)",
            page_count=1,
            image_count=1,
            table_count=0,
            is_scanned=True,
        )

    monkeypatch.setattr(knowledge_library_module, "extract_pdf_text", fake_extract_pdf_text)
    service = _service(tmp_path, knowledge_dir)

    before = service.preview_file(user_id="user-1", path="scan.pdf")
    _write_frontmatter(service, relative_path="scan.pdf", content="扫描件 OCR 全文")
    after = service.preview_file(user_id="user-1", path="scan.pdf")

    assert before["content"] == ""
    assert before["text_status"] == "not_ingested"
    assert before["render_content"].startswith("## Page 1")
    assert after["content"] == "扫描件 OCR 全文"
    assert after["render_content"].startswith("## Page 1")


def test_preview_pdf_exposes_a_rasterized_first_page_thumbnail(tmp_path: Path) -> None:
    """PDF 卡片预览应返回真实首页 PNG,而不是通用 PDF 图标。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    pdf_path = knowledge_dir / "paper.pdf"
    with fitz.open() as document:
        page = document.new_page(width=320, height=480)
        page.insert_text((36, 52), "MetaWeave PDF cover")
        document.save(pdf_path)
    service = _service(tmp_path, knowledge_dir)

    preview = service.preview_file(user_id="user-1", path="paper.pdf")

    assert preview["thumbnail_url"].startswith("/knowledge/assets/pdf_preview/")
    asset_name = preview["thumbnail_url"].removeprefix("/knowledge/assets/")
    thumbnail_path = service.config.storage.assets_dir / "knowledge" / asset_name
    assert thumbnail_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_preview_csv_keeps_raw_text_and_table_rows(tmp_path: Path) -> None:
    """CSV 的 Text 与 Forms 必须来自同一原文件,且原文保持可编辑。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "data.csv").write_text("name,value\nalpha,1\n", encoding="utf-8")
    service = _service(tmp_path, knowledge_dir)

    preview = service.preview_file(user_id="user-1", path="data.csv")

    assert preview["kind"] == "table"
    assert preview["content"] == "name,value\nalpha,1\n"
    assert preview["sheets"][0]["rows"] == [["name", "value"], ["alpha", "1"]]
    assert preview["readonly"] is False


def test_preview_xls_uses_forms_table(tmp_path: Path, monkeypatch) -> None:
    """旧版 XLS 仍属于 Forms 管线,不应降级成 Binary。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "legacy.xls").write_bytes(b"xls")
    service = _service(tmp_path, knowledge_dir)
    monkeypatch.setattr(service, "_preview_xls", lambda path: [{"name": "Sheet1", "rows": [["A", "B"]]}])

    preview = service.preview_file(user_id="user-1", path="legacy.xls")

    assert preview["kind"] == "table"
    assert preview["sheets"] == [{"name": "Sheet1", "rows": [["A", "B"]]}]
    assert preview["readonly"] is True


def test_preview_pptx_keeps_native_preview_blank_and_markdown_projection(tmp_path: Path) -> None:
    """PPTX Preview 目前为空,Markdown 模式只读取灌库投影。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "slides.pptx").write_bytes(b"pptx")
    service = _service(tmp_path, knowledge_dir)
    _write_frontmatter(service, relative_path="slides.pptx", content="幻灯片全文")

    preview = service.preview_file(user_id="user-1", path="slides.pptx")

    assert preview["kind"] == "presentation"
    assert preview["semantic_markdown"] == "# test\n\n幻灯片全文"
    assert preview["readonly"] is True


def test_preview_doc_is_classified_as_unsupported_binary(tmp_path: Path) -> None:
    """旧版 DOC 明确不进入 DOCX 预览管线。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "legacy.doc").write_bytes(b"\xd0\xcf\x11\xe0\x00\xff")
    service = _service(tmp_path, knowledge_dir)

    preview = service.preview_file(user_id="user-1", path="legacy.doc")

    assert preview["kind"] == "unsupported"
    assert preview["readonly"] is True


def test_preview_video_exposes_inline_player_source_without_ingestion(tmp_path: Path) -> None:
    """视频仅返回浏览器播放器数据,不能进入知识灌库白名单。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "clip.mp4").write_bytes(b"video")
    service = _service(tmp_path, knowledge_dir)

    preview = service.preview_file(user_id="user-1", path="clip.mp4")

    assert preview["kind"] == "video"
    assert preview["video_container"] == "native"
    assert preview["mime_type"] == "video/mp4"
    assert preview["raw_url"].endswith("/knowledge/files/raw?user_id=user-1&path=clip.mp4")
    assert preview["readonly"] is True
    assert service._can_ingest_source_file(knowledge_dir / "clip.mp4") is False


def test_preview_video_detects_mpegts_hidden_behind_mp4_extension(tmp_path: Path) -> None:
    """扩展名为 MP4 的 MPEG-TS 文件应交给流式转封装播放器。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    transport_packet = b"\x47" + (b"\x00" * 187)
    (knowledge_dir / "recording.mp4").write_bytes(transport_packet * 3)
    service = _service(tmp_path, knowledge_dir)

    preview = service.preview_file(user_id="user-1", path="recording.mp4")

    assert preview["kind"] == "video"
    assert preview["video_container"] == "mpegts"


def test_resolve_knowledge_asset_serves_pdf_preview_image(tmp_path: Path) -> None:
    """PDF 预览导出的 /knowledge/assets 图片应能被后端解析为真实文件。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    asset_path = tmp_path / "assets" / "knowledge" / "pdf_preview" / "asset-key" / "image_0001.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    service = _service(tmp_path, knowledge_dir)

    resolved_path, media_type = service.resolve_knowledge_asset_for_response(
        path="pdf_preview/asset-key/image_0001.png",
    )

    assert resolved_path == asset_path.resolve()
    assert media_type == "image/png"


def test_single_file_result_reports_unchanged_when_sections_exist(tmp_path: Path) -> None:
    """已有可入库 sections 但本轮 0 chunk 时,应按未变化跳过解释而非误报 OCR 无切片。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source_path = knowledge_dir / "table.png"
    source_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    frontmatter_path = tmp_path / "frontmatter" / "table.json"
    frontmatter_path.parent.mkdir()
    frontmatter_path.write_text(
        (
            '{"metadata":{"ocr_status":"completed"},'
            '"sections":[{"section_id":"sec_0000","heading":"table","content":"OCR text"}]}'
        ),
        encoding="utf-8",
    )
    service = _service(tmp_path, knowledge_dir)

    reason, message = service._describe_single_file_ingestion_result(
        source_path=source_path,
        frontmatter_path=frontmatter_path,
        files_ingested=0,
        chunks_created=0,
    )

    assert reason == "unchanged"
    assert "未变化" in message


def test_debug_multimodal_observation_uses_existing_frontmatter(tmp_path: Path, monkeypatch) -> None:
    """debug 多模态观测已有 frontmatter 时不应重跑结构化/OCR。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source_path = knowledge_dir / "note.png"
    source_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    structured_payload = {
        "document_id": "knowledge:note",
        "source_type": "image",
        "source_path": str(source_path),
        "source_uri": str(source_path),
        "source_hash": FrontmatterBootstrapService._hash_file(source_path),
        "schema_version": 2,
        "markdown": "# note\n\nOCR text for debug\n",
        "projection_hash": "projection-1",
        "title": "note",
        "summary": "",
        "tags": [],
        "authority": 0.7,
        "valid_from": None,
        "valid_until": None,
        "metadata": {
            "relative_path": "note.png",
            "ocr_enabled": True,
            "ocr_status": "completed",
        },
        "sections": [
            {
                "section_id": "sec_0000",
                "heading": "note",
                "title_path": ["note"],
                "content": "OCR text for debug",
                "start_char": 0,
                "end_char": 18,
            }
        ],
    }
    config = SimpleNamespace(
        constants=SimpleNamespace(knowledge_supported_suffixes=[".png"], knowledge_tag="knowledge"),
        memory=SimpleNamespace(chunk_size=512, chunk_overlap=128),
    )
    library_service = SimpleNamespace(
        get_active_root_path=lambda user_id: knowledge_dir,
        read_frontmatter_payload_for_file=lambda user_id, path: structured_payload,
        settings_service=SimpleNamespace(is_ocr_enabled_for_user=lambda user_id: True),
    )

    def fail_build_frontmatter_file(self, **kwargs):
        raise AssertionError("debug observation should reuse existing frontmatter")

    monkeypatch.setattr(debug_api, "_require_knowledge_library_service", lambda: library_service)
    monkeypatch.setattr(debug_api, "_require_agent", lambda: SimpleNamespace(config=config))
    monkeypatch.setattr(
        debug_api.FrontmatterBootstrapService,
        "build_frontmatter_file",
        fail_build_frontmatter_file,
    )

    payload = debug_api._build_multimodal_ingestion_observation(user_id="user-1", relative_path="note.png")

    assert payload["json_result"] == structured_payload
    assert payload["semantic_chunks"][0]["content"] == "OCR text for debug"
