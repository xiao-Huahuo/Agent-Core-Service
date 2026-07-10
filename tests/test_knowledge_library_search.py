"""
知识库文件内容搜索回归测试。

功能说明:
验证知识库搜索在向量/全文索引尚未更新时,仍能通过磁盘文件内容直搜找到当前
active 知识库中的文本。
"""

from types import SimpleNamespace

from agent_service.services.knowledge_library_service import KnowledgeLibraryService


class _SettingsServiceStub:
    """测试用设置服务,只返回当前 active 知识库目录。"""

    def __init__(self, knowledge_dir: str) -> None:
        """保存测试知识库目录。"""

        self.knowledge_dir = knowledge_dir

    def get_active_knowledge_library(self, *, user_id: str) -> dict[str, str]:
        """返回测试用户的 active 知识库配置。"""

        return {"knowledge_dir": self.knowledge_dir}


def test_search_file_contents_finds_unindexed_disk_content(tmp_path) -> None:
    """文件尚未灌库时,内容搜索仍应直接命中磁盘中的 UTF-8 文本。"""

    note_path = tmp_path / "notes.md"
    note_path.write_text("第一段\n明确存在的搜索短语\n第三段", encoding="utf-8")
    config = SimpleNamespace(constants=SimpleNamespace(knowledge_supported_suffixes=[".md", ".txt"]))
    service = KnowledgeLibraryService(
        config=config,
        memory_service=SimpleNamespace(),
        settings_service=_SettingsServiceStub(str(tmp_path)),
    )

    results = service.search_file_contents(user_id="user-1", query="存在的搜索短语")

    assert results == [{"source_uri": str(note_path), "snippet": "第一段\n明确存在的搜索短语\n第三段"}]
