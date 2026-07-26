"""
图书馆虚拟编目服务测试。

功能说明:
验证图书馆页是主动维护的虚拟编目层:初始为空,集锦和图书都写入 SQLite,
删除图书馆条目不会删除真实知识库文件。

使用说明:
在项目根目录执行 `python -m pytest tests/test_library_service.py`。
"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.services.library_service import LibraryService
from agent_service.services.settings_service import SettingsService


class _MemoryServiceStub:
    """SettingsService 测试用内存数据库依赖。"""

    def __init__(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")


class _KnowledgeLibraryServiceStub:
    """LibraryService 测试用真实文件状态依赖。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    def list_files(self, *, user_id: str) -> list[dict]:  # noqa: ARG002
        """返回测试知识库文件树。"""

        return [
            {
                "name": "paper.md",
                "path": "paper.md",
                "isDir": False,
                "mtime": "2026-07-26 10:00",
                "indexStatus": "dirty",
                "graphStatus": "dirty",
            }
        ]


class _KnowledgeGraphServiceStub:
    """LibraryService 测试用图谱状态依赖。"""

    def list_document_statuses(self, *, user_id: str, library_id: str) -> dict[str, str]:  # noqa: ARG002
        """返回固定图谱状态。"""

        return {"paper.md": "dirty"}


def make_service(tmp_path: Path) -> LibraryService:
    """创建图书馆测试服务。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "knowledge_dir": str(tmp_path),
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_directories=False,
        ensure_models=False,
    )
    settings = SettingsService(config=config, memory_service=_MemoryServiceStub())  # type: ignore[arg-type]
    return LibraryService(
        config=config,
        settings_service=settings,
        knowledge_library_service=_KnowledgeLibraryServiceStub(tmp_path),  # type: ignore[arg-type]
        knowledge_graph_service=_KnowledgeGraphServiceStub(),  # type: ignore[arg-type]
    )


def test_library_starts_empty_until_user_adds_items(tmp_path: Path) -> None:
    """图书馆初始为空,不会镜像真实知识库文件。"""

    (tmp_path / "paper.md").write_text("hello", encoding="utf-8")
    service = make_service(tmp_path)

    response = service.list_items(user_id="u1")

    assert response["items"] == []


def test_collection_and_book_are_virtual_metadata(tmp_path: Path) -> None:
    """集锦和图书条目写入虚拟编目,真实文件只被 source_path 引用。"""

    (tmp_path / "paper.md").write_text("hello", encoding="utf-8")
    service = make_service(tmp_path)

    collection = service.create_collection(user_id="u1", title="论文集", tags=["paper"])["item"]
    book = service.create_item(
        user_id="u1",
        parent_id=collection["item_id"],
        content_type="knowledge_file",
        source_path="paper.md",
        title="原论文",
        description="注意力机制资料",
        tags=["paper", "ai"],
    )["item"]
    response = service.list_items(user_id="u1", parent_id=collection["item_id"], tag="ai")

    assert book["source_name"] == "paper.md"
    assert book["index_status"] == "dirty"
    assert response["items"][0]["display_title"] == "原论文"
    assert response["breadcrumbs"][0]["title"] == "论文集"
    assert (tmp_path / "paper.md").exists()


def test_delete_library_item_does_not_delete_real_file(tmp_path: Path) -> None:
    """移出图书馆只删除虚拟条目,不删除真实知识库文件。"""

    source = tmp_path / "paper.md"
    source.write_text("hello", encoding="utf-8")
    service = make_service(tmp_path)
    book = service.create_item(
        user_id="u1",
        content_type="knowledge_file",
        source_path="paper.md",
        title="原论文",
    )["item"]

    result = service.delete_item(user_id="u1", item_id=book["item_id"])
    response = service.list_items(user_id="u1")

    assert result["ok"] is True
    assert response["items"] == []
    assert source.read_text(encoding="utf-8") == "hello"
