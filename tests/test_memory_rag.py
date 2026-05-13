"""
RAG 检索链路测试脚本。

功能说明:
本文件用于验证 README 要求的混合检索与 ReRank 主链路已经接入生产代码,重点覆盖:
1. 关键词召回是否能从统一长期记忆表中命中相关内容。
2. `MemoryRetrievalService` 是否已经真正走过 `hybrid retrieval -> rerank -> final rank`
   这条完整工作流。

使用说明:
在项目根目录执行 `python -m pytest tests/test_memory_rag.py`。
"""

from __future__ import annotations

from typing import Sequence

from sqlmodel import SQLModel, create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService
from agent_service.services.memory.rag.hybrid_retrieval import HybridRetrievalService
from agent_service.services.memory.rag.rerank import RerankProvider, RerankService
from agent_service.services.memory.retrieval_service import MemoryRetrievalService


class FakeEmbeddingProvider:
    """
    测试用假 Embedding 提供者。

    dimension: 输出向量维度。
    """

    def __init__(self, *, dimension: int = 3) -> None:
        """保存输出维度。"""

        self.dimension = dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """根据文本长度生成稳定假向量。"""

        return [[float(len(text) + index) for index in range(self.dimension)] for text in texts]


class FakeRerankProvider(RerankProvider):
    """
    测试用假 ReRank 提供者。

    本实现故意偏好包含“负责模块”的候选,用于验证 ReRank 已接入主链路。
    """

    def score_pairs(self, *, query: str, documents: Sequence[str]) -> list[float]:
        """按候选内容返回稳定测试分数。"""

        _ = query
        scores: list[float] = []
        for document in documents:
            if "负责模块" in document:
                scores.append(0.95)
                continue
            if "项目代号" in document:
                scores.append(0.35)
                continue
            scores.append(0.1)
        return scores


class LowConfidenceRerankProvider(RerankProvider):
    """
    测试用低分 ReRank 提供者。

    用于验证 ReRank 不会把已经明确命中的 active fact 硬降到阈值以下。
    """

    def score_pairs(self, *, query: str, documents: Sequence[str]) -> list[float]:
        """无论候选内容如何都返回偏低分数。"""

        _ = query
        return [0.2 for _ in documents]


def make_rag_test_config() -> AgentConfig:
    """创建 RAG 测试专用配置。"""

    return AgentConfig.load_config(
        {
            "memory": {
                "vector_top_k": 5,
                "keyword_top_k": 5,
                "rerank_top_k": 3,
                "score_threshold": 0.0,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )


def test_hybrid_retrieval_service_returns_keyword_candidates() -> None:
    """验证关键词召回可以从统一长期记忆表中命中相关摘要。"""

    config = make_rag_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_hybrid",
            tag="Memory",
            memory_type="session_summary",
            content="项目代号是 stone-cat,负责模块是 SummaryNode。",
            source_type="session_messages",
            source_id="sess_hybrid",
            embedding_model="fake",
            embedding_vector_json=[1.0, 2.0, 3.0],
        )
    )
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_hybrid",
            tag="Memory",
            memory_type="session_summary",
            content="用户偏好简洁回答。",
            source_type="session_messages",
            source_id="sess_hybrid",
            embedding_model="fake",
            embedding_vector_json=[1.0, 2.0, 3.0],
        )
    )
    hybrid_service = HybridRetrievalService(config=config, engine=engine)

    candidates = hybrid_service.retrieve_keyword_candidates(
        query="项目代号和负责模块是什么",
        user_id="user_1",
        session_id="sess_hybrid",
        tag="Memory",
        memory_type="session_summary",
        limit=3,
    )

    assert candidates
    assert candidates[0].memory.content.startswith("项目代号是 stone-cat")
    assert "项目代号" in candidates[0].matched_terms or "负责模块" in candidates[0].matched_terms


def test_memory_retrieval_service_uses_hybrid_and_rerank_workflow() -> None:
    """验证统一检索服务已经接入混合检索和 ReRank 工作流。"""

    config = make_rag_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_rerank",
            tag="Memory",
            memory_type="session_summary",
            content="项目代号是 stone-cat。",
            source_type="session_messages",
            source_id="sess_rerank",
            authority=0.6,
            embedding_model="fake",
            embedding_vector_json=[10.0, 11.0, 12.0],
        )
    )
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_rerank",
            tag="Memory",
            memory_type="session_summary",
            content="当前负责模块是 SummaryNode。",
            source_type="session_messages",
            source_id="sess_rerank",
            authority=0.6,
            embedding_model="fake",
            embedding_vector_json=[10.0, 11.0, 12.0],
        )
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
        memory_service=memory_service,
        rerank_service=RerankService(config=config, provider=FakeRerankProvider()),
    )

    memories = retrieval_service.retrieve_long_term_memory(
        query="负责模块是什么",
        user_id="user_1",
        session_id="sess_rerank",
        top_k=2,
    )

    assert len(memories) == 2
    assert any(item.memory.content.startswith("当前负责模块是 SummaryNode") for item in memories)
    target = next(item for item in memories if item.memory.content.startswith("当前负责模块是 SummaryNode"))
    assert target.rerank_score == 0.95
    assert "keyword" in target.retrieval_channels


def test_memory_retrieval_service_keeps_active_fact_when_rerank_is_lower_than_merged_score() -> None:
    """验证 ReRank 低分不会把 active fact 错误过滤掉。"""

    config = AgentConfig.load_config(
        {
            "memory": {
                "vector_top_k": 5,
                "keyword_top_k": 5,
                "rerank_top_k": 3,
                "score_threshold": 0.7,
            }
        },
        load_env=False,
        ensure_directories=False,
        ensure_models=False,
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1",
            session_id="sess_current",
            tag="Memory",
            memory_type="session_fact",
            content="当前项目代号为3333333。",
            source_type="session_summary",
            source_id="summary_1",
            authority=0.6,
            metadata_json={
                "fact": {
                    "namespace": "project",
                    "key": "project_code",
                    "value": "3333333",
                    "category": "single_value",
                    "status": "active",
                    "value_type": "string",
                    "valid_from": "2026-05-13T00:00:00+00:00",
                    "valid_until": None,
                },
                "fact_status": "active",
            },
            embedding_model="fake",
            embedding_vector_json=[10.0, 11.0, 12.0],
        )
    )
    retrieval_service = MemoryRetrievalService(
        config=config,
        embedding_service=EmbeddingService(config=config, provider=FakeEmbeddingProvider(dimension=3)),
        memory_service=memory_service,
        rerank_service=RerankService(config=config, provider=LowConfidenceRerankProvider()),
    )

    memories = retrieval_service.retrieve_long_term_memory(
        query="当前项目代号是什么? 1111111 和 2222222 现在还算当前值吗?",
        user_id="user_1",
        session_id="sess_final",
        top_k=3,
    )

    assert len(memories) == 1
    assert memories[0].memory.content == "当前项目代号为3333333。"
    assert memories[0].rerank_score == 0.2
    assert memories[0].relevance_score >= memories[0].rerank_score
