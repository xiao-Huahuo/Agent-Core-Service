from pathlib import Path
from types import SimpleNamespace

from agent_service.services.knowledge_library_service import KnowledgeLibraryService


class _SettingsServiceStub:
    def __init__(self, knowledge_dir: Path) -> None:
        self.user_id = "user-1"
        self.library_id = "library-1"
        self.knowledge_dir = str(knowledge_dir)

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


class _MemoryServiceStub:
    def __init__(self) -> None:
        self.deleted_sources: list[tuple[str, str]] = []

    def delete_memories_for_source(self, *, user_id: str, tag: str, memory_type: str, source_id: str) -> int:
        self.deleted_sources.append((user_id, source_id))
        return 3


def _service(tmp_path: Path, knowledge_dir: Path) -> tuple[KnowledgeLibraryService, _MemoryServiceStub]:
    memory_service = _MemoryServiceStub()
    config = SimpleNamespace(
        constants=SimpleNamespace(knowledge_tag="knowledge"),
        storage=SimpleNamespace(
            base_data_dir=tmp_path / "runtime",
            frontmatter_dir=tmp_path / "runtime" / "frontmatter",
        ),
    )
    return (
        KnowledgeLibraryService(
            config=config,
            memory_service=memory_service,
            settings_service=_SettingsServiceStub(knowledge_dir),
            knowledge_graph_service=SimpleNamespace(),
        ),
        memory_service,
    )


def test_delete_path_moves_file_to_trash_and_restore(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    source = knowledge_dir / "notes.md"
    source.write_text("hello", encoding="utf-8")
    service, memory_service = _service(tmp_path, knowledge_dir)

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
    service, _memory_service = _service(tmp_path, knowledge_dir)
    result = service.delete_path(user_id="user-1", path="notes.md")

    deleted = service.delete_trash_entry(user_id="user-1", trash_id=result["trash_id"])

    assert deleted == {"ok": True, "trash_id": result["trash_id"]}
    assert service.list_deleted_paths(user_id="user-1") == []
