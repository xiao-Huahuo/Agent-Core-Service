"""
模型下载脚本。

功能说明:
本文件负责检查并下载本地 Embedding 模型和 ReRank 模型。`AgentConfig.load_config()`
会在加载配置时调用 `ensure_models()` 自动检查模型是否存在;如果模型目录缺失、
缺少模型配置或缺少权重文件,则会使用 `huggingface_hub.snapshot_download()` 下载模型。

手动使用:
可以通过命令行同时指定 Embedding 与 ReRank 的模型名称和本地绝对下载目录:

python -m agent_service.scripts.download_model \
  --embedding-model-name "BAAI/bge-small-zh-v1.5" \
  --embedding-model-dir "D:/Projects/Python/AgentService/runtime/models/embedding" \
  --rerank-model-name "BAAI/bge-reranker-v2-m3" \
  --rerank-model-dir "D:/Projects/Python/AgentService/runtime/models/rerank"
"""

from __future__ import annotations

import argparse
from pathlib import Path


MODEL_MARKER_FILE = ".download_complete"
MODEL_CONFIG_FILES = {
    "config.json",
    "modules.json",
    "config_sentence_transformers.json",
}
MODEL_WEIGHT_FILES = {
    "model.safetensors",
    "pytorch_model.bin",
    "model.onnx",
}
MODEL_TOKENIZER_FILES = {
    "tokenizer.json",
    "tokenizer_config.json",
    "sentencepiece.bpe.model",
    "vocab.txt",
}


def ensure_model(model_name: str, model_dir: Path | str) -> Path | None:
    """
    检查指定模型是否已经存在,不存在时从 Hugging Face 下载。

    model_name: Hugging Face 模型名称,例如 BAAI/bge-small-zh-v1.5。
    model_dir: 该类模型的本地缓存根目录。
    """

    if not model_name:
        return None

    target_dir = model_target_dir(model_name, model_dir)
    if is_model_available(target_dir):
        return target_dir

    _download_from_huggingface(model_name, target_dir)
    if not is_model_available(target_dir):
        raise RuntimeError(f"模型下载后仍不完整: {target_dir}")
    return target_dir


def ensure_models(
    *,
    embedding_model_name: str,
    embedding_model_dir: Path | str,
    rerank_model_name: str,
    rerank_model_dir: Path | str,
) -> None:
    """
    检查 Embedding 与 ReRank 模型,缺失时分别下载到对应目录。

    embedding_model_name: Embedding 模型名称。
    embedding_model_dir: Embedding 模型本地缓存根目录。
    rerank_model_name: ReRank 模型名称。
    rerank_model_dir: ReRank 模型本地缓存根目录。
    """

    ensure_model(embedding_model_name, embedding_model_dir)
    ensure_model(rerank_model_name, rerank_model_dir)


def model_target_dir(model_name: str, model_dir: Path | str) -> Path:
    """
    根据模型名称生成稳定的本地目标目录。

    model_name: Hugging Face 模型名称。
    model_dir: 该类模型的本地缓存根目录。
    """

    safe_name = model_name.replace("/", "__")
    return Path(model_dir).expanduser().resolve() / safe_name


def is_model_available(target_dir: Path) -> bool:
    """
    判断目标目录中是否已经存在完整可用的模型文件。

    target_dir: 某个具体模型的本地目录。
    """

    if not target_dir.exists() or not target_dir.is_dir():
        return False
    file_names = {path.name for path in target_dir.rglob("*") if path.is_file()}
    has_config = bool(file_names & MODEL_CONFIG_FILES)
    has_weight = bool(file_names & MODEL_WEIGHT_FILES)
    has_tokenizer = bool(file_names & MODEL_TOKENIZER_FILES)
    has_marker = (target_dir / MODEL_MARKER_FILE).exists()
    return has_marker and has_config and has_weight and has_tokenizer


def _download_from_huggingface(model_name: str, target_dir: Path) -> None:
    """调用 huggingface_hub 下载模型快照。"""

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("缺少 huggingface_hub 依赖,无法自动下载模型。") from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=model_name,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )
    (target_dir / MODEL_MARKER_FILE).write_text(model_name, encoding="utf-8")


def main() -> None:
    """命令行入口,用于手动下载 Embedding 与 ReRank 两类模型。"""

    parser = argparse.ArgumentParser(description="Download Hugging Face embedding and rerank models.")
    parser.add_argument("--embedding-model-name", required=True)
    parser.add_argument("--embedding-model-dir", required=True)
    parser.add_argument("--rerank-model-name", required=True)
    parser.add_argument("--rerank-model-dir", required=True)
    args = parser.parse_args()
    ensure_models(
        embedding_model_name=args.embedding_model_name,
        embedding_model_dir=args.embedding_model_dir,
        rerank_model_name=args.rerank_model_name,
        rerank_model_dir=args.rerank_model_dir,
    )


if __name__ == "__main__":
    main()
