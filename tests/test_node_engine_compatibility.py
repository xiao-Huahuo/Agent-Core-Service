"""前端锁文件与项目 Node.js 支持范围回归测试。

使用说明:
当升级前端任务编排依赖时运行本测试，避免锁文件要求高于 package.json 声明的 Node 版本。
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDITOR_ROOT = PROJECT_ROOT / "editor"
SUPPORTED_NODE_ENGINE = "^22.18.0 || >=24.12.0"
COMPATIBLE_RUN_ALL_VERSION = "8.0.4"


def test_frontend_lock_supports_declared_node_engine() -> None:
    """直接依赖和锁定依赖不得超过项目声明的 Node.js 最低版本。"""

    package = json.loads((EDITOR_ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((EDITOR_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    root_lock = lock["packages"][""]
    run_all_lock = lock["packages"]["node_modules/npm-run-all2"]

    assert package["engines"]["node"] == SUPPORTED_NODE_ENGINE
    assert package["devDependencies"]["npm-run-all2"] == COMPATIBLE_RUN_ALL_VERSION
    assert root_lock["devDependencies"]["npm-run-all2"] == COMPATIBLE_RUN_ALL_VERSION
    assert run_all_lock["version"] == COMPATIBLE_RUN_ALL_VERSION

    incompatible = {
        name: metadata["engines"]["node"]
        for name, metadata in lock["packages"].items()
        if metadata.get("engines", {}).get("node") == "^22.22.2 || ^24.15.0 || >=26.0.0"
    }
    assert incompatible == {}


def test_windows_packaging_repairs_missing_electron_runtime_before_build() -> None:
    """完整和单独安装器构建都必须在耗时步骤前检查 Electron 运行时。"""

    package = json.loads((EDITOR_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert scripts["prepare:electron-runtime"] == "node node_modules/electron/install.js"
    assert scripts["predist:win"] == "npm run prepare:electron-runtime"
    assert scripts["prebuild:win-installer"] == "npm run prepare:electron-runtime"
