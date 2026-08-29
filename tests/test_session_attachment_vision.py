"""
会话图片附件 OCR 与本地视觉理解组合测试。

使用说明:
通过假的视觉服务验证上传图片会在原有 OCR/占位文本之后追加视觉语义，且不会
下载或执行真实模型。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import threading
import time

from PIL import Image

from agent_service.core.agent_config import AgentConfig
from agent_service.services.memory.rag.image_ocr import ImageOcrResult, ImageOcrService
from agent_service.services.session_attachment.service import SessionAttachmentService
from tests.db_test_utils import create_test_engine


class _SettingsStub:
    """提供附件服务需要的 active 知识库和 OCR 开关。"""

    def __init__(self, root: Path, *, vision_enabled: bool = False) -> None:
        """保存测试知识库路径和用户级识图开关。"""

        self.root = root
        self.vision_enabled = vision_enabled

    def get_active_knowledge_library(self, *, user_id: str) -> dict[str, str]:  # noqa: ARG002
        """返回测试专用知识库。"""

        return {"library_id": "library-1", "name": "测试库", "knowledge_dir": str(self.root)}

    def is_ocr_enabled_for_user(self, *, user_id: str) -> bool:  # noqa: ARG002
        """关闭真实 OCR，保留解析器生成的图片元数据占位。"""

        return False

    def is_vision_understanding_enabled_for_user(self, *, user_id: str) -> bool:  # noqa: ARG002
        """返回当前测试指定的用户级识图开关。"""

        return self.vision_enabled


class _VisionStub:
    """记录 OCR 文本并返回稳定的视觉语义。"""

    def __init__(self) -> None:
        """初始化调用次数和最近 OCR 文本。"""

        self.ocr_text = ""
        self.call_count = 0

    def understand_image(self, *, image_path: Path, ocr_text: str, prompt: str = "") -> str:  # noqa: ARG002
        """模拟本地 Qwen 的图片理解输出。"""

        self.call_count += 1
        self.ocr_text = ocr_text
        return "图中有一条从输入文档指向知识库的蓝色箭头。"


def _wait_for_processing(service: SessionAttachmentService, attachment_id: str) -> dict[str, object]:
    """等待假的后台解析结束并返回最新 DTO。"""

    for _ in range(100):
        attachment = service.get_attachment(user_id="u1", session_id="s1", attachment_id=attachment_id)
        status = str((attachment.get("metadata") or {}).get("processing_status"))
        if status in {"completed", "failed"}:
            return attachment
        time.sleep(0.01)
    raise AssertionError("attachment processing did not finish")


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
        engine=create_test_engine(f"sqlite:///{tmp_path / 'runtime' / 'db' / 'attachments.db'}"),
        create_tables=False,
        settings_service=_SettingsStub(tmp_path / "knowledge", vision_enabled=True),  # type: ignore[arg-type]
        vision_service=vision,
    )

    uploaded = service.upload_file(
        user_id="u1",
        session_id="s1",
        filename="diagram.png",
        content=_png_bytes(),
        mime_type="image/png",
    )
    completed = _wait_for_processing(service, str(uploaded["attachment_id"]))
    record = service.list_session_attachments(user_id="u1", session_id="s1")[0]
    extracted = Path(record.text_path).read_text(encoding="utf-8")

    assert uploaded["metadata"]["processing_status"] == "queued"
    assert completed["metadata"]["processing_status"] == "completed"
    assert completed["metadata"]["multimodal_metadata"]["vision_status"] == "completed"
    assert "OCR 识别文字" in vision.ocr_text
    assert "视觉理解" in extracted
    assert "蓝色箭头" in extracted


def test_uploaded_image_skips_qwen_when_vision_setting_is_disabled(tmp_path: Path, monkeypatch: object) -> None:
    """识图关闭时图片只做 OCR，视觉服务不得被调用。"""

    config = AgentConfig.load_config(
        {"storage": {"base_data_dir": str(tmp_path / "runtime"), "sqlite_path": str(tmp_path / "runtime" / "db" / "attachments.db")}},
        load_env=False,
        ensure_directories=True,
        ensure_models=False,
    )
    vision = _VisionStub()
    monkeypatch.setattr(
        ImageOcrService,
        "extract_image_text",
        lambda self, source_path: ImageOcrResult(content="仅 OCR", has_text=True, engine_available=True),  # noqa: ARG005
    )
    service = SessionAttachmentService(
        config=config,
        engine=create_test_engine(f"sqlite:///{tmp_path / 'runtime' / 'db' / 'attachments.db'}"),
        create_tables=False,
        settings_service=_SettingsStub(tmp_path / "knowledge", vision_enabled=False),  # type: ignore[arg-type]
        vision_service=vision,
    )

    uploaded = service.upload_file(user_id="u1", session_id="s1", filename="ocr.png", content=_png_bytes(), mime_type="image/png")
    completed = _wait_for_processing(service, str(uploaded["attachment_id"]))
    record = service.list_session_attachments(user_id="u1", session_id="s1")[0]

    assert vision.call_count == 0
    assert completed["metadata"]["multimodal_metadata"]["vision_status"] == "disabled"
    assert "仅 OCR" in Path(record.text_path).read_text(encoding="utf-8")


def test_upload_returns_while_attachment_parser_is_still_running(tmp_path: Path, monkeypatch: object) -> None:
    """后台解析被暂停时，上传调用仍须立即返回 queued 附件。"""

    config = AgentConfig.load_config(
        {"storage": {"base_data_dir": str(tmp_path / "runtime"), "sqlite_path": str(tmp_path / "runtime" / "db" / "attachments.db")}},
        load_env=False,
        ensure_directories=True,
        ensure_models=False,
    )
    service = SessionAttachmentService(
        config=config,
        engine=create_test_engine(f"sqlite:///{tmp_path / 'runtime' / 'db' / 'attachments.db'}"),
        create_tables=False,
        settings_service=_SettingsStub(tmp_path / "knowledge"),  # type: ignore[arg-type]
    )
    parser_started = threading.Event()
    release_parser = threading.Event()
    original_parser = service._parse_to_attachment_text

    def blocked_parser(**kwargs: object):  # noqa: ANN202
        """暂停解析线程，直到上传返回断言已经完成。"""

        parser_started.set()
        release_parser.wait(timeout=2)
        return original_parser(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "_parse_to_attachment_text", blocked_parser)

    uploaded = service.upload_file(user_id="u1", session_id="s1", filename="blocked.png", content=_png_bytes(), mime_type="image/png")

    assert parser_started.wait(timeout=1)
    assert uploaded["metadata"]["processing_status"] == "queued"
    release_parser.set()


def test_attachment_uri_resolves_exact_session_file_instead_of_same_basename(tmp_path: Path) -> None:
    """不同会话的同名图片必须通过完整 URI 返回各自文件。"""

    config = AgentConfig.load_config(
        {"storage": {"base_data_dir": str(tmp_path / "runtime"), "sqlite_path": str(tmp_path / "runtime" / "db" / "attachments.db")}},
        load_env=False,
        ensure_directories=True,
        ensure_models=False,
    )
    service = SessionAttachmentService(
        config=config,
        engine=create_test_engine(f"sqlite:///{tmp_path / 'runtime' / 'db' / 'attachments.db'}"),
        create_tables=False,
        settings_service=_SettingsStub(tmp_path / "knowledge"),  # type: ignore[arg-type]
    )
    first_bytes = b"first-image"
    second_bytes = b"second-image"
    first = service.upload_file(user_id="u1", session_id="s1", filename="same.png", content=first_bytes, mime_type="image/png")
    second = service.upload_file(user_id="u1", session_id="s2", filename="same.png", content=second_bytes, mime_type="image/png")

    first_path, _, _ = service.get_attachment_file_by_uri(uri=str(first["uri"]))
    second_path, _, _ = service.get_attachment_file_by_uri(uri=str(second["uri"]))

    assert first_path.read_bytes() == first_bytes
    assert second_path.read_bytes() == second_bytes
