"""
用户 LLM 配置测试。

覆盖大/小模型配置继承和已保存模型配置的持久化行为。
"""

from __future__ import annotations

from sqlmodel import create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.services.settings_service import SettingsService


class _MemoryServiceStub:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")


def make_settings_service() -> SettingsService:
    config = AgentConfig.load_config(
        {},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    return SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]


def test_llm_config_small_model_inherits_large_model_fields() -> None:
    service = make_settings_service()

    config = service.save_llm_config(
        user_id="u1",
        api_key="large-key",
        base_url="https://large.example.com/v1",
        model_name="large-model",
        small_api_key="",
        small_base_url="",
        small_model_name="",
    )

    assert config["api_key"] == "large-key"
    assert config["base_url"] == "https://large.example.com/v1"
    assert config["model_name"] == "large-model"
    assert config["small_api_key"] == ""
    assert config["small_base_url"] == ""
    assert config["small_model_name"] == ""
    assert config["effective_small_api_key"] == "large-key"
    assert config["effective_small_base_url"] == "https://large.example.com/v1"
    assert config["effective_small_model_name"] == "large-model"


def test_llm_config_empty_small_fields_clear_stale_values() -> None:
    service = make_settings_service()

    service.save_llm_config(
        user_id="u1",
        api_key="large-key",
        base_url="https://large.example.com/v1",
        model_name="large-model",
        small_api_key="stale-small-key",
        small_base_url="https://stale.example.com/v1",
        small_model_name="stale-small-model",
    )

    config = service.save_llm_config(
        user_id="u1",
        small_api_key="",
        small_base_url="",
        small_model_name="",
    )

    assert config["small_api_key"] == ""
    assert config["small_base_url"] == ""
    assert config["small_model_name"] == ""
    assert config["effective_small_api_key"] == "large-key"
    assert config["effective_small_base_url"] == "https://large.example.com/v1"
    assert config["effective_small_model_name"] == "large-model"


def test_llm_config_presets_can_be_saved_listed_and_deleted() -> None:
    service = make_settings_service()

    preset = service.save_llm_config_preset(
        user_id="u1",
        label="DeepSeek",
        api_key="key",
        base_url="https://api.example.com/v1",
        model_name="model-a",
    )

    presets = service.list_llm_config_presets(user_id="u1")

    assert len(presets) == 1
    assert presets[0]["config_id"] == preset["config_id"]
    assert presets[0]["label"] == "DeepSeek"
    assert presets[0]["model_name"] == "model-a"
    assert service.delete_llm_config_preset(config_id=preset["config_id"]) is True
    assert service.list_llm_config_presets(user_id="u1") == []


def test_memory_config_defaults_on_and_persists_user_override() -> None:
    service = make_settings_service()

    assert service.get_memory_config(user_id="u1")["long_term_memory_enabled"] is True
    saved = service.save_memory_config(user_id="u1", long_term_memory_enabled=False)

    assert saved["long_term_memory_enabled"] is False
    assert service.get_memory_config(user_id="u1")["long_term_memory_enabled"] is False


def test_browser_config_persists_separate_proxy_and_home_page() -> None:
    service = make_settings_service()

    initial = service.get_web_search_config(user_id="u1")
    saved = service.save_web_search_config(
        user_id="u1",
        proxy_url="http://127.0.0.1:7890",
        browser_proxy_url="socks5://127.0.0.1:1080",
        browser_home_url="https://example.com/start",
    )

    assert initial["browser_proxy_url"] == ""
    assert initial["browser_home_url"] == "https://www.google.com"
    assert saved["browser_proxy_url"] == "socks5://127.0.0.1:1080"
    assert saved["browser_home_url"] == "https://example.com/start"
    assert service.get_web_search_config(user_id="u1")["proxy_url"] == "http://127.0.0.1:7890"


def test_browser_proxy_override_can_be_cleared_to_restore_inheritance() -> None:
    service = make_settings_service()
    service.save_web_search_config(
        user_id="u1",
        browser_proxy_url="http://127.0.0.1:7891",
    )

    saved = service.save_web_search_config(user_id="u1", browser_proxy_url="")

    assert saved["browser_proxy_url"] == ""


def test_memory_tools_are_disabled_in_available_tool_catalog_when_memory_is_off() -> None:
    service = make_settings_service()
    service.save_memory_config(user_id="u1", long_term_memory_enabled=False)

    groups = service.list_available_tools(user_id="u1")["groups"]
    memory_group = next(group for group in groups if group["category"] == "MEMORY")

    assert memory_group["tools"]
    assert all(tool["enabled"] is False for tool in memory_group["tools"])


def test_floating_launch_setting_persists_in_user_profile() -> None:
    service = make_settings_service()

    saved = service.save_floating_config(user_id="u1", floating_launch_enabled=True)
    profile = service.ensure_user_profile(user_id="u1")

    assert saved["floating_launch_enabled"] is True
    assert profile["floating_launch_enabled"] is True


def test_user_profile_reports_the_effective_supported_knowledge_suffixes() -> None:
    service = make_settings_service()
    service.config.constants.knowledge_supported_suffixes = [".md", ".custom"]

    profile = service.ensure_user_profile(user_id="u1")

    assert profile["knowledge_supported_suffixes"] == [".md", ".custom"]
