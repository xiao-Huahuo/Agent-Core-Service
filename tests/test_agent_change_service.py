"""Focused persistence and guarded-undo checks for Agent change snapshots."""

from pathlib import Path

from agent_service.core.agent_config import AgentConfig
from agent_service.services.agent_change.service import AgentChangeService


class _KnowledgeServiceStub:
    """Small in-memory knowledge service used to verify change safety rules."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {"note.md": "before\n"}
        self.deleted: list[str] = []

    def read_file(self, *, user_id: str, path: str) -> dict[str, str]:
        if path not in self.files:
            raise ValueError("file not found")
        return {"content": self.files[path]}

    def write_file(self, *, user_id: str, path: str, content: str) -> dict[str, str]:
        self.files[path] = content
        return {"path": path}

    def delete_path(self, *, user_id: str, path: str) -> dict[str, str]:
        self.deleted.append(path)
        self.files.pop(path, None)
        return {"path": path}


def _service(tmp_path: Path) -> tuple[AgentChangeService, _KnowledgeServiceStub]:
    """Create the service with isolated SQLite storage."""

    config = AgentConfig.load_config(ensure_directories=False, ensure_models=False)
    config.storage.sqlite_path = tmp_path / "changes.db"
    knowledge = _KnowledgeServiceStub()
    return AgentChangeService(config=config, knowledge_library_service=knowledge), knowledge  # type: ignore[arg-type]


def test_undo_restores_only_unchanged_agent_edit(tmp_path: Path) -> None:
    """A snapshot restores its saved before text when no later edit intervened."""

    service, knowledge = _service(tmp_path)
    service.start_run(user_id="u", session_id="s", run_id="r")
    service.record_edit(user_id="u", run_id="r", path="note.md", before="before\n", after="after\n")
    snapshot = service.finalize_run(run_id="r")
    assert snapshot is not None
    knowledge.files["note.md"] = "after\n"
    result = service.undo_snapshot(snapshot_id=snapshot["snapshot_id"], user_id="u")
    assert result["is_undone"] is True
    assert knowledge.files["note.md"] == "before\n"


def test_undo_rejects_later_user_edit(tmp_path: Path) -> None:
    """A later user edit blocks undo rather than being overwritten."""

    service, knowledge = _service(tmp_path)
    service.start_run(user_id="u", session_id="s", run_id="r")
    service.record_edit(user_id="u", run_id="r", path="note.md", before="before\n", after="after\n")
    snapshot = service.finalize_run(run_id="r")
    assert snapshot is not None
    knowledge.files["note.md"] = "user edit\n"
    try:
        service.undo_snapshot(snapshot_id=snapshot["snapshot_id"], user_id="u")
    except ValueError as exc:
        assert "file changed after this turn" in str(exc)
    else:
        raise AssertionError("undo must reject later user edits")
