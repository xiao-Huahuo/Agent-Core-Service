"""四库联合搜索服务的来源门控、命中合并与真实语义链路测试。

使用说明：仅运行本文件即可验证用户选择的库决定实际调用范围，且语义结果来自
向量检索服务而不是部分匹配结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from agent_service.services.unified_search.service import UnifiedSearchService


class _SettingsStub:
    """返回固定用户与当前知识库，供隔离断言使用。"""

    def ensure_user_profile(self, *, user_id: str) -> dict[str, object]:
        """构造当前 active library 上下文。"""

        return {
            "user_id": user_id,
            "active_knowledge_library": {
                "library_id": "lib-current",
                "knowledge_dir": "D:/knowledge/current",
            },
        }


class _UnusedService:
    """任何调用都会失败，用于证明未选中的库没有执行搜索。"""

    def __getattr__(self, name: str):
        """为任意意外业务调用返回立即失败的函数。"""

        def fail(**_: object) -> object:
            raise AssertionError(f"unexpected call: {name}")

        return fail


class _ComponentStub:
    """提供两条真实组件源码候选。"""

    def list_components(self, *, user_id: str, tag: str = "any") -> dict[str, object]:
        """返回属于请求用户的组件数据。"""

        assert user_id == "u1"
        assert tag == "any"
        return {
            "tags": ["buttons", "cards", "any"],
            "components": [
                {
                    "component_id": "buttons/SaveButton.vue",
                    "user_id": user_id,
                    "title": "SaveButton",
                    "tag": "buttons",
                    "source_format": "vue",
                    "source": "<template><button aria-label=\"Save\">保存草稿</button></template>",
                    "builtin": False,
                    "created_at": None,
                    "updated_at": "2026-08-29T10:00:00+00:00",
                },
                {
                    "component_id": "cards/ChartCard.vue",
                    "user_id": user_id,
                    "title": "ChartCard",
                    "tag": "cards",
                    "source_format": "vue",
                    "source": "<template><article>季度图表</article></template>",
                    "builtin": False,
                    "created_at": None,
                    "updated_at": "2026-08-29T09:00:00+00:00",
                },
            ],
        }


class _MemoryStub:
    """记录语义索引同步，并模拟已有哈希命中。"""

    def __init__(self, *, indexed: bool = True) -> None:
        """初始化同步调用记录。"""

        self.deleted: list[str] = []
        self.indexed = indexed
        self.created: list[object] = []

    def list_source_ids(self, **_: object) -> set[str]:
        """返回当前组件来源，避免测试触发真实写库。"""

        return {
            "unified:components:buttons/SaveButton.vue",
            "unified:components:cards/ChartCard.vue",
        } if self.indexed else set()

    def has_source_hash(self, **_: object) -> bool:
        """声明候选已按最新内容建立向量索引。"""

        return self.indexed

    def delete_memories_for_source(self, *, source_id: str, **_: object) -> int:
        """记录意外的索引删除。"""

        self.deleted.append(source_id)
        return 1

    def create_memory(self, memory: object) -> object:
        """记录新建的真实向量记忆 DTO。"""

        self.created.append(memory)
        return memory


@dataclass
class _SemanticMemory:
    """模拟 MemoryRetrievalService 返回的可溯源记忆。"""

    source_id: str
    content: str
    metadata_json: dict[str, object]


@dataclass
class _SemanticHit:
    """模拟带最终相关度的语义召回项。"""

    memory: _SemanticMemory
    final_score: float


class _RetrievalStub:
    """提供组件语义召回，并记录用户隔离标识。"""

    def __init__(self, *, indexed: bool = True) -> None:
        """构造检索配置和调用记录。"""

        self.config = SimpleNamespace(
            constants=SimpleNamespace(knowledge_tag="Knowledge"),
            memory=SimpleNamespace(chunk_size=512, chunk_overlap=64, rerank_top_k=20),
            model=SimpleNamespace(embedding_model_name="test-embedding"),
        )
        self.memory_service = _MemoryStub(indexed=indexed)
        self.embedding_service = SimpleNamespace(embed_texts=lambda texts: [[1.0] for _ in texts])
        self.semantic_owner = ""

    def retrieve_unified_search(self, *, query: str, user_id: str, top_k: int) -> list[_SemanticHit]:
        """返回只有真实语义链路才能产生的 ChartCard 命中。"""

        assert query == "数据可视化"
        assert top_k == 20
        self.semantic_owner = user_id
        return [
            _SemanticHit(
                memory=_SemanticMemory(
                    source_id="unified:components:cards/ChartCard.vue",
                    content="ChartCard cards 季度图表",
                    metadata_json={"source": "components", "library_id": "lib-current"},
                ),
                final_score=0.87,
            )
        ]


def _service(*, retrieval: object | None = None) -> UnifiedSearchService:
    """建立只允许组件库访问的联合搜索服务。"""

    return UnifiedSearchService(
        settings_service=_SettingsStub(),
        knowledge_library_service=_UnusedService(),
        library_service=_UnusedService(),
        component_library_service=_ComponentStub(),
        smart_form_service=_UnusedService(),
        retrieval_service=retrieval or _RetrievalStub(),
    )


def test_selected_sources_gate_real_backend_calls_and_merge_title_with_fulltext() -> None:
    """只选组件库时不得访问另外三库，标题与源码命中合并为一条。"""

    result = _service().search(
        user_id="u1",
        query="Save",
        sources={"components"},
        fulltext=True,
        semantic=False,
    )

    assert result["selected_sources"] == ["components"]
    assert result["counts"] == {"files": 0, "library": 0, "components": 1, "literature": 0}
    assert len(result["results"]) == 1
    assert result["results"][0]["source"] == "components"
    assert result["results"][0]["matched_modes"] == ["title", "fulltext"]
    assert result["results"][0]["item"]["component_id"] == "buttons/SaveButton.vue"


def test_semantic_mode_uses_vector_retrieval_and_active_library_owner() -> None:
    """语义开关必须调用真实检索入口，并用当前知识库 owner 隔离索引。"""

    retrieval = _RetrievalStub()
    result = _service(retrieval=retrieval).search(
        user_id="u1",
        query="数据可视化",
        sources={"components"},
        fulltext=False,
        semantic=True,
    )

    assert retrieval.semantic_owner == "u1::knowledge::lib-current"
    assert retrieval.memory_service.deleted == []
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "cards/ChartCard.vue"
    assert result["results"][0]["matched_modes"] == ["semantic"]
    assert result["results"][0]["score"] == 0.87


def test_changed_component_is_embedded_and_persisted_before_semantic_retrieval() -> None:
    """首次或内容变化后的组件必须生成向量记忆，不能用源码部分匹配代替。"""

    retrieval = _RetrievalStub(indexed=False)
    result = _service(retrieval=retrieval).search(
        user_id="u1",
        query="数据可视化",
        sources={"components"},
        fulltext=False,
        semantic=True,
    )

    assert retrieval.memory_service.deleted == [
        "unified:components:buttons/SaveButton.vue",
        "unified:components:cards/ChartCard.vue",
    ]
    assert len(retrieval.memory_service.created) == 2
    created = retrieval.memory_service.created[0]
    assert created.user_id == "u1::knowledge::lib-current"
    assert created.memory_type == "unified_search_chunk"
    assert created.embedding_vector_json == [1.0]
    assert result["results"][0]["matched_modes"] == ["semantic"]


class _KnowledgeFulltextStub:
    """提供一个文件树节点和真实磁盘正文命中。"""

    def list_files(self, *, user_id: str) -> list[dict[str, object]]:
        """返回文件库正式节点。"""

        return [
            {"name": "guide.md", "path": "docs/guide.md", "isDir": False, "size": 10},
            {"name": "guide.md", "path": ".mw/md/guide.md", "isDir": False, "size": 10},
        ]

    def search_file_contents(self, *, user_id: str, query: str) -> list[dict[str, str]]:
        """返回当前 active library 内的全文片段。"""

        assert query == "深度检索"
        return [{"source_uri": "D:/knowledge/current/docs/guide.md", "snippet": "这里介绍深度检索流程"}]


class _LibraryFulltextStub:
    """提供引用同一真实知识文件的图书卡片。"""

    def list_items(self, *, user_id: str, parent_id: str) -> dict[str, object]:
        """只在根目录返回一本图书。"""

        return {
            "items": [] if parent_id else [{
                "item_id": "book-1",
                "user_id": user_id,
                "parent_id": "",
                "item_type": "book",
                "content_type": "knowledge_file",
                "title": "检索手册",
                "display_title": "检索手册",
                "description": "",
                "source_path": "docs/guide.md",
                "source_name": "guide.md",
                "source_url": "",
                "tags": [],
                "updated_at": "",
            }],
        }


class _ComponentFulltextStub:
    """提供源码正文命中的组件。"""

    def list_components(self, *, user_id: str, tag: str = "any") -> dict[str, object]:
        """返回带查询短语的组件源码。"""

        return {
            "tags": ["cards", "any"],
            "components": [{
                "component_id": "cards/SearchCard.vue",
                "user_id": user_id,
                "title": "SearchCard",
                "tag": "cards",
                "source_format": "vue",
                "source": "<template><article>深度检索</article></template>",
                "builtin": False,
                "created_at": None,
                "updated_at": None,
            }],
        }


class _LiteratureFulltextStub:
    """提供摘要不含查询词、完整单元格含查询词的文献行。"""

    def list_literature_entries(self, *, user_id: str, library_id: str) -> list[dict[str, object]]:
        """返回文献侧栏卡片摘要。"""

        return [{
            "form_id": "form-1",
            "form_title": "研究文献",
            "row_id": "row-1",
            "title": "检索论文",
            "file_name": "paper.pdf",
            "asset_path": ".mw/forms/paper.pdf",
            "content_excerpt": "摘要没有关键词",
            "file_size": 10,
            "entered_at": "2026-08-29T00:00:00+00:00",
            "updated_at": "",
            "last_viewed_at": "",
            "tags": [],
            "rating": 0,
        }]

    def list_forms(self, **_: object) -> list[dict[str, str]]:
        """返回文献表摘要。"""

        return [{"form_id": "form-1", "title": "研究文献"}]

    def get_form(self, **_: object) -> dict[str, object]:
        """返回包含完整 literature_content 的正式行数据。"""

        return {"form": {"title": "研究文献", "rows": [{
            "id": "row-1",
            "cells": {"literature_content": {"value": "正文中的深度检索方法"}},
        }]}}


class _FulltextMemoryStub:
    """模拟无额外解析索引命中的长期记忆服务。"""

    def search_knowledge_content(self, **_: object) -> list[dict[str, object]]:
        """让磁盘正文成为本测试唯一文件全文来源。"""

        return []


class _FulltextRetrievalStub:
    """只为非语义测试提供全文索引依赖。"""

    def __init__(self) -> None:
        """建立最小检索配置。"""

        self.memory_service = _FulltextMemoryStub()
        self.config = SimpleNamespace(memory=SimpleNamespace(rerank_top_k=20))


def test_fulltext_searches_real_content_in_all_four_libraries_and_projects_book_file_hits() -> None:
    """全文开关应搜索四库真实正文，并把图书文件命中投影为图书卡片结果。"""

    service = UnifiedSearchService(
        settings_service=_SettingsStub(),
        knowledge_library_service=_KnowledgeFulltextStub(),
        library_service=_LibraryFulltextStub(),
        component_library_service=_ComponentFulltextStub(),
        smart_form_service=_LiteratureFulltextStub(),
        retrieval_service=_FulltextRetrievalStub(),
    )

    result = service.search(
        user_id="u1",
        query="深度检索",
        sources={"files", "library", "components", "literature"},
        fulltext=True,
        semantic=False,
    )

    assert result["counts"] == {"files": 1, "library": 1, "components": 1, "literature": 1}
    assert {item["source"] for item in result["results"]} == {"files", "library", "components", "literature"}
    assert all(item["matched_modes"] == ["fulltext"] for item in result["results"])
    assert all(not item["id"].startswith(".mw/") for item in result["results"])
