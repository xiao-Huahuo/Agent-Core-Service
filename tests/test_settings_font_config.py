"""
用户字体设置持久化测试。

验证 UI 与编辑区正文的字号可以独立保存，并在用户档案中独立返回。
"""

from __future__ import annotations

from tests.db_test_utils import create_test_engine as create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings.service import SettingsService


class _MemoryServiceStub:
    """Provide the in-memory database required by SettingsService."""

    def __init__(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")


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
