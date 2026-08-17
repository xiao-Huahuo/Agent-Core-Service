"""
Smart form database service.

功能说明:
本服务将智能表格从前端的表格对象拆分到 SQLite 关系表,并按列/行顺序恢复为前端
表格结构。表格数据不再写入知识库 form.json,知识库仅继续保存上传附件。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, delete, select

import agent_service.models  # noqa: F401
from agent_service.models.smart_form import (
    DEFAULT_SMART_FORM_ROW_HEIGHT,
    SmartFormCellRecord,
    SmartFormColumnRecord,
    SmartFormRecord,
    SmartFormRowRecord,
)

LEGACY_DEFAULT_SMART_FORM_ROW_HEIGHT = 112


class SmartFormService:
    """智能表格数据库服务。"""

    def __init__(self, *, engine: Engine, create_tables: bool = True) -> None:
        """保存数据库引擎并按需创建智能表格表。"""

        self.engine = engine
        if create_tables:
            SQLModel.metadata.create_all(self.engine)
            self._ensure_row_height_column()

    def _ensure_row_height_column(self) -> None:
        """为旧数据库补充行高列,保持现有智能表格可原地升级。"""

        columns = {column["name"] for column in inspect(self.engine).get_columns("smart_form_rows")}
        if "height" in columns:
            return
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE smart_form_rows ADD COLUMN height INTEGER NOT NULL DEFAULT 282"))

    def list_forms(self, *, user_id: str) -> list[dict[str, Any]]:
        """列出用户智能表格。"""

        normalized_user_id = self._required(user_id, "user_id")
        with Session(self.engine) as db:
            records = db.exec(
                select(SmartFormRecord)
                .where(SmartFormRecord.user_id == normalized_user_id)
                .order_by(SmartFormRecord.updated_at.desc())
            ).all()
            return [
                {
                    "form_id": record.form_id,
                    "title": record.title,
                    "asset_dir": record.asset_dir,
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

    def save_form(self, *, user_id: str, form: dict[str, Any], form_id: str | None = None, asset_dir: str = "") -> dict[str, Any]:
        """创建或覆盖保存一张智能表格。"""

        normalized_user_id = self._required(user_id, "user_id")
        normalized_form = self._validate_form(form)
        normalized_form_id = (form_id or "").strip() or self._generate_form_id()
        now = self._utc_now()
        with Session(self.engine) as db:
            record = db.get(SmartFormRecord, normalized_form_id)
            if record is not None and record.user_id != normalized_user_id:
                raise ValueError("form_id belongs to another user")
            if record is None:
                record = SmartFormRecord(
                    form_id=normalized_form_id,
                    user_id=normalized_user_id,
                    title=str(normalized_form["title"]),
                    asset_dir=asset_dir.strip(),
                    version=int(normalized_form.get("version") or 1),
                    created_at=now,
                    updated_at=now,
                )
            record.title = str(normalized_form["title"])
            record.asset_dir = asset_dir.strip()
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
            db.add(SmartFormRowRecord(
                row_record_id=self._row_record_id(form_id, row_id),
                form_id=form_id,
                row_id=row_id,
                order_index=row_index,
                height=max(56, row_height),
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
            "rows": [{"id": row.row_id, "height": row.height, "cells": cells_by_row.get(row.row_id, {})} for row in rows],
        }
        return {
            "form_id": record.form_id,
            "user_id": record.user_id,
            "asset_dir": record.asset_dir,
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
        if record.tone:
            payload["tone"] = record.tone
        return payload

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
