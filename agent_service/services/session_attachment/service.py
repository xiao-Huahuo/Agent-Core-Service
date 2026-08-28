"""Session attachment upload, parsing, and context injection service."""

from __future__ import annotations

import json
import hashlib
import mimetypes
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import AgentConfig
from agent_service.core.db.engine import get_database_engine
from agent_service.models.attachment import SessionAttachmentRecord
from agent_service.services.memory.rag.frontmatter_bootstrap import FrontmatterBootstrapService
from agent_service.services.memory.rag.frontmatter_document import StructuredKnowledgeDocument, StructuredKnowledgeSection
from agent_service.services.settings.service import SettingsService


@dataclass(slots=True)
class AttachmentContext:
    """Prepared context text and citation metadata for session attachments."""

    content: str
    citation_map: dict[str, dict[str, str]]
    attachment_count: int
    injected_count: int


class ImageUnderstandingService(Protocol):
    """附件服务使用的最小本地图像理解接口。"""

    def understand_image(self, *, image_path: Path, ocr_text: str, prompt: str = "") -> str:
        """结合原图与 OCR 文本返回视觉语义。"""

        ...


class SessionAttachmentService:
    """Manage uploaded files that are available to the current Agent session only."""

    REFERENCE_HINT_PATTERN = re.compile(
        r"(\u9644\u4ef6|\u4e0a\u4f20|\u4e0a\u50b3|\u6587\u4ef6|\u6587\u6863|\u6587\u6a94|\u8fd9\u4e2a|\u9019\u500b|\u8fd9\u4e9b|\u9019\u4e9b|\u521a\u624d|\u525b\u624d|\u521a\u521a|\u525b\u525b|"
        r"attachment|attachments|uploaded|upload|file|files|document|documents)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        config: AgentConfig,
        settings_service: SettingsService,
        vision_service: ImageUnderstandingService | None = None,
        engine: Engine | None = None,
        create_tables: bool = True,
    ) -> None:
        self.config = config
        self.settings_service = settings_service
        self.vision_service = vision_service
        self.engine = engine or get_database_engine(config)

    def upload_file(
        self,
        *,
        user_id: str,
        session_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "",
    ) -> dict[str, object]:
        """Save an uploaded file, parse it with the shared document parser, and record it."""

        normalized_user_id = user_id.strip()
        normalized_session_id = session_id.strip()
        safe_filename = Path(filename).name.strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")
        if not normalized_session_id:
            raise ValueError("session_id is required")
        if not safe_filename:
            raise ValueError("filename is required")

        active_library = self.settings_service.get_active_knowledge_library(user_id=normalized_user_id)
        library_id = str(active_library["library_id"])
        library_name = str(active_library.get("name") or library_id)
        upload_dir = self._upload_dir(
            user_id=normalized_user_id,
            library=library_id,
            session_id=normalized_session_id,
        )
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._unique_child_path(target_dir=upload_dir, preferred_name=safe_filename)
        target_path.write_bytes(content)

        attachment_id = f"att_{uuid4().hex}"
        text_path, document = self._parse_to_attachment_text(
            attachment_id=attachment_id,
            source_path=target_path,
            upload_dir=upload_dir,
            user_id=normalized_user_id,
        )
        record = SessionAttachmentRecord(
            attachment_id=attachment_id,
            user_id=normalized_user_id,
            session_id=normalized_session_id,
            library_id=library_id,
            library_name=library_name,
            filename=safe_filename,
            stored_name=target_path.name,
            path=str(target_path),
            text_path=str(text_path),
            uri=self._attachment_uri(
                user_id=normalized_user_id,
                library=library_id,
                session_id=normalized_session_id,
                filename=target_path.name,
            ),
            mime_type=mime_type or mimetypes.guess_type(target_path.name)[0] or "",
            size=len(content),
            source_type=document.source_type,
            summary=document.summary,
            metadata_json={
                "title": document.title,
                "source_hash": document.source_hash,
                "section_count": len(document.sections),
                "parser": "FrontmatterBootstrapService",
                "multimodal_metadata": document.metadata,
            },
        )
        with Session(self.engine) as db_session:
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
        return self._record_to_dict(record)

    def list_session_attachments(self, *, user_id: str, session_id: str) -> list[SessionAttachmentRecord]:
        """Return attachments for a user session in upload order."""

        statement = (
            select(SessionAttachmentRecord)
            .where(SessionAttachmentRecord.user_id == user_id)
            .where(SessionAttachmentRecord.session_id == session_id)
            .order_by(SessionAttachmentRecord.created_at.asc())
        )
        with Session(self.engine) as db_session:
            return list(db_session.exec(statement).all())

    def delete_attachment(self, *, user_id: str, session_id: str, attachment_id: str) -> bool:
        """Delete one session attachment record and its runtime files."""

        normalized_user_id = user_id.strip()
        normalized_session_id = session_id.strip()
        normalized_attachment_id = attachment_id.strip()
        if not normalized_user_id or not normalized_session_id or not normalized_attachment_id:
            raise ValueError("user_id, session_id and attachment_id are required")
        with Session(self.engine) as db_session:
            record = db_session.get(SessionAttachmentRecord, normalized_attachment_id)
            if record is None:
                return False
            if record.user_id != normalized_user_id or record.session_id != normalized_session_id:
                return False
            self._delete_runtime_file(record.path)
            self._delete_runtime_file(record.text_path)
            db_session.delete(record)
            db_session.commit()
            return True

    def build_context(
        self,
        *,
        user_id: str,
        session_id: str,
        current_prompt: str,
        max_total_chars: int | None = None,
        max_attachment_chars: int | None = None,
    ) -> AttachmentContext:
        """Build session attachment catalog and relevant content snippets for the model."""

        max_total_chars = max_total_chars or self.config.limits.attachment_context_max_chars
        max_attachment_chars = max_attachment_chars or self.config.limits.attachment_single_max_chars
        attachments = self.list_session_attachments(user_id=user_id, session_id=session_id)
        if not attachments:
            return AttachmentContext(content="", citation_map={}, attachment_count=0, injected_count=0)

        selected = self._select_relevant_attachments(attachments=attachments, current_prompt=current_prompt)
        citation_map: dict[str, dict[str, str]] = {}
        lines = [
            "--- Session Uploaded Attachments Start ---",
            "The user uploaded these files directly into this session. They are NOT knowledge-base files and must not be ingested.",
            "You can read and use the extracted attachment content below. Do not claim that you cannot open or read these uploads.",
            "Attachment catalog:",
        ]
        selected_ids = {item.attachment_id for item in selected}
        for index, item in enumerate(attachments, 1):
            marker = " (content injected below)" if item.attachment_id in selected_ids else ""
            lines.append(f"- [A{index}] {item.filename} | {item.size} bytes | {item.source_type}{marker}")
            citation_map[f"A{index}"] = {
                "source_uri": item.uri or item.path,
                "content": item.summary or self._read_text_preview(
                    item.text_path,
                    self.config.limits.attachment_preview_chars,
                ),
                "title": item.filename,
                "source": "session_attachment",
            }

        remaining = max_total_chars - sum(len(line) + 1 for line in lines)
        injected_count = 0
        if selected and remaining > 0:
            lines.append("Relevant attachment content:")
        for item in selected:
            if remaining <= 0:
                break
            attachment_index = attachments.index(item) + 1
            text = self._read_text_preview(item.text_path, min(max_attachment_chars, remaining))
            if not text:
                continue
            block = f"### [A{attachment_index}] {item.filename}\n{text}"
            lines.append(block)
            remaining -= len(block) + 1
            injected_count += 1
        lines.append("--- Session Uploaded Attachments End ---")
        return AttachmentContext(
            content="\n".join(lines),
            citation_map=citation_map,
            attachment_count=len(attachments),
            injected_count=injected_count,
        )

    def _parse_to_attachment_text(
        self,
        *,
        attachment_id: str,
        source_path: Path,
        upload_dir: Path,
        user_id: str,
    ) -> tuple[Path, StructuredKnowledgeDocument]:
        suffixes = set(self.config.constants.knowledge_supported_suffixes)
        frontmatter_dir = upload_dir / ".attachments" / "frontmatter"
        text_dir = upload_dir / ".attachments" / "text"
        text_dir.mkdir(parents=True, exist_ok=True)
        is_direct_image = source_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        ocr_enabled = is_direct_image or self.settings_service.is_ocr_enabled_for_user(user_id=user_id)
        frontmatter_path: Path | None = None
        try:
            _, frontmatter_path = FrontmatterBootstrapService(
                config=self.config,
                ocr_enabled=ocr_enabled,
            ).build_frontmatter_file(
                source_path=source_path,
                knowledge_dir=upload_dir,
                frontmatter_dir=frontmatter_dir,
                supported_suffixes=suffixes,
            )
            payload = json.loads(frontmatter_path.read_text(encoding="utf-8"))
            document = StructuredKnowledgeDocument.from_dict(payload)
        except ValueError:
            document = self._build_fallback_document(source_path=source_path, upload_dir=upload_dir)
        if is_direct_image:
            self._append_image_understanding(document=document, source_path=source_path)
            if frontmatter_path is not None:
                frontmatter_path.write_text(
                    json.dumps(document.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        text_path = text_dir / f"{attachment_id}.txt"
        text_path.write_text(self._document_to_text(document), encoding="utf-8")
        return text_path, document

    def _append_image_understanding(
        self,
        *,
        document: StructuredKnowledgeDocument,
        source_path: Path,
    ) -> None:
        """在 OCR 之后调用本地模型，并把互补视觉描述追加到附件正文。"""

        if self.vision_service is None:
            document.metadata["vision_status"] = "unavailable"
            return
        ocr_text = self._document_to_text(document)
        try:
            description = self.vision_service.understand_image(
                image_path=source_path,
                ocr_text=ocr_text,
            ).strip()
        except Exception as exc:
            document.metadata["vision_status"] = "error"
            document.metadata["vision_error"] = type(exc).__name__
            return
        if not description:
            document.metadata["vision_status"] = "empty"
            return
        document.sections.append(
            StructuredKnowledgeSection(
                section_id="vision-understanding",
                heading="视觉理解",
                title_path=[document.title, "视觉理解"],
                content=description,
                start_char=0,
                end_char=len(description),
            )
        )
        document.metadata["vision_status"] = "completed"
        document.metadata["vision_model"] = self.config.model.local_model_name

    def _build_fallback_document(self, *, source_path: Path, upload_dir: Path) -> StructuredKnowledgeDocument:
        """Build a lightweight attachment document for unsupported suffixes."""

        raw_bytes = source_path.read_bytes()
        source_hash = hashlib.sha256(raw_bytes).hexdigest()
        try:
            body = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            body = source_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            body = f"Binary or unsupported file: {source_path.name}"
        if not body.strip():
            body = f"Empty or unsupported file: {source_path.name}"
        relative_path = source_path.relative_to(upload_dir).as_posix()
        return StructuredKnowledgeDocument(
            document_id=hashlib.sha1(relative_path.encode("utf-8")).hexdigest(),
            source_type="attachment",
            source_path=str(source_path),
            source_uri=str(source_path),
            source_hash=source_hash,
            title=source_path.name,
            summary="",
            tags=[],
            authority=0.5,
            valid_from=None,
            valid_until=None,
            metadata={
                "file_suffix": source_path.suffix.lower(),
                "relative_path": relative_path,
                "modality": "unsupported",
            },
            sections=[
                StructuredKnowledgeSection(
                    section_id="fallback",
                    heading=source_path.name,
                    title_path=[source_path.name],
                    content=body,
                    start_char=0,
                    end_char=len(body),
                )
            ],
        )

    @staticmethod
    def _document_to_text(document: StructuredKnowledgeDocument) -> str:
        lines = [f"# {document.title}".strip()]
        if document.summary:
            lines.extend(["", document.summary.strip()])
        for section in document.sections:
            title_path = " / ".join(section.title_path) or section.heading
            content = section.content.strip()
            if not content:
                continue
            lines.extend(["", f"## {title_path}", content])
        return "\n".join(lines).strip()

    def _select_relevant_attachments(
        self,
        *,
        attachments: list[SessionAttachmentRecord],
        current_prompt: str,
    ) -> list[SessionAttachmentRecord]:
        prompt = current_prompt.casefold()
        selected = [
            item
            for item in attachments
            if item.filename.casefold() in prompt or Path(item.filename).stem.casefold() in prompt
        ]
        if selected:
            return selected
        if self.REFERENCE_HINT_PATTERN.search(current_prompt):
            return attachments
        if len(attachments) == 1:
            return attachments
        return []

    def _attachment_uri(self, *, user_id: str, library: str, session_id: str, filename: str) -> str:
        return (
            "session-upload://"
            f"{self._safe_component(user_id)}/{self._safe_component(library)}/"
            f"{self._safe_component(session_id)}/{filename}"
        )

    def _upload_dir(self, *, user_id: str, library: str, session_id: str) -> Path:
        return (
            self.config.storage.base_data_dir
            / "uploads"
            / self._safe_component(user_id)
            / self._safe_component(library)
            / self._safe_component(session_id)
        )

    @staticmethod
    def _safe_component(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "default"

    @classmethod
    def _unique_child_path(cls, *, target_dir: Path, preferred_name: str) -> Path:
        safe_name = Path(preferred_name).name.strip() or "untitled"
        first_path = (target_dir / safe_name).resolve()
        if not first_path.exists():
            return first_path
        stem = first_path.stem
        suffix = first_path.suffix
        for index in range(1, self.config.limits.attachment_name_collision_attempts):
            candidate = (target_dir / f"{stem} ({index}){suffix}").resolve()
            if not candidate.exists():
                return candidate
        return (target_dir / f"{stem} ({int(time.time())}){suffix}").resolve()

    @staticmethod
    def _read_text_preview(text_path: str, limit: int) -> str:
        if not text_path:
            return ""
        path = Path(text_path)
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "\n...(已截断)"

    def _delete_runtime_file(self, path_value: str) -> None:
        if not path_value:
            return
        path = Path(path_value).expanduser().resolve()
        uploads_root = (self.config.storage.base_data_dir / "uploads").resolve()
        try:
            path.relative_to(uploads_root)
        except ValueError:
            return
        if path.is_file():
            path.unlink(missing_ok=True)

    @staticmethod
    def _record_to_dict(record: SessionAttachmentRecord) -> dict[str, object]:
        return {
            "attachment_id": record.attachment_id,
            "user_id": record.user_id,
            "session_id": record.session_id,
            "library_id": record.library_id,
            "library_name": record.library_name,
            "filename": record.filename,
            "stored_name": record.stored_name,
            "uri": record.uri,
            "mime_type": record.mime_type,
            "size": record.size,
            "source_type": record.source_type,
            "summary": record.summary,
            "metadata": record.metadata_json,
            "created_at": record.created_at.isoformat(),
        }
