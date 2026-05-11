from __future__ import annotations

import argparse
from pathlib import Path


MODEL_MARKER_FILE = ".download_complete"
MODEL_REQUIRED_FILES = {
    "config.json",
    "model.safetensors",
    "pytorch_model.bin",
    "modules.json",
    "tokenizer.json",
}


def ensure_model(model_name: str, model_dir: Path | str) -> Path | None:
    """
    检查指定模型是否已经存在,不存在时从 Hugging Face 下载。

    model_name: Hugging Face 模型名称,例如 BAAI/bge-small-zh-v1.5。
    model_dir: 该类模型的本地缓存根目录。
    """

    if not model_name:
        return None

    target_dir = _model_target_dir(model_name, model_dir)
    if _is_model_available(target_dir):
        return target_dir

    _download_from_huggingface(model_name, target_dir)
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


def _model_target_dir(model_name: str, model_dir: Path | str) -> Path:
    """根据模型名称生成稳定的本地目标目录。"""

    safe_name = model_name.replace("/", "__")
    return Path(model_dir).expanduser().resolve() / safe_name


def _is_model_available(target_dir: Path) -> bool:
    """判断目标目录中是否已经存在可用模型文件。"""

    if not target_dir.exists() or not target_dir.is_dir():
        return False
    if (target_dir / MODEL_MARKER_FILE).exists():
        return True
    return any(path.name in MODEL_REQUIRED_FILES for path in target_dir.rglob("*") if path.is_file())


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
    """命令行入口,用于手动下载单个模型。"""

    parser = argparse.ArgumentParser(description="Download a Hugging Face model into a local directory.")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-dir", required=True)
    args = parser.parse_args()
    ensure_model(args.model_name, args.model_dir)


if __name__ == "__main__":
    main()
