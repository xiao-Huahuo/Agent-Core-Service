"""
知识库文件生命周期与索引清理回归测试。

使用说明:
通过轻量服务桩验证删除、重命名、覆盖保存等文件变化会同步清理 frontmatter、
向量切片和语义图谱来源,避免磁盘内容变化后继续召回旧数据。
"""

from pathlib import Path
from types import SimpleNamespace

from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.knowledge_library_service import KnowledgeIgnoreMatcher, KnowledgeLibraryService


class _SettingsServiceStub:
    def __init__(self, knowledge_dir: Path) -> None:
        self.user_id = "user-1"
        self.library_id = "library-1"
        self.knowledge_dir = str(knowledge_dir)
        self.knowledge_ignore_patterns = ""

    def ensure_user_profile(self, *, user_id: str) -> dict:
        return {
            "user_id": self.user_id,
            "active_knowledge_library": {
                "library_id": self.library_id,
                "knowledge_dir": self.knowledge_dir,
            },
        }

    def get_active_knowledge_library(self, *, user_id: str) -> dict[str, str]:
        return {"library_id": self.library_id, "knowledge_dir": self.knowledge_dir}

    def build_knowledge_owner_id(self, *, user_id: str, library_id: str) -> str:
        return f"{user_id}:{library_id}"

    def get_knowledge_ingestion_config(self, *, user_id: str) -> dict[str, str]:
        return {"knowledge_ignore_patterns": self.knowledge_ignore_patterns}

    def is_ocr_enabled_for_user(self, *, user_id: str) -> bool:
        return False


class _MemoryServiceStub:
    def __init__(self) -> None:
        self.deleted_sources: list[tuple[str, str]] = []
        self.source_ids: set[str] = set()

    def delete_memories_for_source(self, *, user_id: str, tag: str, memory_type: str, source_id: str) -> int:
        self.deleted_sources.append((user_id, source_id))
        return 3

    def list_source_ids(self, *, user_id: str, tag: str, memory_type: str) -> set[str]:
        return set(self.source_ids)

    def list_source_updated_at(self, *, user_id: str, tag: str, memory_type: str) -> dict[str, object]:
        return {}


class _GraphServiceStub:
    def __init__(self) -> None:
        self.statuses: dict[str, object] = {}
        self.deleted_document_ids: list[str] = []

    def list_document_statuses(self, *, user_id: str, library_id: str) -> dict[str, object]:
        return dict(self.statuses)

    def delete_document_graph(self, *, user_id: str, library_id: str, document_id: str) -> int:
        self.deleted_document_ids.append(document_id)
        return 1


def _service(
    tmp_path: Path,
    knowledge_dir: Path,
) -> tuple[KnowledgeLibraryService, _MemoryServiceStub, _SettingsServiceStub, _GraphServiceStub]:
    memory_service = _MemoryServiceStub()
    settings_service = _SettingsServiceStub(knowledge_dir)
    graph_service = _GraphServiceStub()
    config = SimpleNamespace(
        constants=SimpleNamespace(knowledge_tag="knowledge", knowledge_supported_suffixes=[".md", ".txt"]),
        storage=SimpleNamespace(
            base_data_dir=tmp_path / "runtime",
            frontmatter_dir=tmp_path / "runtime" / "frontmatter",
            trash_dir=tmp_path / "runtime" / "trash",
        ),
    )
    return (
        KnowledgeLibraryService(
            config=config,
            memory_service=memory_service,
            settings_service=settings_service,
            knowledge_graph_service=graph_service,
        ),
        memory_service,
        settings_service,
        graph_service,
    )


def test_delete_path_moves_file_to_trash_and_restore(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source = knowledge_dir / "notes.md"
    source.write_text("hello", encoding="utf-8")
    service, memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)

    result = service.delete_path(user_id="user-1", path="notes.md")

    assert result["ok"] is True
    assert result["original_relative_path"] == "notes.md"
    assert result["chunks_deleted"] == 3
    assert not source.exists()
    assert memory_service.deleted_sources
    trash_entries = service.list_deleted_paths(user_id="user-1")
    assert [entry["trash_id"] for entry in trash_entries] == [result["trash_id"]]

    restored = service.restore_deleted_path(user_id="user-1", trash_id=result["trash_id"])

    assert restored["ok"] is True
    assert restored["restored_path"] == "notes.md"
    assert source.read_text(encoding="utf-8") == "hello"
    assert service.list_deleted_paths(user_id="user-1") == []


def test_delete_trash_entry_permanently_removes_metadata_and_content(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source = knowledge_dir / "notes.md"
    source.write_text("hello", encoding="utf-8")
    service, _memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)
    result = service.delete_path(user_id="user-1", path="notes.md")

    deleted = service.delete_trash_entry(user_id="user-1", trash_id=result["trash_id"])

    assert deleted == {"ok": True, "trash_id": result["trash_id"]}
    assert service.list_deleted_paths(user_id="user-1") == []


def test_list_files_includes_graph_status(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    for name in ("graphed.md", "pending.md", "ignored.md"):
        (knowledge_dir / name).write_text("hello", encoding="utf-8")
    service, memory_service, settings_service, graph_service = _service(tmp_path, knowledge_dir)
    settings_service.knowledge_ignore_patterns = "ignored.md"
    frontmatter_root = service._resolve_user_frontmatter_dir("user-1", "library-1")
    for name in ("graphed.md", "pending.md"):
        document_id = FrontmatterBootstrapService._build_document_id(Path(name))
        memory_service.source_ids.add(document_id)
        frontmatter_path = (frontmatter_root / name).with_suffix(".json")
        frontmatter_path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter_path.write_text(
            '{"source_hash":"hash-1","metadata":{"relative_path":"' + name + '"},"sections":[]}',
            encoding="utf-8",
        )
        if name == "graphed.md":
            graph_service.statuses[document_id] = SimpleNamespace(source_hash="hash-1", status="completed")

    nodes = {node["name"]: node for node in service.list_files(user_id="user-1")}

    assert nodes["graphed.md"]["graphStatus"] == "graphed"
    assert nodes["graphed.md"]["createdAt"]
    assert nodes["pending.md"]["graphStatus"] == "dirty"
    assert nodes["ignored.md"]["graphStatus"] == "ignored"


def test_cleanup_ignored_sources_deletes_graph_artifacts(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    ignored_file = knowledge_dir / "ignored.md"
    ignored_file.write_text("hello", encoding="utf-8")
    service, _memory_service, settings_service, graph_service = _service(tmp_path, knowledge_dir)
    settings_service.knowledge_ignore_patterns = "ignored.md"

    result = service.cleanup_ignored_sources(user_id="user-1")
    expected_document_id = FrontmatterBootstrapService._build_document_id(Path("ignored.md"))

    assert result["files_seen"] == 1
    assert result["chunks_deleted"] == 3
    assert graph_service.deleted_document_ids == [expected_document_id]


def test_write_file_invalidates_existing_index_artifacts(tmp_path: Path) -> None:
    """覆盖已存在文件前必须删除该来源的全部旧索引。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source = knowledge_dir / "notes.md"
    source.write_text("old content", encoding="utf-8")
    service, memory_service, _settings_service, graph_service = _service(tmp_path, knowledge_dir)
    frontmatter_root = service._resolve_user_frontmatter_dir("user-1", "library-1")
    frontmatter_path = frontmatter_root / "notes.json"
    frontmatter_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter_path.write_text(
        '{"metadata":{"relative_path":"notes.md"},"sections":[]}',
        encoding="utf-8",
    )
    markdown_path = service._resolve_user_markdown_dir("user-1", "library-1") / "notes.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("old projection", encoding="utf-8")

    service.write_file(user_id="user-1", path="notes.md", content="new content")

    expected_document_id = FrontmatterBootstrapService._build_document_id(Path("notes.md"))
    assert source.read_text(encoding="utf-8") == "new content"
    assert memory_service.deleted_sources == [("user-1:library-1", expected_document_id)]
    assert graph_service.deleted_document_ids == [expected_document_id]
    assert not frontmatter_path.exists()
    assert not markdown_path.exists()


def test_list_files_shows_dot_directories_but_marks_them_ingestion_ignored(tmp_path: Path) -> None:
    """点目录应完整展示，但目录本身和后代都标记为灌库忽略。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "notes.md").write_text("hello", encoding="utf-8")
    (knowledge_dir / ".notes.md").write_text("visible dot file", encoding="utf-8")
    git_dir = knowledge_dir / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    cache_dir = knowledge_dir / "docs" / ".cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "draft.md").write_text("ignored draft", encoding="utf-8")
    service, _memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)

    nodes = {node["name"]: node for node in service.list_files(user_id="user-1")}

    assert set(nodes) == {".git", ".notes.md", "docs", "notes.md"}
    assert nodes[".git"]["indexStatus"] == "ignored"
    assert nodes[".git"]["children"][0]["name"] == "HEAD"
    assert nodes[".git"]["children"][0]["indexStatus"] == "ignored"
    assert nodes["docs"]["children"][0]["name"] == ".cache"
    assert nodes["docs"]["children"][0]["children"][0]["indexStatus"] == "ignored"
    assert nodes[".notes.md"]["indexStatus"] == "dirty"


def test_ingestion_ignore_matcher_ignores_every_dot_directory_only() -> None:
    """灌库默认忽略任意层级点目录，但不按点文件名称扩大规则。"""

    matcher = KnowledgeIgnoreMatcher("")

    assert matcher.is_ignored(".git", is_dir=True) is True
    assert matcher.is_ignored(".git/HEAD", is_dir=False) is True
    assert matcher.is_ignored("docs/.cache/draft.md", is_dir=False) is True
    assert matcher.is_ignored(".notes.md", is_dir=False) is False
    assert matcher.is_ignored("docs/.draft.md", is_dir=False) is False


def test_legacy_forms_are_not_hard_ignored(tmp_path: Path) -> None:
    """智能表格元数据默认忽略,但上传到 assets/ 的文献仍可灌库。"""

    knowledge_dir = tmp_path / "knowledge"
    forms_dir = knowledge_dir / "forms"
    assets_dir = forms_dir / "AI文献阅读解析多维表" / "assets"
    assets_dir.mkdir(parents=True)
    (forms_dir / "data.csv").write_text("title\nhello", encoding="utf-8")
    (assets_dir / "paper.md").write_text("paper text", encoding="utf-8")
    service, _memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)

    nodes = service.list_files(user_id="user-1")
    form_node = nodes[0]
    children_by_name = {node["name"]: node for node in form_node["children"]}
    table_node = children_by_name["AI文献阅读解析多维表"]
    table_children_by_name = {node["name"]: node for node in table_node["children"]}
    asset_node = table_children_by_name["assets"]["children"][0]

    assert form_node["name"] == "forms"
    assert form_node["indexStatus"] == "dirty"
    assert children_by_name["data.csv"]["indexStatus"] == "dirty"
    assert asset_node["indexStatus"] == "dirty"


def test_tree_signature_tracks_files_without_parent_directories(tmp_path: Path) -> None:
    """轮询签名不应因目录 mtime 变化而误使同目录其他文件索引失效。"""

    knowledge_dir = tmp_path / "knowledge"
    nested_dir = knowledge_dir / "notes"
    nested_dir.mkdir(parents=True)
    (nested_dir / "a.md").write_text("a", encoding="utf-8")
    service, _memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)

    signature = service.build_tree_signature(user_id="user-1")

    assert set(signature) == {"notes/a.md"}


def test_read_markdown_projection_returns_managed_markdown(tmp_path: Path) -> None:
    """阅读源文件时必须返回 `.mw/md` 投影，而不是直接解码原文件。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source = knowledge_dir / "report.pdf"
    source.write_bytes(b"binary-pdf-placeholder")
    service, memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)
    document_id = FrontmatterBootstrapService._build_document_id(Path("report.pdf"))
    memory_service.source_ids.add(document_id)
    markdown_path = service._resolve_user_markdown_dir("user-1", "library-1") / "report.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# Report\n\nProjected body", encoding="utf-8")
    frontmatter_path = service._resolve_user_frontmatter_dir("user-1", "library-1") / "report.json"
    frontmatter_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter_path.write_text(
        '{"source_hash":"' + FrontmatterBootstrapService._hash_file(source) + '",'
        '"metadata":{"relative_path":"report.pdf"}}',
        encoding="utf-8",
    )

    result = service.read_markdown_projection(user_id="user-1", path="report.pdf")

    assert result["path"] == "report.pdf"
    assert result["projection_path"] == ".mw/md/report.md"
    assert result["content"] == "# Report\n\nProjected body"


def test_read_markdown_projection_auto_ingests_missing_projection(tmp_path: Path, monkeypatch) -> None:
    """源文件尚无投影或索引时，阅读操作必须先复用单文件灌库链路。"""

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source = knowledge_dir / "notes.txt"
    source.write_text("source body", encoding="utf-8")
    service, _memory_service, _settings_service, _graph_service = _service(tmp_path, knowledge_dir)
    ingestion_calls: list[Path] = []

    def fake_ingest_frontmatter_file(
        self: object,
        *,
        frontmatter_path: Path,
        user_id: str,
        progress_callback: object | None = None,
    ) -> SimpleNamespace:
        """保留真实投影转换，只隔离本测试不关心的向量模型写入。"""

        ingestion_calls.append(frontmatter_path)
        return SimpleNamespace(
            files_seen=1,
            files_ingested=1,
            files_skipped=0,
            chunks_created=1,
            chunks_deleted=0,
        )

    monkeypatch.setattr(
        "agent_service.services.memory.rag.knowledge_ingestion.KnowledgeIngestionService.ingest_frontmatter_file",
        fake_ingest_frontmatter_file,
    )

    result = service.read_markdown_projection(user_id="user-1", path="notes.txt")

    assert [path.name for path in ingestion_calls] == ["notes.json"]
    assert result["content"] == "# notes\n\nsource body\n"
    assert (knowledge_dir / ".mw" / "frontmatter" / "notes.json").is_file()
    assert (knowledge_dir / ".mw" / "md" / "notes.md").is_file()
