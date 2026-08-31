"""
Embedding 向量生成服务。

功能说明:
本文件封装本地 Embedding 模型调用。生产路径使用 `sentence-transformers`
加载 `scripts/download_model.py` 下载后的具体模型目录并生成向量。测试或特殊
场景可以注入自定义 provider,避免真实模型依赖。

使用说明:
service = EmbeddingService(config=config)
vectors = service.embed_texts(["hello"])
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Sequence
from typing import Protocol

from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.download_model import is_model_available, model_target_dir
from agent_service.services.memory.rag.torch_loading import load_with_safe_module_apply
from agent_service.services.memory.rag.sentence_transformer_imports import load_sentence_transformer_type

logger = logging.getLogger(__name__)

_provider: SentenceTransformerEmbeddingProvider | None = None
_provider_lock = threading.Lock()


def _get_shared_provider(config: AgentConfig) -> SentenceTransformerEmbeddingProvider:
    """返回模块级单例 provider,避免多次加载模型。"""
    global _provider
    if _provider is not None:
        return _provider
    with _provider_lock:
        if _provider is None:
            _provider = SentenceTransformerEmbeddingProvider(config=config)
        return _provider


def is_shared_embedding_provider_loaded() -> bool:
    """返回共享 Embedding provider 是否已经持有可用模型，不触发加载。"""

    return _provider is not None and _provider.loaded


class EmbeddingProvider(Protocol):
    """
    Embedding 提供者协议。

    embed_texts: 接收文本列表并返回同顺序的浮点向量列表。
    """

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """生成文本向量。"""


class SentenceTransformerEmbeddingProvider:
    """
    基于 sentence-transformers 的本地 Embedding 提供者。

    config: 全局配置对象,用于读取模型目录和模型名称。
    """

    def __init__(self, *, config: AgentConfig) -> None:
        """保存配置并延迟（异步）加载模型。"""

        self.config = config
        self._model: object | None = None
        self._load_lock = threading.Lock()
        self._load_thread: threading.Thread | None = None
        self._load_error: Exception | None = None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """
        生成文本向量。

        texts: 需要向量化的文本列表。
        """

        if not texts:
            return []
        model = self._get_model(wait=True)
        if model is None:
            raise RuntimeError("Embedding 模型尚未就绪，正在异步加载中，请稍后重试。")
        vectors = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        result: list[list[float]] = []
        for i, vector in enumerate(vectors):
            vec = [float(value) for value in vector]
            if any(not math.isfinite(v) for v in vec):
                logger.warning("文本索引 %d 生成的向量包含 NaN/Inf，已替换为零向量", i)
                vec = [0.0] * len(vec)
            result.append(vec)
        return result

    def warmup(self) -> None:
        """预加载模型到内存,避免首次请求冷启动延迟。"""

        self._get_model(wait=False)

    @property
    def loaded(self) -> bool:
        """返回当前 provider 是否已经完成模型加载。"""

        return self._model is not None

    def _get_model(self, *, wait: bool) -> object | None:
        """异步加载本地 sentence-transformers 模型。

        首次调用触发后台加载线程，后续调用若加载未完成则返回 None，
        或等待加载完成后返回模型实例。
        """

        if self._model is not None:
            from agent_service.core.model_status import ModelState, set_model_state

            set_model_state("embedding", ModelState.READY)
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
                    name="embedding-model-load",
                )
                self._load_thread.start()
            load_thread = self._load_thread
        if wait:
            load_thread.join()
            if self._load_error is not None:
                raise self._load_error
            return self._model
        return self._model

    def _load_model_in_thread(self) -> None:
        """在后台线程中执行实际模型加载。"""

        from agent_service.core.model_status import ModelState, set_model_state

        try:
            SentenceTransformer = load_sentence_transformer_type()
        except Exception as exc:  # noqa: BLE001
            set_model_state("embedding", ModelState.ERROR)
            self._load_error = (
                RuntimeError("缺少 sentence-transformers 依赖,请先安装 agent_service/requirements.txt。")
                if isinstance(exc, ImportError)
                else exc
            )
            logger.exception("Embedding 模型依赖导入失败: %s", exc)
            return

        if not self.config.model.embedding_model_name:
            set_model_state("embedding", ModelState.ERROR)
            self._load_error = ValueError("config.model.embedding_model_name 不能为空。")
            return
        model_path = model_target_dir(
            self.config.model.embedding_model_name,
            self.config.storage.embedding_model_dir,
        )
        if not is_model_available(model_path):
            set_model_state("embedding", ModelState.AWAITING_DOWNLOAD)
            return
        import os
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        set_model_state("embedding", ModelState.LOADING)
        banner = "=" * 57
        logger.info(banner)
        logger.info("开始加载 Embedding 模型: %s", self.config.model.embedding_model_name)
        logger.info("模型路径: %s", model_path)
        logger.info(banner)
        try:
            # 绕过 PyTorch 2.5+ meta tensor 与 self.to(device) 的兼容性问题:
            # SentenceTransformer.__init__ 内部会调用 self.to(device),该操作会递归
            # 遍历所有子模块并对每个参数调用 .to()。如果某个参数仍是 meta tensor,
            # .to() 会因无法复制抛出 RuntimeError ("Cannot copy out of meta tensor")。
            # 解决方案: 在调用 _apply 前,预先将整个模型树中所有 meta tensor 物化到 CPU。
            import torch as _torch

            self._model = load_with_safe_module_apply(
                _torch,
                lambda: SentenceTransformer(str(model_path)),
            )
            set_model_state("embedding", ModelState.READY)
        except Exception as exc:
            logger.exception("Embedding 模型加载失败: %s", exc)
            set_model_state("embedding", ModelState.ERROR)
            self._load_error = exc
            return
        logger.info(banner)
        logger.info("Embedding 模型加载完成: %s", self.config.model.embedding_model_name)
        logger.info(banner)


class EmbeddingService:
    """
    Embedding 服务门面。

    config: 全局配置对象。
    provider: 可选自定义 provider,测试时可注入假向量生成器。
    """

    def __init__(self, *, config: AgentConfig, provider: EmbeddingProvider | None = None) -> None:
        """初始化 Embedding 服务。"""

        self.config = config
        self.provider = provider or _get_shared_provider(config)

    def warmup(self) -> None:
        """预加载底层 Embedding 模型到内存。"""

        if hasattr(self.provider, 'warmup'):
            self.provider.warmup()

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """
        批量生成文本向量。

        texts: 需要向量化的文本列表。
        """

        return self.provider.embed_texts(texts)

    def embed_text(self, text: str) -> list[float]:
        """
        生成单条文本向量。

        text: 需要向量化的文本。
        """

        vectors = self.embed_texts([text])
        return vectors[0] if vectors else []
