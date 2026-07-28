"""知识库图谱抽取服务测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.knowledge_graph import KnowledgeGraphDocumentStatus
from agent_service.services.knowledge_graph_service import (
    KnowledgeGraphService,
    _build_llm_config,
    _graph_progress_doc_entry,
)
from agent_service.services.memory.rag.frontmatter_document import (
    StructuredKnowledgeDocument,
    StructuredKnowledgeSection,
)


class FakeGraphExtractor:
    """返回固定实体关系候选,避免测试请求真实小模型。"""

    def extract(self, *, document: StructuredKnowledgeDocument, section: StructuredKnowledgeSection) -> dict[str, Any]:
        """返回同时包含有效和无效关系的候选。"""

        return {
            "entities": [
                {"name": "FrontmatterBootstrapService", "type": "class", "confidence": 0.9},
                {"name": "StructuredKnowledgeDocument", "type": "data", "confidence": 0.8},
                {"name": "系统", "type": "concept", "confidence": 0.8},
            ],
            "relations": [
                {
                    "source": "FrontmatterBootstrapService",
                    "target": "StructuredKnowledgeDocument",
                    "type": "produces",
                    "evidence": "FrontmatterBootstrapService 生成 StructuredKnowledgeDocument",
                    "confidence": 0.88,
                },
                {
                    "source": "StructuredKnowledgeDocument",
                    "target": "StructuredKnowledgeDocument",
                    "type": "related_to",
                    "evidence": "StructuredKnowledgeDocument",
                    "confidence": 0.9,
                },
                {
                    "source": "FrontmatterBootstrapService",
                    "target": "StructuredKnowledgeDocument",
                    "type": "invented",
                    "evidence": "FrontmatterBootstrapService 生成 StructuredKnowledgeDocument",
                    "confidence": 0.9,
                },
            ],
        }


class FailingGraphExtractor:
    """Simulate small-model extraction failure."""

    def extract(self, *, document: StructuredKnowledgeDocument, section: StructuredKnowledgeSection) -> dict[str, Any]:
        raise RuntimeError("small model unavailable")


class SameEntityDifferentTypeExtractor:
    """模拟不同文档把同名实体抽成不同类型。"""

    def extract(self, *, document: StructuredKnowledgeDocument, section: StructuredKnowledgeSection) -> dict[str, Any]:
        """返回同名但类型可能不同的实体候选。"""

        entity_type = "project" if document.document_id == "doc_a" else "concept"
        return {
            "entities": [
                {"name": "原神", "type": entity_type, "confidence": 0.9},
            ],
            "relations": [],
        }


class SimilarityTextExtractor:
    """模拟小模型只抽出实体,漏掉原文中明确写出的相似关系。"""

    def extract(self, *, document: StructuredKnowledgeDocument, section: StructuredKnowledgeSection) -> dict[str, Any]:
        """返回 A 和 B 两个实体,但不返回 A像B 的关系候选。"""

        return {
            "entities": [
                {"name": "A", "type": "concept", "confidence": 0.9},
                {"name": "B", "type": "concept", "confidence": 0.9},
            ],
            "relations": [],
        }


def test_graph_llm_config_inherits_large_model_when_small_model_empty(tmp_path: Path) -> None:
    """图谱抽取未配置小模型时应完整继承大模型配置。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "",
                "api_key": "",
                "base_url": "",
                "small_model_name": "",
                "small_model_api_key": "",
                "small_model_base_url": "",
            },
            "storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")},
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )

    llm_config = _build_llm_config(
        config,
        user_llm_config={
            "model_name": "deepseek-v4-flash",
            "api_key": "large-key",
            "base_url": "https://api.deepseek.com",
            "small_model_name": "",
            "small_api_key": "",
            "small_base_url": "",
        },
    )

    assert llm_config["model_name"] == "deepseek-v4-flash"
    assert llm_config["api_key"] == "large-key"
    assert llm_config["base_url"] == "https://api.deepseek.com"
    assert llm_config["small_model_name"] == "deepseek-v4-flash"
    assert llm_config["small_api_key"] == "large-key"
    assert llm_config["small_base_url"] == "https://api.deepseek.com"


def test_graph_llm_config_user_large_model_ignores_stale_config_small_key(tmp_path: Path) -> None:
    """用户未配置小模型时,图谱抽取不应混用环境或配置中残留的小模型 key。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "",
                "api_key": "",
                "base_url": "",
                "small_model_name": "stale-small-model",
                "small_model_api_key": "stale-small-key",
                "small_model_base_url": "https://stale-small.example.com",
            },
            "storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")},
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )

    llm_config = _build_llm_config(
        config,
        user_llm_config={
            "model_name": "deepseek-v4-flash",
            "api_key": "valid-large-key",
            "base_url": "https://api.deepseek.com",
            "small_model_name": "",
            "small_api_key": "stale-db-small-key",
            "small_base_url": "",
        },
    )

    assert llm_config["small_model_name"] == "deepseek-v4-flash"
    assert llm_config["small_api_key"] == "valid-large-key"
    assert llm_config["small_base_url"] == "https://api.deepseek.com"


def test_graph_llm_config_uses_explicit_small_model_when_present(tmp_path: Path) -> None:
    """图谱抽取配置了小模型时应优先使用小模型配置。"""

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "",
                "api_key": "",
                "base_url": "",
                "small_model_name": "",
                "small_model_api_key": "",
                "small_model_base_url": "",
            },
            "storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")},
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )

    llm_config = _build_llm_config(
        config,
        user_llm_config={
            "model_name": "large-model",
            "api_key": "large-key",
            "base_url": "https://large.example.com",
            "small_model_name": "small-model",
            "small_api_key": "small-key",
            "small_base_url": "https://small.example.com",
        },
    )

    assert llm_config["small_model_name"] == "small-model"
    assert llm_config["small_api_key"] == "small-key"
    assert llm_config["small_base_url"] == "https://small.example.com"


def test_entity_dedup_merges_semantic_duplicates(tmp_path: Path) -> None:
    """语义去重应合并不同名称但指代同一事物的实体。"""

    from unittest.mock import MagicMock

    from agent_service.services.knowledge_graph_service import (
        EntityCandidate,
        LLMKnowledgeGraphExtractor,
    )

    mock_response = MagicMock()
    mock_response.content = (
        '{"groups": [{"canonical_name": "AI", "canonical_type": "concept", '
        '"entity_indices": [0, 1], "aliases": ["AI", "Artificial Intelligence"]}]}'
    )
    mock_scheduler = MagicMock()
    mock_scheduler.invoke_chat.return_value = mock_response

    config = AgentConfig.load_config(
        {
            "model": {
                "model_name": "mock-model",
                "api_key": "mock-key",
            },
            "storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")},
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    extractor = LLMKnowledgeGraphExtractor(config=config, task_scheduler=mock_scheduler)
    entities = [
        EntityCandidate(name="AI", entity_type="concept", aliases=[], description="人工智能", confidence=0.9),
        EntityCandidate(name="Artificial Intelligence", entity_type="concept", aliases=[], description="人工智慧", confidence=0.85),
    ]
    document = StructuredKnowledgeDocument(
        document_id="doc_dedup",
        source_type="text",
        source_path=str(tmp_path / "dedup.txt"),
        source_uri=str(tmp_path / "dedup.txt"),
        source_hash="h1",
        title="dedup_test",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={},
        sections=[],
    )

    result = extractor.deduplicate_entities(entities, document=document)
    merged = result["entities"]
    name_mapping = result.get("name_mapping", {})

    assert len(merged) == 1
    assert merged[0].name == "AI"
    assert name_mapping.get("Artificial Intelligence") == "AI"


def test_entity_dedup_passthrough_on_single_entity(tmp_path: Path) -> None:
    """只有一个实体时应直接透传,不触发 LLM 调用。"""

    from unittest.mock import MagicMock

    from agent_service.services.knowledge_graph_service import (
        EntityCandidate,
        LLMKnowledgeGraphExtractor,
    )

    mock_scheduler = MagicMock()
    config = AgentConfig.load_config(
        {
            "model": {"model_name": "mock-model", "api_key": "mock-key"},
            "storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")},
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    extractor = LLMKnowledgeGraphExtractor(config=config, task_scheduler=mock_scheduler)
    entities = [
        EntityCandidate(name="唯一实体", entity_type="concept", aliases=[], description="", confidence=0.9),
    ]
    document = StructuredKnowledgeDocument(
        document_id="doc_single", source_type="text", source_path=str(tmp_path / "s.txt"),
        source_uri=str(tmp_path / "s.txt"), source_hash="h1", title="single",
        summary="", tags=[], authority=0.7, valid_from=None, valid_until=None, metadata={}, sections=[],
    )

    result = extractor.deduplicate_entities(entities, document=document)
    assert len(result["entities"]) == 1
    mock_scheduler.invoke_chat.assert_not_called()


def test_graph_progress_doc_entry_uses_source_relative_path(tmp_path: Path) -> None:
    """图谱抽取进度应返回文件树相对路径,以便前端逐个更新图谱状态图标。"""

    document = StructuredKnowledgeDocument(
        document_id="doc_nested_demo",
        source_type="markdown",
        source_path=str(tmp_path / "knowledge" / "notes" / "demo.md"),
        source_uri=str(tmp_path / "knowledge" / "notes" / "demo.md"),
        source_hash="hash-1",
        title="demo",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={"relative_path": "notes/demo.md"},
        sections=[],
    )

    entry = _graph_progress_doc_entry(
        document=document,
        frontmatter_path=tmp_path / "runtime" / "frontmatter" / "notes" / "demo.json",
        frontmatter_dir=tmp_path / "runtime" / "frontmatter",
        status="pending",
        progress=0,
        total_sections=0,
    )

    assert entry["path"] == "notes/demo.md"
    assert entry["name"] == "demo"


def test_knowledge_graph_service_extracts_validated_edges(tmp_path: Path) -> None:
    """验证服务只写入通过证据和白名单校验的点边。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "project_root": str(tmp_path),
                "base_data_dir": str(tmp_path / "runtime"),
                "knowledge_dir": str(tmp_path / "knowledge"),
            }
        },
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    service = KnowledgeGraphService(
        config=config,
        engine=engine,
        extractor=FakeGraphExtractor(),
    )
    document = StructuredKnowledgeDocument(
        document_id="doc_demo",
        source_type="markdown",
        source_path=str(tmp_path / "demo.md"),
        source_uri=str(tmp_path / "demo.md"),
        source_hash="hash-1",
        title="demo",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={"relative_path": "demo.md"},
        sections=[
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading="demo",
                title_path=["demo"],
                content="FrontmatterBootstrapService 生成 StructuredKnowledgeDocument,再进入向量入库。",
                start_char=0,
                end_char=72,
            )
        ],
    )

    result = service.extract_document(user_id="u1", library_id="lib1", document=document)
    graph = service.get_graph(user_id="u1", library_id="lib1")

    assert result.files_extracted == 1
    assert result.entities_written == 2
    assert result.relations_written == 2
    assert graph["stats"]["documents"] == 1
    assert graph["stats"]["entities"] == 2
    semantic_edges = [edge for edge in graph["links"] if edge["kind"] in ("produces", "invented")]
    assert len(semantic_edges) == 2


def test_knowledge_graph_service_skips_unchanged_document(tmp_path: Path) -> None:
    """验证相同 source_hash 的文档不会重复触发抽取。"""

    config = AgentConfig.load_config(
        {"storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")}},
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    service = KnowledgeGraphService(config=config, engine=engine, extractor=FakeGraphExtractor())
    document = StructuredKnowledgeDocument(
        document_id="doc_same_hash",
        source_type="text",
        source_path=str(tmp_path / "same.txt"),
        source_uri=str(tmp_path / "same.txt"),
        source_hash="same-hash",
        title="same",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={"relative_path": "same.txt"},
        sections=[
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading="same",
                title_path=["same"],
                content="FrontmatterBootstrapService 生成 StructuredKnowledgeDocument。",
                start_char=0,
                end_char=60,
            )
        ],
    )

    first = service.extract_document(user_id="u1", library_id="lib1", document=document)
    second = service.extract_document(user_id="u1", library_id="lib1", document=document)

    assert first.files_extracted == 1
    assert second.files_skipped == 1


def test_knowledge_graph_service_keeps_document_node_when_extraction_fails(tmp_path: Path) -> None:
    """小模型失败时仍应写入文档节点,避免图谱看起来没有灌库。"""

    config = AgentConfig.load_config(
        {"storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")}},
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    service = KnowledgeGraphService(config=config, engine=engine, extractor=FailingGraphExtractor())
    document = StructuredKnowledgeDocument(
        document_id="doc_failed",
        source_type="text",
        source_path=str(tmp_path / "failed.txt"),
        source_uri=str(tmp_path / "failed.txt"),
        source_hash="failed-hash",
        title="failed",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={"relative_path": "failed.txt"},
        sections=[
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading="failed",
                title_path=["failed"],
                content="This document should still appear in the graph.",
                start_char=0,
                end_char=47,
            )
        ],
    )

    result = service.extract_document(user_id="u1", library_id="lib1", document=document)
    graph = service.get_graph(user_id="u1", library_id="lib1")

    assert result.files_failed == 1
    assert graph["stats"]["documents"] == 1
    assert graph["stats"]["entities"] == 0
    assert graph["nodes"][0]["label"] == "failed"
    with Session(engine) as db:
        status = db.exec(select(KnowledgeGraphDocumentStatus)).one()
    assert status.status == "failed"
    assert status.message == "small model unavailable"


def test_knowledge_graph_service_coalesces_same_named_entities_across_documents(tmp_path: Path) -> None:
    """同名实体即使被抽成不同类型,语义图谱中也应归并为同一个实体节点。"""

    config = AgentConfig.load_config(
        {"storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")}},
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    service = KnowledgeGraphService(config=config, engine=engine, extractor=SameEntityDifferentTypeExtractor())
    documents = [
        StructuredKnowledgeDocument(
            document_id="doc_a",
            source_type="markdown",
            source_path=str(tmp_path / "a.md"),
            source_uri=str(tmp_path / "a.md"),
            source_hash="hash-a",
            title="文档 A",
            summary="",
            tags=[],
            authority=0.7,
            valid_from=None,
            valid_until=None,
            metadata={"relative_path": "a.md"},
            sections=[
                StructuredKnowledgeSection(
                    section_id="sec_0000",
                    heading="a",
                    title_path=["a"],
                    content="原神 是一个项目。",
                    start_char=0,
                    end_char=9,
                )
            ],
        ),
        StructuredKnowledgeDocument(
            document_id="doc_b",
            source_type="markdown",
            source_path=str(tmp_path / "b.md"),
            source_uri=str(tmp_path / "b.md"),
            source_hash="hash-b",
            title="文档 B",
            summary="",
            tags=[],
            authority=0.7,
            valid_from=None,
            valid_until=None,
            metadata={"relative_path": "b.md"},
            sections=[
                StructuredKnowledgeSection(
                    section_id="sec_0000",
                    heading="b",
                    title_path=["b"],
                    content="原神 是一个概念。",
                    start_char=0,
                    end_char=9,
                )
            ],
        ),
    ]

    for document in documents:
        service.extract_document(user_id="u1", library_id="lib1", document=document)
    graph = service.get_graph(user_id="u1", library_id="lib1")

    genshin_nodes = [
        node
        for node in graph["nodes"]
        if node["kind"] == "entity" and node["label"] == "原神"
    ]
    assert len(genshin_nodes) == 1
    mention_edges = [
        edge
        for edge in graph["links"]
        if edge["kind"] == "mentions" and edge["target"] == genshin_nodes[0]["id"]
    ]
    assert graph["stats"]["entities"] == 1
    assert len(mention_edges) == 2


def test_knowledge_graph_service_infers_explicit_similarity_relation(tmp_path: Path) -> None:
    """小模型漏掉 A像B 关系时,服务应从原文补出 A 到 B 的语义边。"""

    config = AgentConfig.load_config(
        {"storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")}},
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    service = KnowledgeGraphService(config=config, engine=engine, extractor=SimilarityTextExtractor())
    document = StructuredKnowledgeDocument(
        document_id="doc_similarity",
        source_type="text",
        source_path=str(tmp_path / "similarity.txt"),
        source_uri=str(tmp_path / "similarity.txt"),
        source_hash="hash-similarity",
        title="similarity",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={"relative_path": "similarity.txt"},
        sections=[
            StructuredKnowledgeSection(
                section_id="sec_0000",
                heading="similarity",
                title_path=["similarity"],
                content="A像B。",
                start_char=0,
                end_char=4,
            )
        ],
    )

    result = service.extract_document(user_id="u1", library_id="lib1", document=document)
    graph = service.get_graph(user_id="u1", library_id="lib1")
    semantic_edges = [edge for edge in graph["links"] if edge["kind"] == "related_to"]

    assert result.entities_written == 2
    assert result.relations_written == 1
    assert len(semantic_edges) == 1
    assert semantic_edges[0]["evidence"] == "A像B"


def test_cosine_similarity_identical_vectors() -> None:
    """相同向量的余弦相似度应为 1.0。"""

    from agent_service.services.knowledge_graph_service import KnowledgeGraphService

    a = [1.0, 0.0, 0.0]
    assert KnowledgeGraphService._cosine_similarity(a, a) == 1.0


def test_cosine_similarity_orthogonal_vectors() -> None:
    """正交向量的余弦相似度应为 0.0。"""

    from agent_service.services.knowledge_graph_service import KnowledgeGraphService

    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert KnowledgeGraphService._cosine_similarity(a, b) == 0.0


def test_incremental_dedup_passthrough_on_empty_db(tmp_path: Path) -> None:
    """库中没有实体时增量去重应返回空映射。"""

    from unittest.mock import MagicMock

    from sqlalchemy.pool import StaticPool

    from agent_service.core.agent_config import AgentConfig
    from agent_service.services.knowledge_graph_service import (
        EntityCandidate,
        KnowledgeGraphService,
        LLMKnowledgeGraphExtractor,
    )
    from agent_service.services.memory.rag.frontmatter_document import (
        StructuredKnowledgeDocument,
    )

    config = AgentConfig.load_config(
        {"storage": {"project_root": str(tmp_path), "base_data_dir": str(tmp_path / "runtime")}},
        load_env=False,
        load_dotenv=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    mock_scheduler = MagicMock()
    extractor = LLMKnowledgeGraphExtractor(config=config, task_scheduler=mock_scheduler)
    service = KnowledgeGraphService(config=config, engine=engine, extractor=None, create_tables=True)
    document = StructuredKnowledgeDocument(
        document_id="doc_inc",
        source_type="text",
        source_path=str(tmp_path / "inc.txt"),
        source_uri=str(tmp_path / "inc.txt"),
        source_hash="h1",
        title="inc_test",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={},
        sections=[],
    )

    # 库中无实体,应返回空
    mapping = service._deduplicate_entities_incremental(
        user_id="u1",
        library_id="lib1",
        new_entities=[EntityCandidate(name="AI", entity_type="concept", aliases=[], description="", confidence=0.9)],
        extractor=extractor,
        document=document,
    )
    assert mapping == {}
