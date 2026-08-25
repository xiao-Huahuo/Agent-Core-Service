"""
存储设置服务回归测试。

功能说明:
验证知识库托管目录始终固定在 `.mw` 下，存储设置只展示真实运行路径，
并且运行中只允许清空可安全回收的最近删除目录。

使用说明:
在项目根目录执行 `python -m pytest tests/test_storage_service.py`。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_service.core.agent_config import AgentConfig
from agent_service.services.storage_service import StorageService


class _SettingsStub:
    """提供固定活动知识库，禁止存储服务读取旧路径覆盖。"""

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir

    def get_active_knowledge_library(self, *, user_id: str) -> dict:  # noqa: ARG002
        """返回带旧自定义图书馆路径的资料，验证服务仍固定使用 `.mw/library`。"""

        return {
            "knowledge_dir": str(self.knowledge_dir),
            "library_storage_dir": "legacy-bookshelf",
        }

    def get_storage_path_overrides(self, *, user_id: str) -> dict:  # noqa: ARG002
        """旧路径覆盖不应再参与存储设置解析。"""

        raise AssertionError("legacy storage overrides must not be read")


def _make_service(tmp_path: Path) -> StorageService:
    """创建使用临时知识库和运行目录的存储服务。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(tmp_path),
                "knowledge_dir": str(tmp_path / "knowledge"),
                "base_data_dir": str(tmp_path / "runtime"),
                "sqlite_path": str(tmp_path / "runtime" / "db" / "relation" / "agent_service.db"),
                "chroma_persist_dir": str(tmp_path / "runtime" / "db" / "vector" / "chroma"),
                "relation_db_dir": str(tmp_path / "runtime" / "db" / "relation"),
                "vector_db_dir": str(tmp_path / "runtime" / "db" / "vector"),
                "embedding_model_dir": str(tmp_path / "runtime" / "models" / "embedding"),
                "rerank_model_dir": str(tmp_path / "runtime" / "models" / "rerank"),
                "paddleocr_model_dir": str(tmp_path / "runtime" / "models" / "paddleocr"),
                "log_dir": str(tmp_path / "runtime" / "logs"),
                "assets_dir": str(tmp_path / "runtime" / "assets"),
                "trash_dir": str(tmp_path / "runtime" / "trash"),
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=True,
        ensure_models=False,
    )
    return StorageService(config=config, settings_service=_SettingsStub(tmp_path / "knowledge"))


def test_managed_paths_are_fixed_and_read_only(tmp_path: Path) -> None:
    """所有应用托管知识目录都固定在活动知识库的 `.mw` 下。"""

    service = _make_service(tmp_path)
    response = service.get_storage_config(user_id="u1")
    paths = {entry["key"]: entry for entry in response["paths"]}

    assert Path(paths["managed_root"]["value"]) == tmp_path / "knowledge" / ".mw"
    assert Path(paths["markdown_dir"]["value"]) == tmp_path / "knowledge" / ".mw" / "md"
    assert Path(paths["frontmatter_dir"]["value"]) == tmp_path / "knowledge" / ".mw" / "frontmatter"
    assert Path(paths["library_storage_dir"]["value"]) == tmp_path / "knowledge" / ".mw" / "library"
    assert all(not paths[key]["can_clear"] for key in ("managed_root", "markdown_dir", "frontmatter_dir", "library_storage_dir", "forms_dir", "components_dir"))


def test_storage_paths_cannot_be_overridden(tmp_path: Path) -> None:
    """存储设置 API 不再接受 `.mw` 或运行时路径覆盖。"""

    service = _make_service(tmp_path)

    with pytest.raises(ValueError, match="只读"):
        service.save_storage_config(user_id="u1", paths={"library_storage_dir": "bookshelf"})
    with pytest.raises(ValueError, match="只读"):
        service.save_storage_config(user_id="u1", paths={"base_data_dir": str(tmp_path / "other")})


def test_only_trash_can_be_cleared_while_service_is_running(tmp_path: Path) -> None:
    """数据库、索引、模型和资源目录不可在线删除，最近删除目录可以清空。"""

    service = _make_service(tmp_path)
    trash_file = service.config.storage.trash_dir / "deleted.txt"
    trash_file.write_text("deleted", encoding="utf-8")

    for key in ("sqlite_path", "chroma_persist_dir", "assets_dir", "embedding_model_dir", "log_dir"):
        with pytest.raises(ValueError, match="不允许清空"):
            service.clear_path(path_key=key)

    result = service.clear_path(path_key="trash_dir")

    assert result["freed_bytes"] == len("deleted")
    assert list(service.config.storage.trash_dir.iterdir()) == []


def test_latex_runtime_and_build_cache_are_reported_and_only_caches_are_clearable(tmp_path: Path) -> None:
    """LaTeX 核心运行时不可粗暴清空，仓库、临时目录和 `.mw` 编译缓存可安全回收。"""

    service = _make_service(tmp_path)
    latex_root = service.config.storage.base_data_dir / "latex"
    (latex_root / "miktex" / "engine.bin").parent.mkdir(parents=True)
    (latex_root / "miktex" / "engine.bin").write_bytes(b"runtime")
    (latex_root / "repository" / "package.tar").parent.mkdir(parents=True)
    (latex_root / "repository" / "package.tar").write_bytes(b"repository")
    (latex_root / "temp" / "setup.tmp").parent.mkdir(parents=True)
    (latex_root / "temp" / "setup.tmp").write_bytes(b"temp")
    build_cache = service.settings_service.knowledge_dir / ".mw" / "latex" / "document"
    build_cache.mkdir(parents=True)
    (build_cache / "main.pdf").write_bytes(b"pdf")

    response = service.get_storage_config(user_id="u1")
    paths = {entry["key"]: entry for entry in response["paths"]}

    assert paths["latex_runtime_dir"]["parent"] == "base_data_dir"
    assert paths["latex_distribution_dir"]["can_clear"] is False
    assert paths["latex_repository_dir"]["can_clear"] is True
    assert paths["latex_temp_dir"]["can_clear"] is True
    assert paths["latex_build_cache_dir"]["parent"] == "managed_root"
    assert paths["latex_build_cache_dir"]["can_clear"] is True

    with pytest.raises(ValueError, match="不允许清空"):
        service.clear_path(path_key="latex_distribution_dir", user_id="u1")
    assert service.clear_path(path_key="latex_repository_dir", user_id="u1")["freed_bytes"] == len("repository")
    assert service.clear_path(path_key="latex_build_cache_dir", user_id="u1")["freed_bytes"] == len("pdf")
