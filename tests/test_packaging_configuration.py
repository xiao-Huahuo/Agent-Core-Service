"""Windows 发布配置与外置资源路径回归测试。

使用说明:
这些测试只检查打包清单和轻量路径行为，不执行 PyInstaller 或 Electron 构建。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from agent_service.api.rest import settings as settings_api
from agent_service.core.agent_config import AgentConfig
from agent_service.services.safety.safety_service import SafetyService
from scripts.build_dsh_windows_bundle import verify_bundle_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config_for_project(project_root: Path) -> AgentConfig:
    """构造不创建运行目录、不加载模型的项目级测试配置。"""

    return AgentConfig.load_config(
        {"storage": {"project_root": str(project_root)}},
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )


def _write_sensitive_words(path: Path, blocked_word: str) -> None:
    """写入只包含一个阻断词的最小敏感词配置。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "categories": {
                    "packaging": {
                        "name": "打包回归",
                        "risk_level": "high",
                        "block": True,
                        "exact": [blocked_word],
                        "regex": [],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_pyinstaller_spec_collects_runtime_files_without_all_service_submodules() -> None:
    """发布 exe 必须携带迁移文件，同时避免全量收集后端包。"""

    spec = (PROJECT_ROOT / "AgentService.spec").read_text(encoding="utf-8")

    assert "_snapshot_required_data_dir('editor/dist')" in spec
    assert "_required_data_dir('agent_service/core/db/alembic')" in spec
    assert "_required_data_file('alembic.ini')" in spec
    assert "_required_dsh_sdk_bundle()" in spec
    assert "collect_submodules('agent_service')" not in spec
    assert "['xlrd', 'torchvision']" in spec


def test_checked_in_dsh_sdk_bundle_matches_locked_release() -> None:
    """正式 EXE将收集的内置 SDK必须通过版本、大小和 SHA-256门禁。"""

    archive, manifest = verify_bundle_files(PROJECT_ROOT / "resources" / "dsh" / "sdk")

    assert archive.stat().st_size == 66_008_168
    assert manifest.is_file()


def test_backend_direct_runtime_dependencies_are_declared() -> None:
    """代码直接导入的运行依赖不得依赖当前机器的传递安装结果。"""

    requirements = (PROJECT_ROOT / "agent_service" / "requirements.txt").read_text(encoding="utf-8")
    declared = {
        line.split("==", maxsplit=1)[0].split(">=", maxsplit=1)[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "--"))
    }

    assert {"numpy", "pyyaml", "xlrd", "fpdf2"} <= declared


def test_safety_service_uses_and_reloads_project_sensitive_words(tmp_path: Path) -> None:
    """安装版安全审核必须读取用户项目目录中的可持久化词库。"""

    config = _config_for_project(tmp_path)
    sensitive_words_path = tmp_path / "resources" / "safety" / "sensitive_words.json"
    _write_sensitive_words(sensitive_words_path, "first-blocked-word")
    service = SafetyService(config=config)

    assert service.sensitive_words_path == sensitive_words_path.resolve()
    assert service._sensitive_checker is not None
    assert service._sensitive_checker.check("first-blocked-word").blocked is True

    _write_sensitive_words(sensitive_words_path, "second-blocked-word")
    service.reload_sensitive_words()

    assert service._sensitive_checker is not None
    assert service._sensitive_checker.check("first-blocked-word").blocked is False
    assert service._sensitive_checker.check("second-blocked-word").blocked is True


def test_safety_settings_endpoint_reads_project_sensitive_words(tmp_path: Path, monkeypatch: object) -> None:
    """安全设置接口必须通过同一个外置词库完成读取、保存与热重载。"""

    config = _config_for_project(tmp_path)
    sensitive_words_path = tmp_path / "resources" / "safety" / "sensitive_words.json"
    _write_sensitive_words(sensitive_words_path, "endpoint-blocked-word")
    monkeypatch.setattr(
        settings_api,
        "_require_settings_service",
        lambda: SimpleNamespace(config=config),
    )
    reload_calls: list[bool] = []
    monkeypatch.setattr(
        settings_api,
        "_require_agent",
        lambda: SimpleNamespace(
            safety_service=SimpleNamespace(reload_sensitive_words=lambda: reload_calls.append(True)),
        ),
    )

    payload = asyncio.run(settings_api.get_sensitive_words())
    replacement = {"categories": {"replacement": {"exact": ["saved-word"]}}}
    response = asyncio.run(settings_api.save_sensitive_words(replacement))

    assert payload["categories"]["packaging"]["exact"] == ["endpoint-blocked-word"]
    assert response == {"ok": True}
    assert json.loads(sensitive_words_path.read_text(encoding="utf-8")) == replacement
    assert reload_calls == [True]
