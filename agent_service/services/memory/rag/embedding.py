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

from collections.abc import Sequence
from typing import Protocol

from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.download_model import ensure_model, model_target_dir


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
        """保存配置并延迟加载模型。"""

        self.config = config
        self._model: object | None = None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """
        生成文本向量。

        texts: 需要向量化的文本列表。
        """

        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(list(texts), normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]

    def _get_model(self) -> object:
        """延迟加载本地 sentence-transformers 模型。"""

        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "缺少 sentence-transformers 依赖,请先安装 agent_service/requirements.txt。"
            ) from exc

        if not self.config.model.embedding_model_name:
            raise ValueError("config.model.embedding_model_name 不能为空。")
        model_path = ensure_model(
            self.config.model.embedding_model_name,
            self.config.storage.embedding_model_dir,
        )
        if model_path is None:
            model_path = model_target_dir(
                self.config.model.embedding_model_name,
                self.config.storage.embedding_model_dir,
            )
        if not model_path.exists():
            raise FileNotFoundError(f"Embedding 模型目录不存在: {model_path}")
        self._model = SentenceTransformer(str(model_path))
        return self._model


class EmbeddingService:
    """
    Embedding 服务门面。

    config: 全局配置对象。
    provider: 可选自定义 provider,测试时可注入假向量生成器。
    """

    def __init__(self, *, config: AgentConfig, provider: EmbeddingProvider | None = None) -> None:
        """初始化 Embedding 服务。"""

        self.config = config
        self.provider = provider or SentenceTransformerEmbeddingProvider(config=config)

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
