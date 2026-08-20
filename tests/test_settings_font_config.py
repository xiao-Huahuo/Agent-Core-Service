"""
用户字体设置持久化测试。

验证 UI 与编辑区正文的字号可以独立保存，并在用户档案中独立返回。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings_service import SettingsService


class _MemoryServiceStub:
    """Provide the in-memory database required by SettingsService."""

    def __init__(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")


class _LegacyMemoryServiceStub:
    """Provide a database shaped like the pre-split font settings schema."""

    def __init__(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE user_settings (
                    user_id VARCHAR(128) PRIMARY KEY,
                    knowledge_dir VARCHAR(1024) NOT NULL,
                    font_size_percent INTEGER NOT NULL DEFAULT 100,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """))
            connection.execute(text("""
                INSERT INTO user_settings (
                    user_id, knowledge_dir, font_size_percent, created_at, updated_at
                ) VALUES (
                    'legacy-user', 'D:/Knowledge', 115,
                    '2026-08-20 00:00:00', '2026-08-20 00:00:00'
                )
            """))


def _make_settings_service() -> SettingsService:
    """Create an isolated settings service for font persistence checks."""

    config = AgentConfig.load_config(
        {},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    return SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]


def test_font_sizes_persist_independently_in_user_profile() -> None:
    """Changing one font-size setting must not overwrite the other setting."""

    service = _make_settings_service()

    saved = service.save_font_config(
        user_id="u1",
        ui_font_size_percent=90,
        text_font_size_percent=125,
    )
    profile = service.ensure_user_profile(user_id="u1")

    assert saved["ui_font_size_percent"] == 90
    assert saved["text_font_size_percent"] == 125
    assert profile["ui_font_size_percent"] == 90
    assert profile["text_font_size_percent"] == 125


def test_legacy_font_size_initializes_both_independent_sizes() -> None:
    """Old clients keep their previous visual size when they save the legacy field."""

    service = _make_settings_service()

    saved = service.save_font_config(user_id="u1", font_size_percent=110)

    assert saved["ui_font_size_percent"] == 110
    assert saved["text_font_size_percent"] == 110


def test_schema_upgrade_copies_legacy_size_into_both_new_columns() -> None:
    """Existing database rows retain their shared size after the schema split."""

    config = AgentConfig.load_config(
        {},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    service = SettingsService(
        config=config,
        memory_service=_LegacyMemoryServiceStub(),  # type: ignore[arg-type]
    )

    profile = service.ensure_user_profile(user_id="legacy-user")

    assert profile["ui_font_size_percent"] == 115
    assert profile["text_font_size_percent"] == 115
