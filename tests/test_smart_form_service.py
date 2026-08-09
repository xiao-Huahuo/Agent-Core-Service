"""
Smart form service tests.

功能说明:
验证智能表格通过关系型数据库表保存和加载,覆盖 TODO 中涉及的标签、智能标签、
星级、文件、只读文本和智能文本列。

使用说明:
运行 `python -m pytest tests/test_smart_form_service.py`。
"""

from __future__ import annotations

from sqlmodel import create_engine

from agent_service.services.smart_form_service import SmartFormService


def test_smart_form_service_round_trips_all_column_types() -> None:
    """保存再读取时应完整恢复列定义、标签选项和单元格附件元数据。"""

    engine = create_engine("sqlite:///:memory:")
    service = SmartFormService(engine=engine)
    form = {
        "version": 1,
        "title": "项目阅读表",
        "updatedAt": "2026-08-10T00:00:00+00:00",
        "columns": [
            {"id": "row_index", "title": "序号", "type": "index", "removable": False, "editable": False, "width": 64},
            {"id": "literature_file", "title": "文献上传", "type": "file", "removable": False, "editable": False, "width": 168},
            {"id": "literature_content", "title": "文献内容", "type": "readonly_text", "removable": False, "editable": False, "width": 240},
            {"id": "title", "title": "标题", "type": "smart_text", "removable": False, "editable": True, "width": 230, "tone": "blue"},
            {"id": "paper_type", "title": "文献类型", "type": "smart_tag", "removable": True, "editable": True, "width": 150, "options": ["研究论文", "综述论文"], "tone": "green"},
            {"id": "rating", "title": "重要性", "type": "star", "removable": True, "editable": True, "width": 150},
            {"id": "reading_progress", "title": "阅读进度", "type": "tag", "removable": True, "editable": True, "width": 132, "options": ["未读", "已读", "阅读中"]},
        ],
        "rows": [{
            "id": "row_1",
            "cells": {
                "literature_file": {"value": "paper.pdf", "fileName": "paper.pdf", "assetPath": "forms/项目阅读表/assets/paper.pdf"},
                "literature_content": {"value": "抽取正文", "status": "ready"},
                "title": {"value": "LLM 标题", "status": "ready"},
                "paper_type": {"value": "研究论文, 综述论文", "status": "ready"},
                "rating": {"value": "5"},
                "reading_progress": {"value": "已读"},
            },
        }],
    }

    saved = service.save_form(user_id="u1", asset_dir="forms/项目阅读表", form=form)
    loaded = service.get_form(user_id="u1", form_id=saved["form_id"])

    assert loaded is not None
    loaded_form = loaded["form"]
    assert [column["id"] for column in loaded_form["columns"]] == [column["id"] for column in form["columns"]]
    paper_type = next(column for column in loaded_form["columns"] if column["id"] == "paper_type")
    assert paper_type["options"] == ["研究论文", "综述论文"]
    row_cells = loaded_form["rows"][0]["cells"]
    assert row_cells["paper_type"]["value"] == "研究论文, 综述论文"
    assert row_cells["literature_file"]["assetPath"] == "forms/项目阅读表/assets/paper.pdf"
    assert row_cells["title"]["status"] == "ready"
