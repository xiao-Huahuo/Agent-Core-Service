"""
图片 OCR 工具。

功能说明:
本文件封装 PaddleOCR 图片文字识别,用于普通图片预览和图片知识源入库。调用方传入
AgentConfig 后,工具会按配置选择中英文 OCR 模型、推理设备和置信度阈值,并将识别
结果按图片中的行列位置重排为可检索文本。未启用 OCR 或缺少 PaddleOCR 依赖时返回
空结果而不是打断预览。

使用说明:
service = ImageOcrService(config=config)
result = service.extract_image_text(Path("demo.png"))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_service.core.agent_config import AgentConfig
from agent_service.scripts.download_model import _disable_paddleocr_mkldnn_by_default
from agent_service.scripts.download_model import _build_paddleocr_pipeline

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ImageOcrResult:
    """
    图片 OCR 结果。

    content: 按图片排版重排后的文本。
    has_text: 是否识别到可信文字。
    word_count: 可信文本片段数量。
    average_confidence: 可信文本片段平均置信度。
    engine_available: OCR 引擎是否可用。
    """

    content: str = ""
    has_text: bool = False
    word_count: int = 0
    average_confidence: float = 0.0
    engine_available: bool = False


class ImageOcrService:
    """
    图片 OCR 服务。

    config: 全局配置,用于读取 OCR 开关、PaddleOCR 模型名称、语言和置信度阈值。
    """

    def __init__(self, *, config: AgentConfig) -> None:
        """保存配置并延迟创建 PaddleOCR pipeline。"""

        self.config = config
        self._pipeline: Any | None = None

    def extract_image_text(self, source_path: Path) -> ImageOcrResult:
        """
        对单张图片执行 OCR。

        source_path: 图片文件路径。
        """

        if not self.config.ocr.enabled:
            return ImageOcrResult()
        pipeline = self._get_pipeline()
        if pipeline is None:
            return ImageOcrResult()
        try:
            raw_result = self._run_pipeline(pipeline=pipeline, source_path=source_path)
        except Exception as exc:
            logger.warning("PaddleOCR 图片推理失败: %s | path=%s", exc, source_path)
            return ImageOcrResult(engine_available=False)

        items = self._collect_items(raw_result)
        trusted_items = [item for item in items if item["confidence"] >= self.config.ocr.min_confidence]
        if not trusted_items:
            return ImageOcrResult(engine_available=True)
        content = self._format_items_as_lines(trusted_items)
        average_confidence = sum(float(item["confidence"]) for item in trusted_items) / len(trusted_items)
        return ImageOcrResult(
            content=content,
            has_text=bool(content.strip()),
            word_count=len(trusted_items),
            average_confidence=average_confidence,
            engine_available=True,
        )

    def _get_pipeline(self) -> Any | None:
        """延迟导入 PaddleOCR 并创建可复用 pipeline。"""

        if self._pipeline is not None:
            return self._pipeline
        _disable_paddleocr_mkldnn_by_default()
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]
        except ImportError:
            return None
        try:
            self._pipeline = _build_paddleocr_pipeline(
                PaddleOCR=PaddleOCR,
                language=self.config.ocr.language,
                text_detection_model_name=self.config.ocr.text_detection_model_name,
                text_recognition_model_name=self.config.ocr.text_recognition_model_name,
                device=self.config.ocr.device,
                text_detection_model_dir=self.config.storage.paddleocr_model_dir / "text_detection",
                text_recognition_model_dir=self.config.storage.paddleocr_model_dir / "text_recognition",
            )
            return self._pipeline
        except Exception:
            return None

    @staticmethod
    def _run_pipeline(*, pipeline: Any, source_path: Path) -> Any:
        """兼容 PaddleOCR 3.x predict 与旧版 ocr 调用入口。"""

        if hasattr(pipeline, "predict"):
            return pipeline.predict(input=str(source_path))
        return pipeline.ocr(str(source_path), cls=False)

    def _collect_items(self, raw_result: Any) -> list[dict[str, Any]]:
        """从 PaddleOCR 不同版本的输出结构中抽取文本、置信度和框坐标。"""

        normalized = _normalize_raw_result(raw_result)
        items: list[dict[str, Any]] = []
        for node in normalized:
            if isinstance(node, dict):
                items.extend(self._collect_items_from_dict(node))
                continue
            if isinstance(node, (list, tuple)):
                items.extend(self._collect_items_from_sequence(node))
        return [item for item in items if str(item.get("text", "")).strip()]

    def _collect_items_from_dict(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """抽取 PaddleOCR 3.x 字典结构中的识别结果。"""

        texts = payload.get("rec_texts") or payload.get("texts") or []
        scores = payload.get("rec_scores") or payload.get("scores") or []
        boxes = payload.get("rec_boxes") or payload.get("dt_polys") or payload.get("boxes") or []
        items: list[dict[str, Any]] = []
        for index, text in enumerate(texts):
            items.append(
                {
                    "text": str(text).strip(),
                    "confidence": _float_at(scores, index, default=1.0),
                    "box": _box_at(boxes, index),
                }
            )
        return items

    def _collect_items_from_sequence(self, payload: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
        """抽取旧版 PaddleOCR 嵌套列表结构中的识别结果。"""

        items: list[dict[str, Any]] = []
        if len(payload) >= 2 and isinstance(payload[1], (list, tuple)) and len(payload[1]) >= 2:
            text = str(payload[1][0]).strip()
            confidence = _safe_float(payload[1][1], default=1.0)
            items.append({"text": text, "confidence": confidence, "box": payload[0]})
            return items
        for child in payload:
            if isinstance(child, dict):
                items.extend(self._collect_items_from_dict(child))
            elif isinstance(child, (list, tuple)):
                items.extend(self._collect_items_from_sequence(child))
        return items

    @staticmethod
    def _format_items_as_lines(items: list[dict[str, Any]]) -> str:
        """把识别结果按纵向行、横向列重排为文本,表格截图会尽量保留列次序。"""

        enriched = []
        for item in items:
            left, top, height = _box_geometry(item.get("box"))
            enriched.append({**item, "left": left, "top": top, "height": height})
        enriched.sort(key=lambda item: (item["top"], item["left"]))
        lines: list[list[dict[str, Any]]] = []
        for item in enriched:
            if not lines:
                lines.append([item])
                continue
            previous = lines[-1]
            average_height = max(8.0, sum(float(node["height"]) for node in previous) / len(previous))
            if abs(float(item["top"]) - float(previous[0]["top"])) <= average_height * 0.6:
                previous.append(item)
            else:
                lines.append([item])
        formatted_lines = []
        for line in lines:
            ordered = sorted(line, key=lambda item: float(item["left"]))
            formatted_lines.append(" | ".join(str(item["text"]).strip() for item in ordered if str(item["text"]).strip()))
        return "\n".join(line for line in formatted_lines if line).strip()


def _normalize_raw_result(raw_result: Any) -> list[Any]:
    """将 PaddleOCR 输出规整为可遍历节点列表。"""

    if raw_result is None:
        return []
    if isinstance(raw_result, dict):
        return [raw_result]
    if isinstance(raw_result, (list, tuple)):
        nodes: list[Any] = []
        for item in raw_result:
            if hasattr(item, "json") and isinstance(item.json, dict):
                nodes.append(item.json)
            elif hasattr(item, "to_dict"):
                nodes.append(item.to_dict())
            elif hasattr(item, "__dict__") and item.__dict__:
                nodes.append(item.__dict__)
            else:
                nodes.append(item)
        return nodes
    if hasattr(raw_result, "json") and isinstance(raw_result.json, dict):
        return [raw_result.json]
    if hasattr(raw_result, "to_dict"):
        return [raw_result.to_dict()]
    if hasattr(raw_result, "__dict__") and raw_result.__dict__:
        return [raw_result.__dict__]
    return []


def _float_at(values: Any, index: int, *, default: float) -> float:
    """安全读取列表中的浮点数。"""

    try:
        return _safe_float(values[index], default=default)
    except (IndexError, TypeError):
        return default


def _box_at(values: Any, index: int) -> Any:
    """安全读取列表中的框坐标。"""

    try:
        return values[index]
    except (IndexError, TypeError):
        return None


def _safe_float(value: Any, *, default: float) -> float:
    """安全转换浮点数。"""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _box_geometry(box: Any) -> tuple[float, float, float]:
    """从 PaddleOCR 框坐标中估算 left/top/height。"""

    if not box:
        return 0.0, 0.0, 12.0
    if isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(item, (int, float)) for item in box):
        left, top, right, bottom = [float(item) for item in box]
        return left, top, max(1.0, bottom - top)
    points: list[tuple[float, float]] = []
    if isinstance(box, (list, tuple)):
        for point in box:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((_safe_float(point[0], default=0.0), _safe_float(point[1], default=0.0)))
    if not points:
        return 0.0, 0.0, 12.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(1.0, max(ys) - min(ys))
