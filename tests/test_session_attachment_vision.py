"""
会话图片附件 OCR 与本地视觉理解组合测试。

使用说明:
通过假的视觉服务验证上传图片会在原有 OCR/占位文本之后追加视觉语义，且不会
下载或执行真实模型。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.rag.image_ocr import ImageOcrResult, ImageOcrService
from agent_service.services.session_attachment_service import SessionAttachmentService


class _SettingsStub:
    """提供附件服务需要的 active 知识库和 OCR 开关。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    def get_active_knowledge_library(self, *, user_id: str) -> dict[str, str]:  # noqa: ARG002
        """返回测试专用知识库。"""

        return {"library_id": "library-1", "name": "测试库", "knowledge_dir": str(self.root)}

    def is_ocr_enabled_for_user(self, *, user_id: str) -> bool:  # noqa: ARG002
        """关闭真实 OCR，保留解析器生成的图片元数据占位。"""

        return False


class _VisionStub:
    """记录 OCR 文本并返回稳定的视觉语义。"""

    def __init__(self) -> None:
        self.ocr_text = ""

    def understand_image(self, *, image_path: Path, ocr_text: str, prompt: str = "") -> str:  # noqa: ARG002
        """模拟本地 Qwen 的图片理解输出。"""

        self.ocr_text = ocr_text
        return "图中有一条从输入文档指向知识库的蓝色箭头。"


def _png_bytes() -> bytes:
    """生成一张无需测试资源文件的最小 PNG。"""

    buffer = BytesIO()
    Image.new("RGB", (16, 16), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_uploaded_image_combines_ocr_text_and_local_vision_description(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """直接上传图片时必须先保留 OCR 结果，再追加本地模型的视觉理解。"""

    config = AgentConfig.load_config(
        {
            "storage": {
                "base_data_dir": str(tmp_path / "runtime"),
                "sqlite_path": str(tmp_path / "runtime" / "db" / "attachments.db"),
            }
        },
        load_env=False,
        ensure_directories=True,
        ensure_models=False,
    )
    vision = _VisionStub()
    monkeypatch.setattr(
        ImageOcrService,
        "extract_image_text",
        lambda self, source_path: ImageOcrResult(  # noqa: ARG005
            content="OCR 识别文字",
            has_text=True,
            word_count=1,
            average_confidence=0.99,
            engine_available=True,
        ),
    )
    service = SessionAttachmentService(
        config=config,
        settings_service=_SettingsStub(tmp_path / "knowledge"),  # type: ignore[arg-type]
        vision_service=vision,
    )

    uploaded = service.upload_file(
        user_id="u1",
        session_id="s1",
        filename="diagram.png",
        content=_png_bytes(),
        mime_type="image/png",
    )
    record = service.list_session_attachments(user_id="u1", session_id="s1")[0]
    extracted = Path(record.text_path).read_text(encoding="utf-8")

    assert uploaded["metadata"]["multimodal_metadata"]["vision_status"] == "completed"
    assert "OCR 识别文字" in vision.ocr_text
    assert "视觉理解" in extracted
    assert "蓝色箭头" in extracted
