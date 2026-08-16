"""
Component library filesystem service tests.

Usage:
Verifies that component source lives only below the active knowledge library's
components directory, persists across service instances, and stays excluded
from normal knowledge ingestion.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from agent_service.services.component_library_service import COMPONENT_TAGS, ComponentLibraryService
from agent_service.services.knowledge_library_service import KnowledgeIgnoreMatcher


class _SettingsStub:
    """Resolve one isolated active knowledge library for service tests."""

    def __init__(self, root: Path) -> None:
        """Retain the temporary knowledge root."""

        self.root = root

    def ensure_user_profile(self, *, user_id: str) -> dict[str, object]:
        """Return the same profile shape as SettingsService."""

        return {
            "user_id": user_id,
            "active_knowledge_library": {
                "library_id": "test-library",
                "knowledge_dir": str(self.root),
            },
        }


def _service(tmp_path: Path) -> ComponentLibraryService:
    """Create a component service bound to one temporary knowledge root."""

    return ComponentLibraryService(settings_service=_SettingsStub(tmp_path))


def test_components_are_read_only_from_active_knowledge_components_directory(tmp_path: Path) -> None:
    """Unrelated supercomponents files must not appear in the user component library."""

    external = tmp_path.parent / "supercomponents" / "new"
    external.mkdir(parents=True, exist_ok=True)
    (external / "保存按钮.vue").write_text("<template><button>保存</button></template>", encoding="utf-8")

    result = _service(tmp_path).list_components(user_id="u1", tag="any")

    assert result == {"components": [], "tags": list(COMPONENT_TAGS)}


def test_uploaded_component_is_a_utf8_file_and_survives_service_instances(tmp_path: Path) -> None:
    """A component upload must persist as source under components/<tag>."""

    service = _service(tmp_path)
    source = "<template><input placeholder=\"邮箱\" /></template>"
    created = service.create_component(user_id="u1", source=source, tag="inputs", filename="email.vue")

    stored_path = tmp_path / "components" / "inputs" / "email.vue"
    assert stored_path.read_text(encoding="utf-8") == source
    assert created["component"]["component_id"] == "inputs/email.vue"
    assert created["component"]["builtin"] is False

    filtered = _service(tmp_path).list_components(user_id="u1", tag="inputs")
    assert filtered["components"] == [created["component"]]


def test_upload_uses_safe_unique_names_and_supported_extensions(tmp_path: Path) -> None:
    """File names may not escape components and collisions must not overwrite source."""

    service = _service(tmp_path)
    first = service.create_component(user_id="u1", source="<button>One</button>", tag="buttons", filename="button.html")
    second = service.create_component(user_id="u1", source="<button>Two</button>", tag="buttons", filename="button.html")

    assert first["component"]["title"] == "button"
    assert second["component"]["title"] == "button-2"
    assert (tmp_path / "components" / "buttons" / "button.html").read_text(encoding="utf-8") == "<button>One</button>"
    assert (tmp_path / "components" / "buttons" / "button-2.html").read_text(encoding="utf-8") == "<button>Two</button>"

    with pytest.raises(ValueError, match="supported component file"):
        service.create_component(user_id="u1", source="x", tag="buttons", filename="component.js")
    with pytest.raises(ValueError, match="file name"):
        service.create_component(user_id="u1", source="x", tag="buttons", filename="../escape.vue")


def test_component_rename_moves_the_source_file_and_updates_the_visible_title(tmp_path: Path) -> None:
    """Inline renaming must persist by moving the canonical component file."""

    service = _service(tmp_path)
    source = "<template><button>保存</button></template>"
    created = service.create_component(user_id="u1", source=source, tag="buttons", filename="old-name.vue")

    renamed = service.rename_component(
        user_id="u1",
        component_id=str(created["component"]["component_id"]),
        title="保存按钮",
    )

    assert renamed["component"]["title"] == "保存按钮"
    assert renamed["component"]["component_id"] == "buttons/保存按钮.vue"
    assert not (tmp_path / "components" / "buttons" / "old-name.vue").exists()
    assert (tmp_path / "components" / "buttons" / "保存按钮.vue").read_text(encoding="utf-8") == source
    assert service.list_components(user_id="u1", tag="buttons")["components"] == [renamed["component"]]


def test_create_component_rejects_unknown_tags_and_oversized_source(tmp_path: Path) -> None:
    """The filesystem trust boundary must retain tag and source validation."""

    service = _service(tmp_path)
    with pytest.raises(ValueError, match="unsupported component tag"):
        service.create_component(user_id="u1", source="<button>OK</button>", tag="menus")
    with pytest.raises(ValueError, match="too large"):
        service.create_component(user_id="u1", source="x" * 250_001, tag="any")


def test_components_directory_is_ignored_by_application_default() -> None:
    """Component sources must not enter file-tree ingestion even without user rules."""

    matcher = KnowledgeIgnoreMatcher("")

    assert matcher.is_ignored("components", is_dir=True)
    assert matcher.is_ignored("components/buttons/example.vue")
    assert not matcher.is_ignored("notes/example.md")


def test_legacy_database_rows_migrate_to_files_before_their_rows_are_deleted(tmp_path: Path) -> None:
    """Existing uploads remain visible after changing the canonical storage."""

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE component_library_items ("
            "component_id TEXT PRIMARY KEY, user_id TEXT, title TEXT, tag TEXT, "
            "source_format TEXT, source TEXT)"
        ))
        connection.execute(
            text(
                "INSERT INTO component_library_items "
                "(component_id, user_id, title, tag, source_format, source) "
                "VALUES ('legacy-1', 'u1', '旧按钮', 'buttons', 'vue', :source)"
            ),
            {"source": "<template><button>旧按钮</button></template>"},
        )
    service = ComponentLibraryService(
        settings_service=_SettingsStub(tmp_path),
        legacy_engine=engine,
    )

    listed = service.list_components(user_id="u1", tag="buttons")

    assert listed["components"][0]["title"] == "旧按钮"
    assert (tmp_path / "components" / "buttons" / "旧按钮.vue").is_file()
    with engine.begin() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM component_library_items")).scalar_one() == 0
