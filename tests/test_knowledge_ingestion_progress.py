"""不同管线汇入统一切片与向量阶段后的详细进度测试。"""

from __future__ import annotations

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.rag.frontmatter_document import (
    StructuredKnowledgeDocument,
    StructuredKnowledgeSection,
)
from agent_service.services.memory.rag.knowledge_ingestion import KnowledgeIngestionService


class FakeEmbeddingService:
    """记录每批真实切片数。"""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[float(index)] for index, _ in enumerate(texts)]


class FakeMemoryService:
    """记录向量写入数量。"""

    def __init__(self) -> None:
        self.created: list[object] = []

    def create_memory(self, payload: object) -> None:
        self.created.append(payload)


def test_vector_progress_reports_real_batches_and_chunk_counts() -> None:
    """超过 16 个切片时应按真实批次数持续更新阶段、单位和总进度。"""

    config = AgentConfig.load_config(load_env=False, ensure_directories=False, ensure_models=False)
    embedding = FakeEmbeddingService()
    memory = FakeMemoryService()
    service = KnowledgeIngestionService(
        config=config,
        embedding_service=embedding,  # type: ignore[arg-type]
        memory_service=memory,  # type: ignore[arg-type]
    )
    sections = [
        StructuredKnowledgeSection(
            section_id=f"sec_{index:04d}",
            heading=f"章节 {index}",
            title_path=["批处理文档", f"章节 {index}"],
            content=f"第 {index} 个足够独立的知识切片。",
            start_char=index * 20,
            end_char=(index + 1) * 20,
        )
        for index in range(17)
    ]
    document = StructuredKnowledgeDocument(
        document_id="doc_batches",
        source_type="pdf",
        source_path="papers/batches.pdf",
        source_uri="papers/batches.pdf",
        source_hash="source-hash",
        title="批处理文档",
        summary="",
        tags=[],
        authority=0.7,
        valid_from=None,
        valid_until=None,
        metadata={"relative_path": "papers/batches.pdf"},
        sections=sections,
    )
    events: list[dict[str, object]] = []

    created = service._ingest_document(document=document, user_id="u1", progress_callback=events.append)

    assert created == 17
    assert embedding.batch_sizes == [16, 1]
    assert len(memory.created) == 17
    assert events[0] == {
        "phase": "ingestion",
        "status": "processing",
        "path": "papers/batches.pdf",
        "name": "batches.pdf",
        "stage": "split",
        "stage_label": "切片完成，共 17 个切片",
        "stage_current": 17,
        "stage_total": 17,
        "overall_progress": 54,
        "message": "",
    }
    assert [(event["stage_current"], event["stage_total"]) for event in events[1:]] == [(1, 2), (2, 2)]
    assert events[-1]["overall_progress"] == 96
    assert events[-1]["message"] == "已写入 17 / 17 个切片"
