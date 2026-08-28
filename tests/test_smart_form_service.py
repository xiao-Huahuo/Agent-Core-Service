"""
Smart form service tests.

功能说明:
验证智能表格通过关系型数据库表保存和加载,覆盖 TODO 中涉及的标签、智能标签、
星级、文件、只读文本和智能文本列。

使用说明:
运行 `python -m pytest tests/test_smart_form_service.py`。
"""

from __future__ import annotations

from sqlmodel import Session

from tests.db_test_utils import create_test_engine as create_engine

from agent_service.models.user_settings import UserKnowledgeLibrary
from agent_service.services.smart_form.service import SmartFormService


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
            {"id": "title", "title": "标题", "description": "提取论文正式标题", "type": "smart_text", "removable": False, "editable": True, "width": 230, "tone": "blue"},
            {"id": "paper_type", "title": "文献类型", "type": "smart_tag", "removable": True, "editable": True, "width": 150, "options": ["研究论文", "综述论文"], "tone": "green"},
            {"id": "rating", "title": "重要性", "type": "star", "removable": True, "editable": True, "width": 150},
            {"id": "reading_progress", "title": "阅读进度", "type": "tag", "removable": True, "editable": True, "width": 132, "options": ["未读", "已读", "阅读中"]},
        ],
        "rows": [{
            "id": "row_1",
            "height": 176,
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
    assert loaded_form["rows"][0]["height"] == 176
    assert next(column for column in loaded_form["columns"] if column["id"] == "title")["description"] == "提取论文正式标题"
    assert row_cells["paper_type"]["value"] == "研究论文, 综述论文"
    assert row_cells["literature_file"]["assetPath"] == "forms/项目阅读表/assets/paper.pdf"
    assert row_cells["title"]["status"] == "ready"


def test_smart_form_service_deletes_only_the_owners_form() -> None:
    """删除表格应清除完整关系数据,且不能删除其他用户的表格。"""

    engine = create_engine("sqlite:///:memory:")
    service = SmartFormService(engine=engine)
    saved = service.save_form(
        user_id="owner",
        asset_dir=".mw/forms/delete-me",
        form={
            "title": "待删除表格",
            "columns": [{"id": "text", "title": "文本", "type": "text"}],
            "rows": [{"id": "row-1", "cells": {"text": {"value": "内容"}}}],
        },
    )

    assert service.delete_form(user_id="other", form_id=saved["form_id"]) is False
    assert service.get_form(user_id="owner", form_id=saved["form_id"]) is not None
    assert service.delete_form(user_id="owner", form_id=saved["form_id"]) is True
    assert service.get_form(user_id="owner", form_id=saved["form_id"]) is None


def test_literature_entries_are_library_scoped_and_preserve_entry_time(tmp_path) -> None:
    """文献阅读只列出所属知识库智能表行，整表保存后入表时间保持稳定。"""

    engine = create_engine("sqlite:///:memory:")
    service = SmartFormService(engine=engine)
    with Session(engine) as db:
        db.add(UserKnowledgeLibrary(library_id="lib-1", user_id="u1", name="项目库", knowledge_dir=str(tmp_path), is_active=True))
        db.commit()
    asset_dir = tmp_path / ".mw" / "forms" / "papers" / "assets"
    asset_dir.mkdir(parents=True)
    source = asset_dir / "paper.pdf"
    source.write_bytes(b"pdf")
    form = {
        "title": "论文表",
        "columns": [
            {"id": "literature_file", "title": "文献上传", "type": "file"},
            {"id": "literature_content", "title": "文献内容", "type": "readonly_text"},
            {"id": "title", "title": "标题", "type": "smart_text"},
        ],
        "rows": [{"id": "row-1", "cells": {
            "literature_file": {"value": "paper.pdf", "fileName": "paper.pdf", "assetPath": ".mw/forms/papers/assets/paper.pdf"},
            "literature_content": {"value": "完整正文"},
            "title": {"value": "论文标题"},
        }}],
    }
    saved = service.save_form(user_id="u1", library_id="lib-1", form_kind="literature", asset_dir=".mw/forms/papers", form=form)
    first_created_at = saved["form"]["rows"][0]["createdAt"]
    saved_again = service.save_form(user_id="u1", form_id=saved["form_id"], library_id="lib-1", form_kind="literature", asset_dir=".mw/forms/papers", form=saved["form"])

    assert saved_again["form"]["rows"][0]["createdAt"] == first_created_at
    entries = service.list_literature_entries(user_id="u1", library_id="lib-1")
    assert [(entry["title"], entry["file_size"]) for entry in entries] == [("论文标题", 3)]
    assert service.list_forms(user_id="u1", library_id="other") == []


def test_duplicate_and_delete_literature_row_manage_independent_real_files(tmp_path) -> None:
    """复制行应复制真实文件，删除副本时不能破坏原文献。"""

    engine = create_engine("sqlite:///:memory:")
    service = SmartFormService(engine=engine)
    with Session(engine) as db:
        db.add(UserKnowledgeLibrary(library_id="lib-1", user_id="u1", name="项目库", knowledge_dir=str(tmp_path), is_active=True))
        db.commit()
    asset_dir = tmp_path / ".mw" / "forms" / "papers" / "assets"
    asset_dir.mkdir(parents=True)
    source = asset_dir / "paper.pdf"
    source.write_bytes(b"pdf")
    saved = service.save_form(user_id="u1", library_id="lib-1", form_kind="literature", asset_dir=".mw/forms/papers", form={
        "title": "论文表",
        "columns": [{"id": "literature_file", "title": "文献上传", "type": "file"}, {"id": "literature_content", "title": "文献内容", "type": "readonly_text"}],
        "rows": [{"id": "row-1", "cells": {"literature_file": {"value": "paper.pdf", "fileName": "paper.pdf", "assetPath": ".mw/forms/papers/assets/paper.pdf"}}}],
    })
    duplicated = service.duplicate_literature_row(user_id="u1", form_id=saved["form_id"], row_id="row-1")
    copied_row = duplicated["form"]["rows"][1]
    copied_path = tmp_path / copied_row["cells"]["literature_file"]["assetPath"]

    assert copied_path.exists()
    assert copied_path != source
    assert service.delete_literature_row(user_id="u1", form_id=saved["form_id"], row_id=copied_row["id"], delete_file=True)
    assert not copied_path.exists()
    assert source.exists()
