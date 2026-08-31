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

import logging
import threading
from collections.abc import Sequence
from typing import Protocol

from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.download_model import is_model_available, model_target_dir
from agent_service.services.memory.rag.torch_loading import load_with_safe_module_apply
from agent_service.services.memory.rag.sentence_transformer_imports import load_cross_encoder_type
from agent_service.services.memory.rag.hybrid_retrieval import HybridRetrievalCandidate

logger = logging.getLogger(__name__)

_rerank_provider: SentenceTransformerCrossEncoderProvider | None = None
_rerank_provider_lock = threading.Lock()


def _get_shared_rerank_provider(config: AgentConfig) -> SentenceTransformerCrossEncoderProvider:
    """返回模块级单例 ReRank provider,避免多次加载模型。"""
    global _rerank_provider
    if _rerank_provider is not None:
        return _rerank_provider
    with _rerank_provider_lock:
        if _rerank_provider is None:
            _rerank_provider = SentenceTransformerCrossEncoderProvider(config=config)
        return _rerank_provider


def is_shared_rerank_provider_loaded() -> bool:
    """返回共享 ReRank provider 是否已经持有可用模型，不触发加载。"""

    return _rerank_provider is not None and _rerank_provider.loaded


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
        """保存配置并延迟（异步）加载模型。"""

        self.config = config
        self._model: object | None = None
        self._load_lock = threading.Lock()
        self._load_thread: threading.Thread | None = None
        self._load_error: Exception | None = None

    def warmup(self) -> None:
        """触发后台模型加载，不阻塞。"""

        self._get_model()

    @property
    def loaded(self) -> bool:
        """返回当前 provider 是否已经完成模型加载。"""

        return self._model is not None

    def score_pairs(self, *, query: str, documents: Sequence[str]) -> list[float]:
        """
        对 query-document 对打分。

        query: 当前用户问题。
        documents: 待精排的候选文本列表。
        """

        if not documents:
            return []
        model = self._get_model()
        if model is None:
            raise RuntimeError("ReRank 模型尚未就绪，正在异步加载中，请稍后重试。")
        pairs = [[query, document] for document in documents]
        raw_scores = model.predict(pairs, show_progress_bar=False)
        return [self._normalize_score(float(score)) for score in raw_scores]

    def _get_model(self) -> object | None:
        """异步加载本地 CrossEncoder 模型。

        首次调用触发后台加载线程，后续调用若加载未完成则返回 None。
        """

        if self._model is not None:
            from agent_service.core.model_status import ModelState, set_model_state

            set_model_state("rerank", ModelState.READY)
            return self._model
        if self._load_error is not None:
            raise self._load_error
        with self._load_lock:
            if (
                self._load_thread is not None
                and not self._load_thread.is_alive()
                and self._model is None
                and self._load_error is None
            ):
                self._load_thread = None
            if self._load_thread is None:
                self._load_thread = threading.Thread(
                    target=self._load_model_in_thread,
                    daemon=True,
                    name="rerank-model-load",
                )
                self._load_thread.start()
        return None

    def _load_model_in_thread(self) -> None:
        """在后台线程中执行实际模型加载。"""

        from agent_service.core.model_status import ModelState, set_model_state

        try:
            CrossEncoder = load_cross_encoder_type()
        except Exception as exc:  # noqa: BLE001
            set_model_state("rerank", ModelState.ERROR)
            self._load_error = (
                RuntimeError("缺少 sentence-transformers 依赖,无法加载本地 ReRank 模型。")
                if isinstance(exc, ImportError)
                else exc
            )
            logger.exception("ReRank 模型依赖导入失败: %s", exc)
            return

        if not self.config.model.rerank_model_name:
            set_model_state("rerank", ModelState.ERROR)
            self._load_error = ValueError("config.model.rerank_model_name 不能为空。")
            return
        model_path = model_target_dir(
            self.config.model.rerank_model_name,
            self.config.storage.rerank_model_dir,
        )
        if not is_model_available(model_path):
            set_model_state("rerank", ModelState.AWAITING_DOWNLOAD)
            return
        set_model_state("rerank", ModelState.LOADING)
        banner = "=" * 57
        logger.info(banner)
        logger.info("开始加载 ReRank 模型: %s", self.config.model.rerank_model_name)
        logger.info("模型路径: %s", model_path)
        logger.info(banner)
        try:
            import torch as _torch

            self._model = load_with_safe_module_apply(
                _torch,
                lambda: CrossEncoder(str(model_path)),
            )
            set_model_state("rerank", ModelState.READY)
        except Exception as exc:
            set_model_state("rerank", ModelState.ERROR)
            self._load_error = exc
            return
        logger.info(banner)
        logger.info("ReRank 模型加载完成: %s", self.config.model.rerank_model_name)
        logger.info(banner)

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
        self._cached_provider: RerankProvider | None = provider

    def warmup(self) -> None:
        """预加载底层 ReRank 模型到内存。"""

        if not self.is_enabled():
            return
        provider = self.provider or _get_shared_rerank_provider(self.config)
        self._cached_provider = provider
        if hasattr(provider, 'warmup'):
            provider.warmup()

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
        对混合检索候选做ReRank精排。

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
            # 取Top-K条作为候选项
            return ranked[:top_k]
        provider = self.provider or _get_shared_rerank_provider(self.config)
        self._cached_provider = provider
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
