"""智能表格 Agent 工具。

使用说明:
工具复用 ``SmartFormService`` 的关系型持久化，并与前端保持相同的 smart/plain
两种初始表格结构。智能填充复用 ``StructuredGenerationService``，预览工具只列出
即将修改的单元格，不调用模型也不写数据库。
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from agent_service.schemas.structured_generation import (
    StructuredGenerationField,
    StructuredGenerationOptions,
    StructuredGenerationRequest,
    StructuredGenerationSource,
)
from agent_service.tools.runtime_context import AGENT_ACCESS_READONLY, get_tool_runtime

DEFAULT_ROW_HEIGHT = 282


def _smart_form_service() -> Any:
    """延迟读取智能表格服务，避免 AgentCore 导入环。"""

    from agent_service.api.rest.deps import _require_smart_form_service

    return _require_smart_form_service()


def _generation_service() -> Any:
    """延迟读取结构化字段生成服务。"""

    from agent_service.api.rest.deps import _require_structured_generation_service

    return _require_structured_generation_service()


def _json(payload: Any) -> str:
    """返回保留中文的格式化 JSON。"""

    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _write_runtime(action: str) -> Any:
    """校验智能表格写操作权限。"""

    runtime = get_tool_runtime()
    if runtime.agent_access_mode == AGENT_ACCESS_READONLY:
        raise PermissionError(f"当前 Agent 为只读模式，不能{action}")
    return runtime


def _now() -> str:
    """返回表格协议使用的 UTC ISO 时间。"""

    return datetime.now(timezone.utc).isoformat()


def _new_row(columns: list[dict[str, Any]]) -> dict[str, Any]:
    """按列定义创建一个与前端兼容的空行。"""

    cells: dict[str, dict[str, Any]] = {}
    for column in columns:
        column_id = str(column["id"])
        cell: dict[str, Any] = {"value": ""}
        if column.get("type") in {"smart_text", "smart_tag"}:
            cell["status"] = "idle"
        cells[column_id] = cell
    return {"id": f"row_{uuid.uuid4().hex[:12]}", "height": DEFAULT_ROW_HEIGHT, "cells": cells}


def _default_form(title: str, kind: str) -> dict[str, Any]:
    """创建与 SmartFormsView 相同的智能文献表或普通表模板。"""

    normalized_kind = str(kind or "smart").strip().casefold()
    if normalized_kind not in {"smart", "plain"}:
        raise ValueError("kind must be smart or plain")
    columns: list[dict[str, Any]] = [
        {"id": "row_index", "title": "序号", "type": "index", "removable": False, "editable": False, "width": 64},
        {"id": "literature_file", "title": "文献上传", "type": "file", "removable": True, "editable": False, "width": 168},
        {"id": "literature_content", "title": "文献内容", "type": "readonly_text", "removable": True, "editable": False, "width": 240},
        {"id": "title", "title": "标题", "type": "smart_text", "removable": False, "editable": True, "width": 230, "tone": "blue"},
    ]
    if normalized_kind == "plain":
        columns = [column for column in columns if column["id"] not in {"literature_file", "literature_content"}]
        columns = [
            {**column, "type": "text"} if column["type"] == "smart_text" else column
            for column in columns
        ]
        for column in columns:
            column.pop("tone", None)
    return {
        "version": 1,
        "title": title.strip(),
        "updatedAt": _now(),
        "columns": columns,
        "rows": [_new_row(columns)],
    }


def _get_form_or_raise(form_id: str) -> dict[str, Any]:
    """读取当前用户表格并统一处理不存在情况。"""

    result = _smart_form_service().get_form(user_id=get_tool_runtime().user_id, form_id=form_id)
    if result is None:
        raise ValueError("smart form not found")
    return result


def list_smart_forms(query: str = "") -> str:
    """按标题关键词列出当前用户的智能表格。"""

    forms = _smart_form_service().list_forms(user_id=get_tool_runtime().user_id)
    normalized = query.strip().casefold()
    if normalized:
        forms = [item for item in forms if normalized in str(item.get("title") or "").casefold()]
    return _json(forms)


def create_smart_form(title: str, kind: str = "smart") -> str:
    """创建 smart 智能文献表或 plain 普通表。"""

    runtime = _write_runtime("创建智能表格")
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("title is required")
    slug = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "-", normalized_title).strip("-")[:64] or "table"
    asset_dir = f".mw/forms/{slug}-{uuid.uuid4().hex[:8]}"
    result = _smart_form_service().save_form(
        user_id=runtime.user_id,
        form=_default_form(normalized_title, kind),
        asset_dir=asset_dir,
    )
    return _json(result)


def get_smart_form(form_id: str) -> str:
    """读取一张智能表格的列、行和单元格。"""

    return _json(_get_form_or_raise(form_id))


def get_smart_form_schema(form_id: str) -> str:
    """仅读取表格列定义和基本信息，不返回大体量行数据。"""

    result = _get_form_or_raise(form_id)
    form = dict(result["form"])
    return _json({
        "form_id": result["form_id"],
        "title": form.get("title"),
        "version": form.get("version"),
        "asset_dir": result.get("asset_dir"),
        "columns": form.get("columns") or [],
        "row_count": len(form.get("rows") or []),
    })


def update_smart_form(form_id: str, form: dict[str, Any]) -> str:
    """使用完整表格结构更新指定智能表格。"""

    runtime = _write_runtime("更新智能表格")
    current = _get_form_or_raise(form_id)
    next_form = dict(form)
    next_form["updatedAt"] = _now()
    return _json(
        _smart_form_service().save_form(
            user_id=runtime.user_id,
            form_id=form_id,
            asset_dir=str(current.get("asset_dir") or ""),
            form=next_form,
        )
    )


def patch_smart_form_rows(
    form_id: str,
    updates: list[dict[str, Any]] | None = None,
    add_rows: list[dict[str, Any]] | None = None,
    delete_row_ids: list[str] | None = None,
) -> str:
    """按 row_id 增量修改、增加或删除表格行。"""

    runtime = _write_runtime("编辑智能表格行")
    current = _get_form_or_raise(form_id)
    form = dict(current["form"])
    columns = [dict(column) for column in form.get("columns") or []]
    rows = [dict(row) for row in form.get("rows") or []]
    by_id = {str(row.get("id") or ""): row for row in rows}
    deleted = {str(row_id) for row_id in delete_row_ids or []}
    rows = [row for row in rows if str(row.get("id") or "") not in deleted]
    for update in updates or []:
        row_id = str(update.get("row_id") or "")
        row = by_id.get(row_id)
        if row is None or row_id in deleted:
            raise ValueError(f"smart form row not found: {row_id}")
        cells = dict(row.get("cells") or {})
        for column_id, value in dict(update.get("cells") or {}).items():
            existing = dict(cells.get(column_id) or {})
            existing.update(value if isinstance(value, dict) else {"value": str(value)})
            cells[str(column_id)] = existing
        row["cells"] = cells
        if "height" in update:
            row["height"] = max(56, int(update["height"]))
    for raw_row in add_rows or []:
        row = _new_row(columns)
        supplied_id = str(raw_row.get("id") or "").strip()
        if supplied_id:
            row["id"] = supplied_id
        supplied_cells = dict(raw_row.get("cells") or {})
        for column_id, value in supplied_cells.items():
            row["cells"][str(column_id)] = value if isinstance(value, dict) else {"value": str(value)}
        rows.append(row)
    form["rows"] = rows
    form["updatedAt"] = _now()
    result = _smart_form_service().save_form(
        user_id=runtime.user_id,
        form_id=form_id,
        asset_dir=str(current.get("asset_dir") or ""),
        form=form,
    )
    return _json(result)


def get_smart_form_literature(form_id: str, row_ids: list[str] | None = None) -> str:
    """读取表项关联的文献路径、文件名及已抽取文献内容。"""

    current = _get_form_or_raise(form_id)
    requested = {str(row_id) for row_id in row_ids or []}
    literature: list[dict[str, Any]] = []
    for row in current["form"].get("rows") or []:
        row_id = str(row.get("id") or "")
        if requested and row_id not in requested:
            continue
        cells = dict(row.get("cells") or {})
        file_cell = dict(cells.get("literature_file") or {})
        content_cell = dict(cells.get("literature_content") or {})
        literature.append({
            "row_id": row_id,
            "file_name": file_cell.get("fileName") or file_cell.get("value") or "",
            "asset_path": file_cell.get("assetPath") or "",
            "content": content_cell.get("value") or "",
            "status": content_cell.get("status") or "",
        })
    return _json({"form_id": form_id, "literature": literature})


def _export_csv(form: dict[str, Any]) -> str:
    """把表格导出为 RFC 4180 兼容 CSV。"""

    columns = [column for column in form.get("columns") or [] if column.get("type") != "file"]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([column.get("title") or column.get("id") for column in columns])
    for index, row in enumerate(form.get("rows") or [], 1):
        cells = dict(row.get("cells") or {})
        writer.writerow([
            str(index) if column.get("type") == "index" else str(dict(cells.get(column.get("id")) or {}).get("value") or "")
            for column in columns
        ])
    return output.getvalue()


def _export_markdown(form: dict[str, Any]) -> str:
    """把表格导出为 Markdown 表格。"""

    columns = [column for column in form.get("columns") or [] if column.get("type") != "file"]
    escape = lambda value: re.sub(r"\s+", " ", str(value or "")).replace("|", "\\|").strip()
    lines = [
        "| " + " | ".join(escape(column.get("title") or column.get("id")) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for index, row in enumerate(form.get("rows") or [], 1):
        cells = dict(row.get("cells") or {})
        values = [
            str(index) if column.get("type") == "index" else dict(cells.get(column.get("id")) or {}).get("value") or ""
            for column in columns
        ]
        lines.append("| " + " | ".join(escape(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def export_smart_form(form_id: str, format: str = "csv") -> str:
    """将表格导出为 csv、markdown 或 json，并返回文件名和完整内容。"""

    current = _get_form_or_raise(form_id)
    form = dict(current["form"])
    normalized = format.strip().casefold()
    if normalized == "csv":
        content = _export_csv(form)
        suffix = "csv"
    elif normalized in {"markdown", "md"}:
        content = _export_markdown(form)
        suffix = "md"
    elif normalized == "json":
        content = _json(form)
        suffix = "json"
    else:
        raise ValueError("format must be csv, markdown, or json")
    return _json({"form_id": form_id, "filename": f"{form.get('title') or form_id}.{suffix}", "format": normalized, "content": content})


def _plain_form_from_csv(title: str, content: str) -> dict[str, Any]:
    """把 CSV 首行转换为普通表列，其余记录转换为行。"""

    records = list(csv.reader(io.StringIO(content)))
    if not records or not records[0]:
        raise ValueError("CSV is empty")
    columns = [
        {"id": f"col_{index + 1}", "title": cell.strip() or f"列 {index + 1}", "type": "text", "removable": True, "editable": True, "width": 180}
        for index, cell in enumerate(records[0])
    ]
    rows: list[dict[str, Any]] = []
    for record in records[1:]:
        row = _new_row(columns)
        for index, column in enumerate(columns):
            row["cells"][column["id"]]["value"] = record[index] if index < len(record) else ""
        rows.append(row)
    return {"version": 1, "title": title, "updatedAt": _now(), "columns": columns, "rows": rows or [_new_row(columns)]}


def import_smart_form(content: str, format: str = "json", title: str = "") -> str:
    """从 JSON 或 CSV 内容导入并创建新表格。"""

    runtime = _write_runtime("导入智能表格")
    normalized = format.strip().casefold()
    if normalized == "json":
        form = json.loads(content)
        if not isinstance(form, dict):
            raise ValueError("JSON form root must be an object")
        if title.strip():
            form["title"] = title.strip()
        elif not str(form.get("title") or "").strip():
            form["title"] = "导入表格"
    elif normalized == "csv":
        form = _plain_form_from_csv(title.strip() or "导入表格", content)
    else:
        raise ValueError("format must be json or csv")
    form["updatedAt"] = _now()
    result = _smart_form_service().save_form(
        user_id=runtime.user_id,
        form=form,
        asset_dir=f".mw/forms/import-{uuid.uuid4().hex[:8]}",
    )
    return _json(result)


def _fill_targets(form: dict[str, Any], row_ids: list[str] | None, column_ids: list[str] | None) -> list[dict[str, Any]]:
    """解析可执行智能填充的行、列和文献上下文。"""

    requested_rows = {str(row_id) for row_id in row_ids or []}
    requested_columns = {str(column_id) for column_id in column_ids or []}
    columns = [
        column
        for column in form.get("columns") or []
        if column.get("type") in {"smart_text", "smart_tag"}
        and (not requested_columns or str(column.get("id")) in requested_columns)
    ]
    targets: list[dict[str, Any]] = []
    for row in form.get("rows") or []:
        row_id = str(row.get("id") or "")
        if requested_rows and row_id not in requested_rows:
            continue
        cells = dict(row.get("cells") or {})
        content = str(dict(cells.get("literature_content") or {}).get("value") or "").strip()
        for column in columns:
            targets.append({"row_id": row_id, "column": column, "content": content})
    return targets


def preview_smart_form_fill(
    form_id: str,
    row_ids: list[str] | None = None,
    column_ids: list[str] | None = None,
) -> str:
    """预览智能填充影响的单元格和缺失文献上下文，不调用模型。"""

    current = _get_form_or_raise(form_id)
    targets = _fill_targets(dict(current["form"]), row_ids, column_ids)
    return _json({
        "form_id": form_id,
        "target_count": len(targets),
        "targets": [
            {
                "row_id": target["row_id"],
                "column_id": target["column"].get("id"),
                "column_title": target["column"].get("title"),
                "has_literature_content": bool(target["content"]),
            }
            for target in targets
        ],
    })


def fill_smart_form_cells(
    form_id: str,
    row_ids: list[str] | None = None,
    column_ids: list[str] | None = None,
) -> str:
    """基于每行文献内容调用结构化生成服务并持久化目标智能单元格。"""

    runtime = _write_runtime("填充智能表格")
    current = _get_form_or_raise(form_id)
    form = dict(current["form"])
    targets = _fill_targets(form, row_ids, column_ids)
    by_row: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        by_row.setdefault(str(target["row_id"]), []).append(target)
    ready = 0
    failed = 0
    errors: list[dict[str, str]] = []
    rows = [dict(row) for row in form.get("rows") or []]
    row_by_id = {str(row.get("id") or ""): row for row in rows}
    for row_id, row_targets in by_row.items():
        content = str(row_targets[0]["content"] or "")
        if not content:
            failed += len(row_targets)
            errors.extend({"row_id": row_id, "column_id": str(target["column"].get("id")), "error": "缺少文献内容"} for target in row_targets)
            continue
        fields = [
            StructuredGenerationField(
                id=str(target["column"].get("id")),
                title=str(target["column"].get("title") or target["column"].get("id")),
                type="tag" if target["column"].get("type") == "smart_tag" else "text",
                options=[str(item) for item in target["column"].get("options") or []],
                required=True,
            )
            for target in row_targets
        ]
        response = _generation_service().generate_fields(
            StructuredGenerationRequest(
                user_id=runtime.user_id,
                source=StructuredGenerationSource(
                    kind="literature_document",
                    content=content,
                    metadata={"form_id": form_id, "row_id": row_id},
                ),
                fields=fields,
                options=StructuredGenerationOptions(language="zh", strict_json=True),
            )
        )
        row = row_by_id[row_id]
        cells = dict(row.get("cells") or {})
        for result in response.results:
            existing = dict(cells.get(result.field_id) or {})
            if result.status == "ready" and result.value.strip():
                existing.update({"value": result.value.strip(), "status": "ready"})
                ready += 1
            else:
                existing.update({"status": "failed"})
                failed += 1
                errors.append({"row_id": row_id, "column_id": result.field_id, "error": result.error or "未生成有效内容"})
            cells[result.field_id] = existing
        row["cells"] = cells
    form["rows"] = rows
    form["updatedAt"] = _now()
    saved = _smart_form_service().save_form(
        user_id=runtime.user_id,
        form_id=form_id,
        asset_dir=str(current.get("asset_dir") or ""),
        form=form,
    )
    return _json({"form_id": form_id, "ready": ready, "failed": failed, "errors": errors, "form": saved})
