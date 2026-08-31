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

import threading
import time
from types import SimpleNamespace
from typing import Sequence

from sqlmodel import SQLModel, create_engine

from agent_service.core.agent_config import AgentConfig
from agent_service.core.model_status import ModelState, get_model_status, set_model_state
from agent_service.schemas.longterm_memory_spec import LongTermMemorySpecCreate
from agent_service.services.memory.longterm_memory_service import LongTermMemoryService
from agent_service.services.memory.rag.embedding import EmbeddingService, SentenceTransformerEmbeddingProvider
from agent_service.services.memory.rag.hybrid_retrieval import HybridRetrievalService
from agent_service.services.memory.rag.rerank import (
    RerankProvider,
    RerankService,
    SentenceTransformerCrossEncoderProvider,
)
from agent_service.services.memory.rag import sentence_transformer_imports
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


class FakeSentenceTransformerModel:
    """Minimal model stub used to verify provider loading behavior."""

    def encode(
        self,
        texts: list[str],
        *,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> list[list[float]]:
        _ = normalize_embeddings, show_progress_bar
        return [[float(len(text))] for text in texts]


def test_sentence_transformer_embedding_provider_waits_for_warmup_load() -> None:
    """Embedding generation should wait for the background warmup load to finish."""

    config = make_rag_test_config()
    provider = SentenceTransformerEmbeddingProvider(config=config)
    load_started = threading.Event()
    allow_load_finish = threading.Event()

    def fake_load_model_in_thread() -> None:
        load_started.set()
        allow_load_finish.wait(timeout=5)
        provider._model = FakeSentenceTransformerModel()

    provider._load_model_in_thread = fake_load_model_in_thread  # type: ignore[method-assign]
    provider.warmup()
    assert load_started.wait(timeout=1)

    vectors: list[list[float]] = []
    embed_thread = threading.Thread(target=lambda: vectors.extend(provider.embed_texts(["hello"])))
    embed_thread.start()
    time.sleep(0.05)
    assert embed_thread.is_alive()

    allow_load_finish.set()
    embed_thread.join(timeout=1)

    assert not embed_thread.is_alive()
    assert vectors == [[5.0]]


def test_embedding_provider_restarts_a_stale_loader_thread() -> None:
    """无结果退出的旧加载线程不得让后续 Embedding 预热永久失效。"""

    provider = SentenceTransformerEmbeddingProvider(config=make_rag_test_config())
    stale = threading.Thread(target=lambda: None)
    stale.start()
    stale.join(timeout=1)
    provider._load_thread = stale
    restarted = threading.Event()
    provider._load_model_in_thread = restarted.set  # type: ignore[method-assign]

    provider.warmup()

    assert restarted.wait(timeout=1)


def test_rerank_provider_restarts_a_stale_loader_thread() -> None:
    """无结果退出的旧加载线程不得让后续 ReRank 预热永久失效。"""

    provider = SentenceTransformerCrossEncoderProvider(config=make_rag_test_config())
    stale = threading.Thread(target=lambda: None)
    stale.start()
    stale.join(timeout=1)
    provider._load_thread = stale
    restarted = threading.Event()
    provider._load_model_in_thread = restarted.set  # type: ignore[method-assign]

    provider.warmup()

    assert restarted.wait(timeout=1)


def test_cached_embedding_and_rerank_publish_ready_again() -> None:
    """缓存命中必须纠正后来被覆盖的 loading 状态。"""

    config = make_rag_test_config()
    embedding = SentenceTransformerEmbeddingProvider(config=config)
    rerank = SentenceTransformerCrossEncoderProvider(config=config)
    embedding._model = object()
    rerank._model = object()
    set_model_state("embedding", ModelState.LOADING)
    set_model_state("rerank", ModelState.LOADING)

    embedding.warmup()
    rerank.warmup()
    states = get_model_status().to_dict()

    assert states["embedding"] == "ready"
    assert states["rerank"] == "ready"


def test_shared_embedding_and_rerank_factories_create_singletons(monkeypatch) -> None:
    """共享 provider 工厂必须能创建并稳定复用实例，供模型管理与业务入口调用。"""

    import agent_service.services.memory.rag.embedding as embedding_module
    import agent_service.services.memory.rag.rerank as rerank_module

    monkeypatch.setattr(embedding_module, "_provider", None)
    monkeypatch.setattr(rerank_module, "_rerank_provider", None)
    config = make_rag_test_config()

    embedding = embedding_module._get_shared_provider(config)
    rerank = rerank_module._get_shared_rerank_provider(config)

    assert embedding_module._get_shared_provider(config) is embedding
    assert rerank_module._get_shared_rerank_provider(config) is rerank


def test_sentence_transformer_first_imports_are_serialized(monkeypatch) -> None:
    """Embedding根包与 ReRank子模块不得同时进入 Python首次导入。"""

    active = 0
    max_active = 0
    first_entered = threading.Event()
    release_first = threading.Event()

    def fake_import(module_name: str) -> SimpleNamespace:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        first_entered.set()
        release_first.wait(timeout=2)
        active -= 1
        return SimpleNamespace(SentenceTransformer=object, CrossEncoder=object)

    monkeypatch.setattr(sentence_transformer_imports.importlib, "import_module", fake_import)
    embedding_thread = threading.Thread(target=sentence_transformer_imports.load_sentence_transformer_type)
    rerank_thread = threading.Thread(target=sentence_transformer_imports.load_cross_encoder_type)
    embedding_thread.start()
    assert first_entered.wait(timeout=1)
    rerank_thread.start()
    time.sleep(0.05)
    assert max_active == 1
    release_first.set()
    embedding_thread.join(timeout=1)
    rerank_thread.join(timeout=1)
    assert not embedding_thread.is_alive()
    assert not rerank_thread.is_alive()


def test_sentence_transformer_import_failure_exits_loading_state(monkeypatch) -> None:
    """模块锁异常必须落到 error，不能让管理页永久显示 loading。"""

    import agent_service.services.memory.rag.embedding as embedding_module
    import agent_service.services.memory.rag.rerank as rerank_module

    failure = RuntimeError("simulated module lock deadlock")
    monkeypatch.setattr(embedding_module, "load_sentence_transformer_type", lambda: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(rerank_module, "load_cross_encoder_type", lambda: (_ for _ in ()).throw(failure))
    embedding = SentenceTransformerEmbeddingProvider(config=make_rag_test_config())
    rerank = SentenceTransformerCrossEncoderProvider(config=make_rag_test_config())

    embedding._load_model_in_thread()
    rerank._load_model_in_thread()

    states = get_model_status().to_dict()
    assert states["embedding"] == "error"
    assert states["rerank"] == "error"
    assert embedding._load_error is failure
    assert rerank._load_error is failure


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


def test_search_knowledge_content_uses_default_limit_when_omitted() -> None:
    """联合搜索未显式传 limit 时也必须返回全文命中，不能比较 ``int`` 与 ``None``。"""

    config = make_rag_test_config()
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    memory_service = LongTermMemoryService(config=config, engine=engine, create_tables=False)
    memory_service.create_memory(
        LongTermMemorySpecCreate(
            user_id="user_1:library_1",
            session_id=None,
            tag="Knowledge",
            memory_type="knowledge_chunk",
            content="CSV 文件包含实验数据。",
            source_type="knowledge_file",
            source_id="csv.csv",
            source_uri="D:/Knowledge/csv.csv",
            embedding_model="fake",
            embedding_vector_json=[1.0, 2.0, 3.0],
        )
    )

    results = memory_service.search_knowledge_content(query="CSV", user_id="user_1")

    assert results == [{"source_uri": "D:/Knowledge/csv.csv", "snippet": "CSV 文件包含实验数据。"}]


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
