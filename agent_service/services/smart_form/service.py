"""
Smart form database service.

功能说明:
本服务将智能表格从前端的表格对象拆分到 SQLite 关系表,并按列/行顺序恢复为前端
表格结构。表格数据不再写入知识库 form.json,知识库仅继续保存上传附件。
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlmodel import Session, delete, select

import agent_service.models  # noqa: F401
from agent_service.core.agent_config import DEFAULT_BUSINESS_LIMITS
from agent_service.models.smart_form import (
    DEFAULT_SMART_FORM_ROW_HEIGHT,
    SmartFormCellRecord,
    SmartFormColumnRecord,
    SmartFormRecord,
    SmartFormRowRecord,
    LiteratureReadingStateRecord,
)
from agent_service.models.user_settings import UserKnowledgeLibrary

LEGACY_DEFAULT_SMART_FORM_ROW_HEIGHT = 112


class SmartFormService:
    """智能表格数据库服务。"""

    def __init__(self, *, engine: Engine, create_tables: bool = True) -> None:
        """保存数据库引擎并按需创建智能表格表。"""

        self.engine = engine

    def list_forms(self, *, user_id: str, library_id: str = "", form_kind: str = "") -> list[dict[str, Any]]:
        """列出用户智能表格。"""

        normalized_user_id = self._required(user_id, "user_id")
        with Session(self.engine) as db:
            statement = select(SmartFormRecord).where(SmartFormRecord.user_id == normalized_user_id)
            if library_id.strip():
                statement = statement.where(SmartFormRecord.library_id == library_id.strip())
            if form_kind.strip():
                statement = statement.where(SmartFormRecord.form_kind == form_kind.strip())
            records = db.exec(statement.order_by(SmartFormRecord.updated_at.desc())).all()
            return [
                {
                    "form_id": record.form_id,
                    "title": record.title,
                    "asset_dir": record.asset_dir,
                    "library_id": record.library_id,
                    "form_kind": record.form_kind,
                    "updated_at": record.updated_at,
                }
                for record in records
            ]

    def get_form(self, *, user_id: str, form_id: str) -> dict[str, Any] | None:
        """读取单张智能表格。"""

        normalized_user_id = self._required(user_id, "user_id")
        normalized_form_id = self._required(form_id, "form_id")
        with Session(self.engine) as db:
            record = db.get(SmartFormRecord, normalized_form_id)
            if record is None or record.user_id != normalized_user_id:
                return None
            return self._serialize(db=db, record=record)

    def list_literature_entries(self, *, user_id: str, library_id: str) -> list[dict[str, Any]]:
        """返回当前知识库智能文献表中的轻量行摘要，正文按卡片需要截断。"""

        normalized_user_id = self._required(user_id, "user_id")
        normalized_library_id = self._required(library_id, "library_id")
        with Session(self.engine) as db:
            library = db.get(UserKnowledgeLibrary, normalized_library_id)
            if library is None or library.user_id != normalized_user_id:
                raise ValueError("knowledge library not found")
            records = db.exec(
                select(SmartFormRecord)
                .where(SmartFormRecord.user_id == normalized_user_id)
                .where(SmartFormRecord.library_id == normalized_library_id)
                .where(SmartFormRecord.form_kind == "literature")
                .order_by(SmartFormRecord.updated_at.desc())
            ).all()
            states = db.exec(
                select(LiteratureReadingStateRecord)
                .where(LiteratureReadingStateRecord.user_id == normalized_user_id)
                .where(LiteratureReadingStateRecord.library_id == normalized_library_id)
            ).all()
            state_by_target = {(state.form_id, state.row_id): state for state in states}
            entries: list[dict[str, Any]] = []
            for record in records:
                serialized = self._serialize(db=db, record=record)
                form = serialized["form"]
                columns = form.get("columns") or []
                tag_column_ids = {
                    str(column.get("id") or "")
                    for column in columns
                    if column.get("type") in {"tag", "smart_tag"}
                }
                for row in form.get("rows") or []:
                    cells = row.get("cells") or {}
                    file_cell = cells.get("literature_file") or {}
                    asset_path = str(file_cell.get("assetPath") or "").strip()
                    file_name = str(file_cell.get("fileName") or file_cell.get("value") or "").strip()
                    if not asset_path or not file_name:
                        continue
                    state = state_by_target.get((record.form_id, str(row.get("id") or "")))
                    content = str((cells.get("literature_content") or {}).get("value") or "")
                    tags = sorted({
                        tag.strip()
                        for column_id in tag_column_ids
                        for tag in str((cells.get(column_id) or {}).get("value") or "").split(";")
                        if tag.strip()
                    })
                    entries.append({
                        "form_id": record.form_id,
                        "form_title": record.title,
                        "row_id": row.get("id"),
                        "title": str((cells.get("title") or {}).get("value") or "").strip() or file_name,
                        "file_name": file_name,
                        "asset_path": asset_path,
                        "content_excerpt": " ".join(content.split())[:240],
                        "file_size": self._asset_size(Path(library.knowledge_dir), asset_path),
                        "entered_at": row.get("createdAt"),
                        "updated_at": row.get("updatedAt"),
                        "last_viewed_at": state.last_viewed_at.isoformat() if state else "",
                        "tags": tags,
                        "rating": self._safe_int((cells.get("rating") or {}).get("value")),
                    })
            return entries

    def touch_literature_entry(self, *, user_id: str, library_id: str, form_id: str, row_id: str) -> dict[str, Any]:
        """持久化一次文献行浏览，并返回最新时间。"""

        normalized_user_id = self._required(user_id, "user_id")
        normalized_library_id = self._required(library_id, "library_id")
        normalized_form_id = self._required(form_id, "form_id")
        normalized_row_id = self._required(row_id, "row_id")
        with Session(self.engine) as db:
            record = db.get(SmartFormRecord, normalized_form_id)
            if record is None or record.user_id != normalized_user_id or record.library_id != normalized_library_id:
                raise ValueError("smart form not found")
            row_exists = db.exec(
                select(SmartFormRowRecord)
                .where(SmartFormRowRecord.form_id == normalized_form_id)
                .where(SmartFormRowRecord.row_id == normalized_row_id)
            ).first()
            if row_exists is None:
                raise ValueError("smart form row not found")
            state = db.exec(
                select(LiteratureReadingStateRecord)
                .where(LiteratureReadingStateRecord.user_id == normalized_user_id)
                .where(LiteratureReadingStateRecord.library_id == normalized_library_id)
                .where(LiteratureReadingStateRecord.form_id == normalized_form_id)
                .where(LiteratureReadingStateRecord.row_id == normalized_row_id)
            ).first()
            now = self._utc_now()
            if state is None:
                state = LiteratureReadingStateRecord(
                    state_id=f"{normalized_user_id}:{normalized_library_id}:{normalized_form_id}:{normalized_row_id}",
                    user_id=normalized_user_id,
                    library_id=normalized_library_id,
                    form_id=normalized_form_id,
                    row_id=normalized_row_id,
                )
            state.last_viewed_at = now
            db.add(state)
            db.commit()
            return {"last_viewed_at": now.isoformat()}

    def patch_literature_row(self, *, user_id: str, form_id: str, row_id: str, cells: dict[str, Any]) -> dict[str, Any]:
        """按稳定 row_id 增量更新文献单元格，并返回最新整表协议。"""

        current = self.get_form(user_id=user_id, form_id=form_id)
        if current is None:
            raise ValueError("smart form not found")
        form = current["form"]
        target = next((row for row in form.get("rows") or [] if row.get("id") == row_id), None)
        if target is None:
            raise ValueError("smart form row not found")
        target_cells = target.setdefault("cells", {})
        for column_id, value in cells.items():
            existing = dict(target_cells.get(column_id) or {})
            existing.update(value if isinstance(value, dict) else {"value": str(value)})
            target_cells[str(column_id)] = existing
        return self.save_form(
            user_id=user_id,
            form_id=form_id,
            library_id=current["library_id"],
            form_kind=current["form_kind"],
            asset_dir=current["asset_dir"],
            form=form,
        )

    def duplicate_literature_row(self, *, user_id: str, form_id: str, row_id: str) -> dict[str, Any]:
        """复制文献行及真实文件，使两个条目可独立删除。"""

        current = self.get_form(user_id=user_id, form_id=form_id)
        if current is None:
            raise ValueError("smart form not found")
        form = current["form"]
        source = next((row for row in form.get("rows") or [] if row.get("id") == row_id), None)
        if source is None:
            raise ValueError("smart form row not found")
        with Session(self.engine) as db:
            library = db.get(UserKnowledgeLibrary, current["library_id"])
            if library is None or library.user_id != user_id:
                raise ValueError("knowledge library not found")
            copied = json.loads(json.dumps(source, ensure_ascii=False))
            copied["id"] = f"row_{uuid4().hex[:12]}"
            copied.pop("createdAt", None)
            copied.pop("updatedAt", None)
            file_cell = copied.get("cells", {}).get("literature_file", {})
            asset_path = str(file_cell.get("assetPath") or "")
            if asset_path:
                source_path = self._resolve_asset_path(Path(library.knowledge_dir), asset_path)
                target_path = self._unique_copy_path(source_path)
                shutil.copy2(source_path, target_path)
                relative = target_path.relative_to(Path(library.knowledge_dir).resolve()).as_posix()
                file_cell.update({"assetPath": relative, "fileName": target_path.name, "value": target_path.name})
            form.setdefault("rows", []).append(copied)
        return self.save_form(
            user_id=user_id,
            form_id=form_id,
            library_id=current["library_id"],
            form_kind=current["form_kind"],
            asset_dir=current["asset_dir"],
            form=form,
        )

    def delete_literature_row(self, *, user_id: str, form_id: str, row_id: str, delete_file: bool) -> bool:
        """删除文献行，并在要求时以可回滚的临时重命名安全删除真实文件。"""

        current = self.get_form(user_id=user_id, form_id=form_id)
        if current is None:
            return False
        form = current["form"]
        source = next((row for row in form.get("rows") or [] if row.get("id") == row_id), None)
        if source is None:
            return False
        staged_path: Path | None = None
        original_path: Path | None = None
        if delete_file:
            asset_path = str((source.get("cells", {}).get("literature_file") or {}).get("assetPath") or "")
            if asset_path:
                with Session(self.engine) as db:
                    library = db.get(UserKnowledgeLibrary, current["library_id"])
                    if library is None or library.user_id != user_id:
                        raise ValueError("knowledge library not found")
                    original_path = self._resolve_asset_path(Path(library.knowledge_dir), asset_path)
                    if original_path.exists():
                        staged_path = original_path.with_name(f".{original_path.name}.{uuid4().hex}.deleting")
                        original_path.rename(staged_path)
        form["rows"] = [row for row in form.get("rows") or [] if row.get("id") != row_id]
        try:
            self.save_form(
                user_id=user_id,
                form_id=form_id,
                library_id=current["library_id"],
                form_kind=current["form_kind"],
                asset_dir=current["asset_dir"],
                form=form,
            )
        except Exception:
            if staged_path and original_path and staged_path.exists():
                staged_path.rename(original_path)
            raise
        if staged_path and staged_path.exists():
            staged_path.unlink()
        with Session(self.engine) as db:
            db.exec(
                delete(LiteratureReadingStateRecord)
                .where(LiteratureReadingStateRecord.form_id == form_id)
                .where(LiteratureReadingStateRecord.row_id == row_id)
            )
            db.commit()
        return True

    @staticmethod
    def _resolve_asset_path(root: Path, relative_path: str) -> Path:
        """将表格相对路径限制在所属知识库根目录内。"""

        resolved_root = root.resolve()
        resolved = (resolved_root / relative_path).resolve()
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise ValueError("asset path escapes knowledge library")
        return resolved

    @classmethod
    def _asset_size(cls, root: Path, relative_path: str) -> int:
        """读取真实文献大小；缺失文件返回零以便列表仍可呈现。"""

        try:
            path = cls._resolve_asset_path(root, relative_path)
            return path.stat().st_size if path.is_file() else 0
        except (OSError, ValueError):
            return 0

    @staticmethod
    def _unique_copy_path(source: Path) -> Path:
        """在原目录生成不覆盖现有文件的副本路径。"""

        for index in range(1, 1000):
            candidate = source.with_name(f"{source.stem} ({index}){source.suffix}")
            if not candidate.exists():
                return candidate
        return source.with_name(f"{source.stem}-{uuid4().hex[:8]}{source.suffix}")

    @staticmethod
    def _safe_int(value: Any) -> int:
        """将可选数字单元格安全转换为整数。"""

        try:
            return int(float(str(value or 0)))
        except (TypeError, ValueError):
            return 0

    def save_form(self, *, user_id: str, form: dict[str, Any], form_id: str | None = None, asset_dir: str = "", library_id: str = "", form_kind: str = "") -> dict[str, Any]:
        """创建或覆盖保存一张智能表格。"""

        normalized_user_id = self._required(user_id, "user_id")
        normalized_form = self._validate_form(form)
        normalized_form_id = (form_id or "").strip() or self._generate_form_id()
        normalized_kind = form_kind.strip() or self._form_kind(normalized_form)
        now = self._utc_now()
        with Session(self.engine) as db:
            record = db.get(SmartFormRecord, normalized_form_id)
            if record is not None and record.user_id != normalized_user_id:
                raise ValueError("form_id belongs to another user")
            resolved_library_id = library_id.strip() or (record.library_id if record else "")
            if not resolved_library_id:
                active_library = db.exec(
                    select(UserKnowledgeLibrary)
                    .where(UserKnowledgeLibrary.user_id == normalized_user_id)
                    .where(UserKnowledgeLibrary.is_active == True)  # noqa: E712
                ).first()
                resolved_library_id = active_library.library_id if active_library else ""
            if record is None:
                record = SmartFormRecord(
                    form_id=normalized_form_id,
                    user_id=normalized_user_id,
                    library_id=resolved_library_id,
                    form_kind=normalized_kind,
                    title=str(normalized_form["title"]),
                    asset_dir=asset_dir.strip(),
                    version=int(normalized_form.get("version") or 1),
                    created_at=now,
                    updated_at=now,
                )
            record.title = str(normalized_form["title"])
            record.asset_dir = asset_dir.strip()
            if resolved_library_id:
                record.library_id = resolved_library_id
            record.form_kind = normalized_kind
            record.version = int(normalized_form.get("version") or 1)
            record.updated_at = now
            db.add(record)
            self._replace_children(db=db, form_id=normalized_form_id, form=normalized_form)
            db.commit()
            db.refresh(record)
            return self._serialize(db=db, record=record)

    def delete_form(self, *, user_id: str, form_id: str) -> bool:
        """删除当前用户拥有的表格及其列、行和单元格记录。"""

        normalized_user_id = self._required(user_id, "user_id")
        normalized_form_id = self._required(form_id, "form_id")
        with Session(self.engine) as db:
            record = db.get(SmartFormRecord, normalized_form_id)
            if record is None or record.user_id != normalized_user_id:
                return False
            db.exec(delete(SmartFormCellRecord).where(SmartFormCellRecord.form_id == normalized_form_id))
            db.exec(delete(SmartFormColumnRecord).where(SmartFormColumnRecord.form_id == normalized_form_id))
            db.exec(delete(SmartFormRowRecord).where(SmartFormRowRecord.form_id == normalized_form_id))
            db.delete(record)
            db.commit()
            return True

    @staticmethod
    def _utc_now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    @staticmethod
    def _generate_form_id() -> str:
        """生成智能表格 ID。"""

        return f"sf_{uuid4().hex}"

    @staticmethod
    def _required(value: str, field_name: str) -> str:
        """校验必填字符串。"""

        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _validate_form(form: dict[str, Any]) -> dict[str, Any]:
        """校验前端表格结构的必要字段。"""

        if not isinstance(form, dict):
            raise ValueError("form must be an object")
        if not str(form.get("title") or "").strip():
            raise ValueError("form.title is required")
        if not isinstance(form.get("columns"), list):
            raise ValueError("form.columns must be a list")
        if not isinstance(form.get("rows"), list):
            raise ValueError("form.rows must be a list")
        return form

    def _replace_children(self, *, db: Session, form_id: str, form: dict[str, Any]) -> None:
        """用前端当前表格状态替换列、行、单元格子表。"""

        existing_rows = {
            row.row_id: row
            for row in db.exec(select(SmartFormRowRecord).where(SmartFormRowRecord.form_id == form_id)).all()
        }
        db.exec(delete(SmartFormCellRecord).where(SmartFormCellRecord.form_id == form_id))
        db.exec(delete(SmartFormColumnRecord).where(SmartFormColumnRecord.form_id == form_id))
        db.exec(delete(SmartFormRowRecord).where(SmartFormRowRecord.form_id == form_id))
        columns = form.get("columns") if isinstance(form.get("columns"), list) else []
        rows = form.get("rows") if isinstance(form.get("rows"), list) else []
        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                continue
            column_id = str(column.get("id") or "").strip()
            if not column_id:
                continue
            db.add(SmartFormColumnRecord(
                column_record_id=self._column_record_id(form_id, column_id),
                form_id=form_id,
                column_id=column_id,
                order_index=index,
                title=str(column.get("title") or column_id),
                description=str(column.get("description") or ""),
                column_type=str(column.get("type") or "text"),
                removable=bool(column.get("removable", True)),
                editable=bool(column.get("editable", True)),
                width=int(column.get("width") or 160),
                options_json=json.dumps(column.get("options") or [], ensure_ascii=False),
                tone=str(column.get("tone") or ""),
            ))
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            row_height = int(row.get("height") or DEFAULT_SMART_FORM_ROW_HEIGHT)
            if row_height == LEGACY_DEFAULT_SMART_FORM_ROW_HEIGHT:
                row_height = DEFAULT_SMART_FORM_ROW_HEIGHT
            existing_row = existing_rows.get(row_id)
            now = self._utc_now()
            db.add(SmartFormRowRecord(
                row_record_id=self._row_record_id(form_id, row_id),
                form_id=form_id,
                row_id=row_id,
                order_index=row_index,
                height=max(DEFAULT_BUSINESS_LIMITS.smart_form_min_row_height, row_height),
                created_at=existing_row.created_at if existing_row and existing_row.created_at else now,
                updated_at=now,
            ))
            cells = row.get("cells") if isinstance(row.get("cells"), dict) else {}
            for column_id, cell in cells.items():
                if not isinstance(cell, dict):
                    continue
                db.add(SmartFormCellRecord(
                    cell_record_id=self._cell_record_id(form_id, row_id, str(column_id)),
                    form_id=form_id,
                    row_id=row_id,
                    column_id=str(column_id),
                    value=str(cell.get("value") or ""),
                    status=str(cell.get("status") or ""),
                    asset_path=str(cell.get("assetPath") or ""),
                    file_name=str(cell.get("fileName") or ""),
                ))

    def _serialize(self, *, db: Session, record: SmartFormRecord) -> dict[str, Any]:
        """将关系表记录组装回前端表格结构。"""

        columns = db.exec(
            select(SmartFormColumnRecord)
            .where(SmartFormColumnRecord.form_id == record.form_id)
            .order_by(SmartFormColumnRecord.order_index)
        ).all()
        rows = db.exec(
            select(SmartFormRowRecord)
            .where(SmartFormRowRecord.form_id == record.form_id)
            .order_by(SmartFormRowRecord.order_index)
        ).all()
        cells = db.exec(
            select(SmartFormCellRecord).where(SmartFormCellRecord.form_id == record.form_id)
        ).all()
        cells_by_row: dict[str, dict[str, Any]] = {}
        for cell in cells:
            payload: dict[str, Any] = {"value": cell.value}
            if cell.status:
                payload["status"] = cell.status
            if cell.asset_path:
                payload["assetPath"] = cell.asset_path
            if cell.file_name:
                payload["fileName"] = cell.file_name
            cells_by_row.setdefault(cell.row_id, {})[cell.column_id] = payload
        form = {
            "version": record.version,
            "title": record.title,
            "updatedAt": record.updated_at.isoformat(),
            "columns": [self._serialize_column(column) for column in columns],
            "rows": [{"id": row.row_id, "height": row.height, "createdAt": row.created_at.isoformat(), "updatedAt": row.updated_at.isoformat(), "cells": cells_by_row.get(row.row_id, {})} for row in rows],
        }
        return {
            "form_id": record.form_id,
            "user_id": record.user_id,
            "asset_dir": record.asset_dir,
            "library_id": record.library_id,
            "form_kind": record.form_kind,
            "form": form,
            "updated_at": record.updated_at,
        }

    @staticmethod
    def _serialize_column(record: SmartFormColumnRecord) -> dict[str, Any]:
        """序列化列定义。"""

        try:
            options = json.loads(record.options_json) if record.options_json else []
        except json.JSONDecodeError:
            options = []
        payload: dict[str, Any] = {
            "id": record.column_id,
            "title": record.title,
            "type": record.column_type,
            "removable": record.removable,
            "editable": record.editable,
            "width": record.width,
        }
        if options:
            payload["options"] = options
        if record.description:
            payload["description"] = record.description
        if record.tone:
            payload["tone"] = record.tone
        return payload

    @staticmethod
    def _form_kind(form: dict[str, Any]) -> str:
        """根据正式文献源列兼容判断旧客户端创建的表格类型。"""

        column_ids = {str(column.get("id") or "") for column in form.get("columns") or [] if isinstance(column, dict)}
        return "literature" if {"literature_file", "literature_content"}.issubset(column_ids) else "plain"

    @staticmethod
    def _column_record_id(form_id: str, column_id: str) -> str:
        """生成列记录主键。"""

        return f"{form_id}:col:{column_id}"

    @staticmethod
    def _row_record_id(form_id: str, row_id: str) -> str:
        """生成行记录主键。"""

        return f"{form_id}:row:{row_id}"

    @staticmethod
    def _cell_record_id(form_id: str, row_id: str, column_id: str) -> str:
        """生成单元格记录主键。"""

        return f"{form_id}:cell:{row_id}:{column_id}"
