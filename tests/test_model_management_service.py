"""
模型管理聚合状态与真实下载进度测试。

使用说明:
验证管理页所需的模型名称、路径、大小、文件数、启用/内存状态和真实字节
进度全部由后端生成，不允许前端猜测。
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
from types import ModuleType
from types import SimpleNamespace

from agent_service.core.model_status import ModelState, set_model_state
from agent_service.scripts.download_model import (
    MODEL_MARKER_FILE,
    PADDLEOCR_MARKER_FILE,
    get_all_download_progress,
    model_target_dir,
    reset_download_progress,
    update_download_progress,
)
import agent_service.scripts.download_model as download_module
from agent_service.services.model_management_service import ModelManagementService


class _SettingsStub:
    """提供用户级 OCR 启用状态。"""

    def is_ocr_enabled_for_user(self, *, user_id: str) -> bool:  # noqa: ARG002
        """测试用户启用 OCR。"""

        return True


def _complete_hf_model(path: Path, marker: str) -> None:
    """创建满足现有完整性规则的最小 Hugging Face 模型目录。"""

    path.mkdir(parents=True)
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "model.safetensors").write_bytes(b"weight-data")
    (path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (path / MODEL_MARKER_FILE).write_text(marker, encoding="utf-8")


def test_management_reports_real_model_details_and_enabled_state(tmp_path: Path) -> None:
    """管理接口应汇总真实磁盘与运行状态，不依赖前端路径映射。"""

    embedding_root = tmp_path / "models" / "embedding"
    rerank_root = tmp_path / "models" / "rerank"
    ocr_root = tmp_path / "models" / "ocr"
    embedding_name = "BAAI/test-embedding"
    rerank_name = "BAAI/test-rerank"
    embedding_target = model_target_dir(embedding_name, embedding_root)
    _complete_hf_model(embedding_target, embedding_name)
    ocr_root.mkdir(parents=True)
    (ocr_root / PADDLEOCR_MARKER_FILE).write_text("language=ch", encoding="utf-8")
    (ocr_root / "det.bin").write_bytes(b"ocr-data")
    config = SimpleNamespace(
        model=SimpleNamespace(embedding_model_name=embedding_name, rerank_model_name=rerank_name),
        storage=SimpleNamespace(
            embedding_model_dir=embedding_root,
            rerank_model_dir=rerank_root,
            paddleocr_model_dir=ocr_root,
        ),
        ocr=SimpleNamespace(
            language="ch",
            device="cpu",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
        ),
    )
    set_model_state("embedding", ModelState.READY)
    set_model_state("rerank", ModelState.NOT_DOWNLOADED)
    set_model_state("paddleocr", ModelState.READY)
    reset_download_progress("embedding")

    result = ModelManagementService(config=config, settings_service=_SettingsStub()).get_management_status(user_id="u1")
    models = {item["key"]: item for item in result["models"]}

    assert models["embedding"]["name"] == embedding_name
    assert models["embedding"]["path"] == str(embedding_target)
    assert models["embedding"]["size_bytes"] > 0
    assert models["embedding"]["file_count"] == 4
    assert models["embedding"]["enabled"] is True
    assert models["embedding"]["active"] is True
    assert models["rerank"]["downloaded"] is False
    assert models["paddleocr"]["enabled"] is True
    assert models["paddleocr"]["details"]["language"] == "ch"


def test_download_progress_uses_real_bytes_and_honest_unknown_total() -> None:
    """已知总量显示真实百分比；未知总量只显示字节和不确定状态。"""

    update_download_progress(
        "embedding",
        status="downloading",
        stage="files",
        downloaded_bytes=50,
        total_bytes=200,
        message="下载模型文件",
    )
    update_download_progress(
        "paddleocr",
        status="downloading",
        stage="official_models",
        downloaded_bytes=75,
        total_bytes=None,
        message="准备 OCR 模型",
    )

    progress = get_all_download_progress()

    assert progress["embedding"] == {
        "status": "downloading",
        "stage": "files",
        "downloaded_bytes": 50,
        "total_bytes": 200,
        "percent": 25.0,
        "indeterminate": False,
        "message": "下载模型文件",
    }
    assert progress["paddleocr"]["downloaded_bytes"] == 75
    assert progress["paddleocr"]["percent"] is None
    assert progress["paddleocr"]["indeterminate"] is True


def test_huggingface_tracker_observes_real_intermediate_file_bytes(tmp_path: Path, monkeypatch) -> None:
    """下载器必须从实际文件增长得到 25%，而不是定时器伪造百分比。"""

    fake_hub = ModuleType("huggingface_hub")

    class _HfApi:
        """返回一个总大小为 400 字节的仓库。"""

        def model_info(self, model_name: str, *, files_metadata: bool) -> SimpleNamespace:  # noqa: ARG002
            return SimpleNamespace(siblings=[SimpleNamespace(size=400)])

    def snapshot_download(*, repo_id: str, local_dir: str, local_dir_use_symlinks: bool) -> None:  # noqa: ARG001
        target = Path(local_dir)
        (target / "part.bin").write_bytes(b"a" * 100)
        time.sleep(0.9)
        (target / "part.bin").write_bytes(b"a" * 400)

    fake_hub.HfApi = _HfApi  # type: ignore[attr-defined]
    fake_hub.snapshot_download = snapshot_download  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    observed: list[dict[str, object]] = []
    real_update = download_module.update_download_progress

    def record_progress(model_type: str, **payload: object) -> None:
        real_update(model_type, **payload)  # type: ignore[arg-type]
        observed.append(download_module.get_download_progress(model_type))

    monkeypatch.setattr(download_module, "update_download_progress", record_progress)

    download_module._tracked_hf_download("demo/model", tmp_path / "model", "embedding")

    assert any(item["status"] == "downloading" and item["percent"] == 25.0 for item in observed)
    assert observed[-1]["status"] == "completed"
    assert observed[-1]["percent"] == 100.0
