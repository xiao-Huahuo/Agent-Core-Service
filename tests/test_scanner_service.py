"""Focused scanner service persistence and projection regression tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.services.scanner import ScannerService


class _SettingsStub:
    """Provide one active library without touching user settings storage."""

    def __init__(self, root: Path) -> None:
        """Retain the isolated knowledge root."""

        self.root = root

    def ensure_user_profile(self, *, user_id: str) -> dict:
        """Return the profile fields consumed by ScannerService."""

        return {
            "user_id": user_id,
            "active_knowledge_library": {"library_id": "lib-test", "knowledge_dir": str(self.root)},
            "editor_image_assets_dir": "./assets/",
            "auto_ingest_on_upload": False,
        }


class _KnowledgeStub:
    """Persist saved Markdown into the isolated knowledge root."""

    def __init__(self, root: Path) -> None:
        """Retain the isolated knowledge root."""

        self.root = root

    def write_uploaded_file(self, *, filename: str, content: bytes, **_: object) -> Path:
        """Write the requested Markdown file and return its absolute path."""

        target = self.root / filename
        target.write_bytes(content)
        return target

    def ingest_single_file(self, **_: object) -> None:
        """Record no work because auto ingestion is disabled in this test."""


def test_scanner_text_projection_draft_save_export_and_delete(tmp_path: Path) -> None:
    """Exercise the complete terminal lifecycle without loading OCR models."""

    root = tmp_path / "knowledge"
    root.mkdir()
    engine = create_engine(f"sqlite:///{tmp_path / 'scanner.db'}")
    SQLModel.metadata.create_all(engine)
    config = AgentConfig()
    config.storage.knowledge_dir = root
    service = ScannerService(
        engine=engine,
        config=config,
        settings_service=_SettingsStub(root),  # type: ignore[arg-type]
        knowledge_library_service=_KnowledgeStub(root),  # type: ignore[arg-type]
    )
    try:
        created = service.create_file(user_id="u1", filename="notes.txt", content="alpha\nbeta".encode(), ocr_enabled=False)
        assert created.source_path.startswith(f".mw/scan/{created.scan_id}/source/")
        deadline = time.monotonic() + 8
        current = created
        while current.status in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            current = service.get_scan(user_id="u1", scan_id=created.scan_id)
        assert current.status == "finished", current.error
        assert "alpha" in current.no_ocr_markdown
        assert current.ocr_markdown == ""

        updated = service.update_draft(user_id="u1", scan_id=created.scan_id, variant="no_ocr", content="# Edited\n")
        assert updated.no_ocr_markdown == "# Edited\n"
        saved = service.save_to_knowledge(user_id="u1", scan_id=created.scan_id, variant="no_ocr", conflict_strategy="overwrite")
        assert saved["path"] == "notes.md"
        assert (root / "notes.md").read_text(encoding="utf-8") == "# Edited\n"

        filename, media_type, payload = service.export_payload(user_id="u1", scan_id=created.scan_id, variant="no_ocr")
        assert filename == "notes.zip"
        assert media_type == "application/zip"
        assert payload.startswith(b"PK")

        assert service.delete_scan(user_id="u1", scan_id=created.scan_id)
        assert not (root / ".mw" / "scan" / created.scan_id).exists()

        image = service.create_file(user_id="u1", filename="diagram.png", content=b"not-a-real-png", ocr_enabled=False)
        deadline = time.monotonic() + 8
        image_result = image
        while image_result.status in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            image_result = service.get_scan(user_id="u1", scan_id=image.scan_id)
        assert image_result.status == "finished", image_result.error
        assert "![diagram](./assets/diagram.png)" in image_result.no_ocr_markdown
        assert len(image_result.assets) == 1

        with pytest.raises(ValueError, match="private or local"):
            service.create_url(user_id="u1", url="http://127.0.0.1/private", ocr_enabled=False)
    finally:
        service.stop()
