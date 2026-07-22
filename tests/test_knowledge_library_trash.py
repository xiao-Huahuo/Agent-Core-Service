from pathlib import Path
from types import SimpleNamespace

from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.knowledge_library_service import KnowledgeLibraryService


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
