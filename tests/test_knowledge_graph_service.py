"""知识库图谱抽取服务测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.knowledge_graph import KnowledgeGraphDocumentStatus
from agent_service.services.knowledge_graph_service import KnowledgeGraphService
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
    assert result.relations_written == 1
    assert graph["stats"]["documents"] == 1
    assert graph["stats"]["entities"] == 2
    semantic_edges = [edge for edge in graph["links"] if edge["kind"] == "produces"]
    assert len(semantic_edges) == 1
    assert semantic_edges[0]["evidence"] == "FrontmatterBootstrapService 生成 StructuredKnowledgeDocument"


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
