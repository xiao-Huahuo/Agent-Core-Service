"""DSH Runtime受管资源服务的磁盘状态与租约回归测试。"""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import zipfile

import pytest

from agent_service.core.agent_config import AgentConfig
from agent_service.services.dsh_runtime import DshRuntimePackageManager


def _manager(tmp_path, bundle_dir=None) -> DshRuntimePackageManager:
    """创建使用指定内置制品目录的临时 DSH资源管理器。"""

    config = AgentConfig.load_config(
        overrides={
            "storage": {"base_data_dir": str(tmp_path), "dsh_sdk_dir": "assets/sdks/dsh"},
            "dsh": {"runtime_version": "test-v1"},
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    return DshRuntimePackageManager(config=config, bundle_dir=bundle_dir)


def _embedded_bundle(tmp_path):
    """生成只含测试文件的内置 manifest与 ZIP。"""

    bundle_dir = tmp_path / "embedded"
    bundle_dir.mkdir()
    archive = bundle_dir / "dsh-runtime-win-x64-test-v1.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("runtime.exe", b"runtime")
        package.writestr("launcher.exe", b"launcher")
        package.writestr("config/mw.patch.yml", b"config")
    manifest = {
        "version": "test-v1",
        "platform": "windows",
        "arch": "x64",
        "archive_file": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_size_bytes": archive.stat().st_size,
        "installed_size_bytes": len(b"runtimelauncherconfig"),
        "executable": "runtime.exe",
        "launcher": "launcher.exe",
        "cordis_configs": {"sandbox": "config/mw.patch.yml"},
        "launch_args": {"sandbox": ["{runtime}"]},
    }
    (bundle_dir / "dsh-runtime-win-x64-test-v1.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8",
    )
    return bundle_dir


def test_runtime_manager_resolves_installed_bundle_and_blocks_in_use_uninstall(tmp_path) -> None:
    """ready版本应解析 argv，并在有租约时拒绝卸载。"""

    manager = _manager(tmp_path)
    version_dir = manager.versions_dir / "test-v1"
    (version_dir / "config").mkdir(parents=True)
    for relative in ("runtime.exe", "launcher.exe", "config/mw.patch.yml"):
        target = version_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")
    manifest = {
        "executable": "runtime.exe",
        "launcher": "launcher.exe",
        "cordis_configs": {"sandbox": "config/mw.patch.yml"},
        "launch_args": {"sandbox": ["{runtime}", "--patch", "{root}/config/mw.patch.yml"]},
    }
    (version_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manager.current_file.write_text(
        json.dumps({"version": "test-v1", "executable": "runtime.exe"}),
        encoding="utf-8",
    )

    assert manager.get_management_status()["status"] == "ready"
    assert manager.resolve_launcher() == (version_dir / "launcher.exe").resolve()
    assert manager.resolve_runtime_launch_args("sandbox") == (
        str((version_dir / "runtime.exe").resolve()),
        "--patch",
        str((version_dir / "config" / "mw.patch.yml").resolve()),
    )
    manager.acquire_runtime("child-1")
    with pytest.raises(ValueError, match="正在被子 Agent 使用"):
        manager.uninstall()
    manager.release_runtime("child-1")
    assert manager.uninstall()["status"] == "missing"
    assert not version_dir.exists()


def test_runtime_manager_lazily_extracts_embedded_bundle_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首次租用应从 EXE内置 ZIP解压，且绝不访问网络。"""

    manager = _manager(tmp_path, _embedded_bundle(tmp_path))
    monkeypatch.setattr(manager, "_self_check", lambda launcher, executable: None)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("内置 SDK安装不得访问网络"),
    )

    assert manager.get_management_status()["status"] == "missing"
    assert not (manager.versions_dir / "test-v1").exists()
    executable = manager.acquire_runtime("child-1")

    assert executable.read_bytes() == b"runtime"
    assert manager.get_management_status()["status"] == "ready"
    manager.release_runtime("child-1")


def test_runtime_manager_refuses_install_without_embedded_bundle(tmp_path) -> None:
    """开发运行缺少内置 SDK制品时应明确拒绝安装。"""

    manager = _manager(tmp_path, tmp_path / "missing-bundle")
    with pytest.raises(ValueError, match="内置 SDK"):
        manager.start_install()


def test_runtime_manager_preserves_repair_failure_when_old_runtime_still_exists(tmp_path) -> None:
    """修复失败后不得因旧 executable 尚在就把 failed 状态伪装回 ready。"""

    manager = _manager(tmp_path)
    version_dir = manager.versions_dir / "test-v1"
    version_dir.mkdir(parents=True)
    (version_dir / "runtime.exe").write_bytes(b"old-runtime")
    manager.current_file.write_text(
        json.dumps({"version": "test-v1", "executable": "runtime.exe"}),
        encoding="utf-8",
    )
    manager._set_progress("failed", "repair self-check failed")

    status = manager.get_management_status()

    assert status["status"] == "failed"
    assert status["message"] == "repair self-check failed"


@pytest.mark.skipif(os.name != "nt", reason="Windows MAX_PATH regression")
def test_runtime_manager_extracts_required_node_file_beyond_max_path(tmp_path) -> None:
    """受管 ZIP 的深层 Node 依赖必须通过扩展路径完整解压。"""

    manager = _manager(tmp_path)
    archive = tmp_path / "long-path.zip"
    relative = Path(*(["nested-segment"] * 18), "runtime.js")
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(relative.as_posix(), b"module.exports = true;")
    destination = tmp_path / "extracted"

    manager._extract_archive(archive, destination, total_bytes=0)

    assert manager._windows_io_path(destination / relative).read_bytes() == b"module.exports = true;"
