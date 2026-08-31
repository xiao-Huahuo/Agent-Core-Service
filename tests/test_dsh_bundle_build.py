"""验证 DSH Runtime构建只接受 MW 锁定的上游源码与版本。

本测试不执行实际 Node构建，只覆盖发布入口最前面的不可绕过校验。
"""

import json
from pathlib import Path
from subprocess import CompletedProcess
import subprocess

import pytest

from scripts import build_dsh_windows_bundle as bundle


def test_verify_upstream_accepts_only_locked_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """锁定提交和 Runtime版本同时匹配时返回构建元数据。"""

    lock = bundle.json.loads(bundle.UPSTREAM_LOCK.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        bundle.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, f"{lock['commit']}\n", ""),
    )

    assert bundle.verify_upstream(Path("dsh"), str(lock["runtime_version"])) == lock


@pytest.mark.parametrize("wrong_input", ["commit", "version"])
def test_verify_upstream_rejects_unlocked_input(
    monkeypatch: pytest.MonkeyPatch,
    wrong_input: str,
) -> None:
    """源码提交或 Runtime版本任一漂移时构建立即失败。"""

    lock = bundle.json.loads(bundle.UPSTREAM_LOCK.read_text(encoding="utf-8"))
    actual_commit = "0" * 40 if wrong_input == "commit" else str(lock["commit"])
    requested_version = "unlocked" if wrong_input == "version" else str(lock["runtime_version"])
    monkeypatch.setattr(
        bundle.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, f"{actual_commit}\n", ""),
    )

    with pytest.raises(RuntimeError):
        bundle.verify_upstream(Path("dsh"), requested_version)


def test_verify_bundle_files_requires_exact_locked_artifacts(tmp_path: Path) -> None:
    """EXE门禁只接受与锁定版本、大小和哈希完全一致的 manifest与 ZIP。"""

    lock = json.loads(bundle.UPSTREAM_LOCK.read_text(encoding="utf-8"))
    version = str(lock["runtime_version"])
    archive = tmp_path / f"dsh-runtime-win-x64-{version}.zip"
    archive.write_bytes(b"sdk")
    manifest = {
        "version": version,
        "source_commit": lock["commit"],
        "patch_sha256": bundle.sha256(bundle.MW_PATCH),
        "archive_file": archive.name,
        "archive_size_bytes": archive.stat().st_size,
        "archive_sha256": bundle.sha256(archive),
    }
    (tmp_path / f"dsh-runtime-win-x64-{version}.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8",
    )

    assert bundle.verify_bundle_files(tmp_path) == (
        archive.resolve(),
        tmp_path / f"dsh-runtime-win-x64-{version}.manifest.json",
    )
    archive.unlink()
    with pytest.raises(FileNotFoundError, match="缺少 DSH SDK ZIP"):
        bundle.verify_bundle_files(tmp_path)


def test_prepared_dsh_source_checks_out_lock_and_applies_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全新构建应克隆锁定提交、应用 MW补丁且不修改来源仓库。"""

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True)
    (source / "demo.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "demo.txt"], cwd=source, check=True)
    subprocess.run(
        ["git", "-c", "user.name=MetaWeave", "-c", "user.email=build@metaweave.local", "commit", "-m", "base"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, check=True, capture_output=True, text=True,
    ).stdout.strip()
    lock_path = tmp_path / "upstream.json"
    lock_path.write_text(json.dumps({
        "repository": str(source), "commit": commit, "runtime_version": "test-v1",
    }), encoding="utf-8")
    patch_path = tmp_path / "mw.patch"
    patch_path.write_text(
        "diff --git a/demo.txt b/demo.txt\n"
        "index df967b9..b66ba06 100644\n"
        "--- a/demo.txt\n"
        "+++ b/demo.txt\n"
        "@@ -1 +1 @@\n"
        "-base\n"
        "+patched\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bundle, "UPSTREAM_LOCK", lock_path)
    monkeypatch.setattr(bundle, "MW_PATCH", patch_path)

    with bundle.prepared_dsh_source(source) as checkout:
        temporary_clone = checkout.parent
        assert (checkout / "demo.txt").read_text(encoding="utf-8") == "patched\n"
    assert not temporary_clone.exists()
    assert (source / "demo.txt").read_text(encoding="utf-8") == "base\n"
