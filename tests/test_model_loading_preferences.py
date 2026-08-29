"""模型自动下载用户设置的持久化测试。

使用说明:
验证自动下载默认关闭，且只把用户显式选择写入正式 user_settings 表。
"""

from __future__ import annotations

from tests.db_test_utils import create_test_engine as create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings.service import SettingsService


class _MemoryServiceStub:
    """提供 SettingsService 所需的隔离数据库。"""

    def __init__(self) -> None:
        """创建当前测试独占的内存数据库。"""

        self.engine = create_engine("sqlite:///:memory:")


def _make_settings_service() -> SettingsService:
    """创建不下载任何真实模型的设置服务。"""

    config = AgentConfig.load_config({}, load_env=False, ensure_directories=False, ensure_models=False)
    return SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]


def test_model_auto_download_defaults_to_false_and_persists() -> None:
    """新用户必须默认关闭自动下载，开启后由后端档案稳定返回。"""

    service = _make_settings_service()

    assert service.ensure_user_profile(user_id="u1")["model_auto_download_enabled"] is False

    saved = service.save_model_preferences(user_id="u1", auto_download_enabled=True)

    assert saved == {"user_id": "u1", "auto_download_enabled": True}
    assert service.get_model_preferences(user_id="u1")["auto_download_enabled"] is True
    assert service.ensure_user_profile(user_id="u1")["model_auto_download_enabled"] is True
