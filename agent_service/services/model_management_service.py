"""
模型管理状态聚合服务。

使用说明:
设置页、REST 与 gRPC 调用 `get_management_status()` 获取模型名称、路径、大小、
磁盘完整性、内存状态、用户启用状态和真实下载进度，前端不推测业务数据。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_service.core.model_status import get_model_status
from agent_service.scripts.download_model import (
    PADDLEOCR_MARKER_FILE,
    get_download_progress,
    is_model_available,
    model_target_dir,
)


class ModelManagementService:
    """把四类本地模型的配置、磁盘和运行状态合并为稳定管理 DTO。"""

    def __init__(self, *, config: Any, settings_service: Any) -> None:
        """保存只读服务配置和用户设置依赖。"""

        self.config = config
        self.settings_service = settings_service

    def get_management_status(self, *, user_id: str) -> dict[str, list[dict[str, Any]]]:
        """返回本地 Qwen、Embedding、ReRank 与 PaddleOCR 的完整管理状态。"""

        states = get_model_status().to_dict()
        embedding = self._hf_model(
            key="embedding",
            label="Embedding 模型",
            role="知识向量化",
            name=self.config.model.embedding_model_name,
            base_path=Path(self.config.storage.embedding_model_dir),
            state=states["embedding"],
        )
        rerank = self._hf_model(
            key="rerank",
            label="ReRank 模型",
            role="检索结果重排",
            name=self.config.model.rerank_model_name,
            base_path=Path(self.config.storage.rerank_model_dir),
            state=states["rerank"],
        )
        local_qwen = self._hf_model(
            key="local_qwen",
            label="本地 Qwen 大语言模型",
            role="本地主 Agent、小模型回退与图片理解",
            name=self.config.model.local_model_name,
            base_path=Path(self.config.storage.local_model_dir),
            state=states["local_qwen"],
            extra_details={
                "device": "CPU",
                "capabilities": "文本生成 / 工具调用 / 图片理解",
                "fallback": "未配置大模型时同时承担主模型与小模型",
            },
        )
        ocr_path = Path(self.config.storage.paddleocr_model_dir).expanduser().resolve()
        ocr_size, ocr_files = self._directory_stats(ocr_path)
        ocr_downloaded = (ocr_path / PADDLEOCR_MARKER_FILE).is_file()
        paddleocr = {
            "key": "paddleocr",
            "label": "PaddleOCR 模型",
            "role": "图片与扫描文档文字识别",
            "name": f"{self.config.ocr.text_detection_model_name} + {self.config.ocr.text_recognition_model_name}",
            "path": str(ocr_path),
            "base_path": str(ocr_path),
            "size_bytes": ocr_size,
            "file_count": ocr_files,
            "status": states["paddleocr"],
            "enabled": bool(self.settings_service.is_ocr_enabled_for_user(user_id=user_id)),
            "active": states["paddleocr"] == "ready",
            "downloaded": ocr_downloaded,
            "progress": get_download_progress("paddleocr"),
            "details": {
                "provider": "PaddleOCR / PaddleX",
                "language": self.config.ocr.language,
                "device": self.config.ocr.device,
                "detection_model": self.config.ocr.text_detection_model_name,
                "recognition_model": self.config.ocr.text_recognition_model_name,
            },
        }
        return {"models": [local_qwen, embedding, rerank, paddleocr]}

    def _hf_model(
        self,
        *,
        key: str,
        label: str,
        role: str,
        name: str,
        base_path: Path,
        state: str,
        extra_details: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """构造一个 Hugging Face 模型的磁盘与运行状态。"""

        target = model_target_dir(name, base_path)
        size_bytes, file_count = self._directory_stats(target)
        return {
            "key": key,
            "label": label,
            "role": role,
            "name": name,
            "path": str(target),
            "base_path": str(Path(base_path).expanduser().resolve()),
            "size_bytes": size_bytes,
            "file_count": file_count,
            "status": state,
            "enabled": bool(name),
            "active": state == "ready",
            "downloaded": is_model_available(target),
            "progress": get_download_progress(key),
            "details": {
                "provider": "Hugging Face",
                "repository": name,
                "model_type": key,
                **(extra_details or {}),
            },
        }

    @staticmethod
    def _directory_stats(path: Path) -> tuple[int, int]:
        """返回目录真实字节数和文件数，不跟随不存在的路径。"""

        if not path.exists():
            return 0, 0
        size_bytes = 0
        file_count = 0
        for item in path.rglob("*"):
            if not item.is_file():
                continue
            try:
                size_bytes += item.stat().st_size
                file_count += 1
            except OSError:
                continue
        return size_bytes, file_count
