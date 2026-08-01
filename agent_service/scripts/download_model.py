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
import logging
import os
import shutil
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

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
PADDLEOCR_MARKER_FILE = ".paddleocr_download_complete"

# ---- 下载进度跟踪 ----
_download_progress: dict[str, float] = {}
_download_progress_lock = threading.Lock()


def update_download_progress(model_type: str, pct: float) -> None:
    with _download_progress_lock:
        _download_progress[model_type] = pct


def get_download_progress(model_type: str) -> float:
    with _download_progress_lock:
        return _download_progress.get(model_type, 0.0)


def get_all_download_progress() -> dict[str, float]:
    with _download_progress_lock:
        return dict(_download_progress)


def _tracked_hf_download(
    model_name: str,
    target_dir: Path,
    model_type: str,
) -> None:
    """从 Hugging Face 下载模型并按文件数估算进度。"""

    from huggingface_hub import list_repo_files, snapshot_download

    update_download_progress(model_type, 0.0)
    total_files = 0
    try:
        repo_files = list_repo_files(model_name)
        total_files = len(repo_files)
    except Exception:
        pass

    target_dir.mkdir(parents=True, exist_ok=True)
    initial_count = sum(1 for _ in target_dir.rglob("*") if _.is_file()) if target_dir.exists() else 0
    stop_event = threading.Event()

    if total_files > 0:
        def _track() -> None:
            while not stop_event.is_set():
                current = sum(1 for _ in target_dir.rglob("*") if _.is_file()) - initial_count
                pct = min(99.0, round(current / total_files * 100, 1))
                update_download_progress(model_type, pct)
                stop_event.wait(1.5)

        threading.Thread(target=_track, daemon=True).start()

    snapshot_download(
        repo_id=model_name,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )
    (target_dir / MODEL_MARKER_FILE).write_text(model_name, encoding="utf-8")
    stop_event.set()
    update_download_progress(model_type, 100.0)


def ensure_model(model_name: str, model_dir: Path | str, model_type: str | None = None) -> Path | None:
    """
    检查指定模型是否已经存在,不存在时从 Hugging Face 下载。

    model_name: Hugging Face 模型名称,例如 BAAI/bge-small-zh-v1.5。
    model_dir: 该类模型的本地缓存根目录。
    """

    if not model_name:
        return None

    target_dir = model_target_dir(model_name, model_dir)
    if is_model_available(target_dir):
        logger.info("模型已存在,跳过下载: %s | 路径: %s", model_name, target_dir)
        return target_dir

    _download_from_huggingface(model_name, target_dir, model_type=model_type)
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


def ensure_paddleocr_models(
    *,
    paddleocr_model_dir: Path | str,
    language: str,
    text_detection_model_name: str,
    text_recognition_model_name: str,
    device: str = "cpu",
) -> Path:
    """
    预热 PaddleOCR 文本检测与识别模型。

    paddleocr_model_dir: PaddleOCR 模型缓存根目录。
    language: OCR 语言参数,中英文场景使用 ch。
    text_detection_model_name: 文本检测模型名称。
    text_recognition_model_name: 文本识别模型名称。
    device: 推理设备,默认 cpu。
    """

    target_root = Path(paddleocr_model_dir).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    _disable_paddleocr_mkldnn_by_default()
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("缺少 paddleocr / paddlepaddle 依赖,无法自动准备 OCR 模型。") from exc

    logger.info("开始准备 PaddleOCR 模型: det=%s rec=%s", text_detection_model_name, text_recognition_model_name)
    _build_paddleocr_pipeline(
        PaddleOCR=PaddleOCR,
        language=language,
        text_detection_model_name=text_detection_model_name,
        text_recognition_model_name=text_recognition_model_name,
        text_detection_model_dir=target_root / "text_detection",
        text_recognition_model_dir=target_root / "text_recognition",
        device=device,
    )
    _sync_paddlex_official_model(
        model_name=text_detection_model_name,
        target_dir=target_root / "text_detection",
    )
    _sync_paddlex_official_model(
        model_name=text_recognition_model_name,
        target_dir=target_root / "text_recognition",
    )
    marker_payload = "\n".join(
        [
            f"language={language}",
            f"text_detection_model_name={text_detection_model_name}",
            f"text_recognition_model_name={text_recognition_model_name}",
            f"device={device}",
        ]
    )
    (target_root / PADDLEOCR_MARKER_FILE).write_text(marker_payload, encoding="utf-8")
    logger.info("PaddleOCR 模型准备完成: %s", target_root)
    return target_root


def _build_paddleocr_pipeline(
    *,
    PaddleOCR: object,
    language: str,
    text_detection_model_name: str,
    text_recognition_model_name: str,
    device: str,
    text_detection_model_dir: Path | None = None,
    text_recognition_model_dir: Path | None = None,
) -> object:
    """兼容 PaddleOCR 3.x 和旧版构造参数创建 OCR pipeline。"""

    _disable_paddleocr_mkldnn_by_default()
    detection_dir = _existing_paddle_model_dir(text_detection_model_dir)
    recognition_dir = _existing_paddle_model_dir(text_recognition_model_dir)
    try:
        return PaddleOCR(
            lang=language,
            text_detection_model_name=text_detection_model_name,
            text_recognition_model_name=text_recognition_model_name,
            text_detection_model_dir=detection_dir,
            text_recognition_model_dir=recognition_dir,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=device,
        )
    except TypeError:
        return PaddleOCR(lang=language, use_angle_cls=False, show_log=False)


def _disable_paddleocr_mkldnn_by_default() -> None:
    """默认关闭 PaddleX MKLDNN,规避 Windows CPU 下部分 OCR 模型 oneDNN 推理异常。"""

    os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "False"


def _existing_paddle_model_dir(model_dir: Path | None) -> str | None:
    """仅当本地 PaddleOCR 模型目录已经完整时才传给 PaddleOCR。"""

    if model_dir is None:
        return None
    return str(model_dir) if (model_dir / "inference.yml").is_file() else None


def _sync_paddlex_official_model(*, model_name: str, target_dir: Path) -> None:
    """把 PaddleX 自动下载的官方模型同步到项目 runtime 模型目录。"""

    source_dir = Path.home() / ".paddlex" / "official_models" / model_name
    if not (source_dir / "inference.yml").is_file():
        return
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)


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


def _download_from_huggingface(model_name: str, target_dir: Path, model_type: str | None = None) -> None:
    """调用 huggingface_hub 下载模型快照。"""

    if model_type:
        _tracked_hf_download(model_name, target_dir, model_type)
        return

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("缺少 huggingface_hub 依赖,无法自动下载模型。") from exc

    banner = "=" * 57
    logger.info(banner)
    logger.info("开始下载模型: %s", model_name)
    logger.info("目标目录: %s", target_dir)
    logger.info(banner)
    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=model_name,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )
    (target_dir / MODEL_MARKER_FILE).write_text(model_name, encoding="utf-8")
    logger.info(banner)
    logger.info("模型下载完成: %s", model_name)
    logger.info(banner)


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
