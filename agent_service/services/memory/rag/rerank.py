"""
ReRank 服务。

功能说明:
本文件实现 README 要求的“召回后精排”能力。它接收混合检索候选集,优先使用本地
CrossEncoder ReRank 模型对 `query + document` 对做相关性打分;若未配置模型或
测试环境显式注入假 provider,则回退到现有混合召回分数。

使用说明:
service = RerankService(config=config)
reranked = service.rerank(query="项目代号是什么", candidates=candidates, top_k=3)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.download_model import ensure_model, model_target_dir
from agent_service.services.memory.rag.hybrid_retrieval import HybridRetrievalCandidate


class RerankProvider(Protocol):
    """
    ReRank 提供者协议。

    score_pairs: 接收 query 与候选文本列表,返回同顺序的相关性分数列表。
    """

    def score_pairs(self, *, query: str, documents: Sequence[str]) -> list[float]:
        """对 query-document 对打分。"""


class SentenceTransformerCrossEncoderProvider:
    """
    基于 sentence-transformers CrossEncoder 的本地 ReRank 提供者。

    config: 全局配置对象,用于读取本地 ReRank 模型目录与模型名。
    """

    def __init__(self, *, config: AgentConfig) -> None:
        """保存配置并延迟加载模型。"""

        self.config = config
        self._model: object | None = None

    def score_pairs(self, *, query: str, documents: Sequence[str]) -> list[float]:
        """
        对 query-document 对打分。

        query: 当前用户问题。
        documents: 待精排的候选文本列表。
        """

        if not documents:
            return []
        model = self._get_model()
        pairs = [[query, document] for document in documents]
        raw_scores = model.predict(pairs)
        return [self._normalize_score(float(score)) for score in raw_scores]

    def _get_model(self) -> object:
        """延迟加载本地 CrossEncoder 模型。"""

        if self._model is not None:
            return self._model
        try:
            from sentence_transformers.cross_encoder import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "缺少 sentence-transformers 依赖,无法加载本地 ReRank 模型。"
            ) from exc

        if not self.config.model.rerank_model_name:
            raise ValueError("config.model.rerank_model_name 不能为空。")
        model_path = ensure_model(
            self.config.model.rerank_model_name,
            self.config.storage.rerank_model_dir,
        )
        if model_path is None:
            model_path = model_target_dir(
                self.config.model.rerank_model_name,
                self.config.storage.rerank_model_dir,
            )
        if not model_path.exists():
            raise FileNotFoundError(f"ReRank 模型目录不存在: {model_path}")
        self._model = CrossEncoder(str(model_path))
        return self._model

    @staticmethod
    def _normalize_score(value: float) -> float:
        """
        将 CrossEncoder 输出规范到 0 到 1。

        value: 模型原始分数。
        """

        if value < 0.0:
            return 1.0 / (1.0 + pow(2.718281828459045, -value))
        if value > 1.0:
            return value / (1.0 + value)
        return value


class RerankService:
    """
    ReRank 服务门面。

    config: 全局配置对象。
    provider: 可选自定义 ReRank provider,测试时可注入假实现。
    """

    def __init__(self, *, config: AgentConfig, provider: RerankProvider | None = None) -> None:
        """初始化 ReRank 服务。"""

        self.config = config
        self.provider = provider

    def is_enabled(self) -> bool:
        """
        判断当前是否启用了真实 ReRank 模型。

        如果显式注入 provider,测试和生产都会视为启用。
        """

        return self.provider is not None or bool(self.config.model.rerank_model_name)

    def rerank(
        self,
        *,
        query: str,
        candidates: Sequence[HybridRetrievalCandidate],
        top_k: int,
    ) -> list[HybridRetrievalCandidate]:
        """
        对混合检索候选做精排。

        query: 当前用户问题。
        candidates: 混合召回候选集。
        top_k: 精排后保留的数量。
        """

        if not candidates:
            return []
        if top_k <= 0:
            return []
        if not self.is_enabled():
            ranked = list(candidates)
            ranked.sort(key=self._fallback_rank_key, reverse=True)
            return ranked[:top_k]
        provider = self.provider or SentenceTransformerCrossEncoderProvider(config=self.config)
        documents = [candidate.memory.content for candidate in candidates]
        scores = provider.score_pairs(query=query, documents=documents)
        reranked: list[HybridRetrievalCandidate] = []
        for candidate, score in zip(candidates, scores, strict=False):
            candidate.rerank_score = self._clamp_score(score)
            reranked.append(candidate)
        reranked.sort(key=self._rerank_key, reverse=True)
        return reranked[:top_k]

    @staticmethod
    def _fallback_rank_key(candidate: HybridRetrievalCandidate) -> tuple[float, int, float]:
        """
        未启用真实 ReRank 模型时的回退排序键。

        candidate: 混合检索候选。
        """

        return candidate.merged_score, len(candidate.source_channels), candidate.memory.importance

    @staticmethod
    def _rerank_key(candidate: HybridRetrievalCandidate) -> tuple[float, float, int, float]:
        """
        启用真实 ReRank 模型后的排序键。

        candidate: 混合检索候选。
        """

        rerank_score = candidate.rerank_score or 0.0
        return rerank_score, candidate.merged_score, len(candidate.source_channels), candidate.memory.importance

    @staticmethod
    def _clamp_score(value: float) -> float:
        """
        将分数裁剪到 0 到 1。

        value: 原始分数。
        """

        return max(0.0, min(1.0, value))
