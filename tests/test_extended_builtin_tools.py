"""扩展 Agent 内置工具的业务闭环测试。

使用说明:
覆盖多选上下文、统一后台任务、图谱邻接/路径以及智能/普通表格模板和导出，
确保注册测试之外的核心行为也可执行。
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

from sqlmodel import create_engine

from agent_service.schemas.structured_generation import StructuredGenerationFieldResult
from agent_service.services.component_library_service import ComponentLibraryService
from agent_service.services.editor_context_service import EditorContextService
from agent_service.services.favorite_service import FavoriteService
from agent_service.services.feedback_service import FeedbackService
from agent_service.services.smart_form_service import SmartFormService
from agent_service.tools import builtin_business_ops, builtin_knowledge_ops, builtin_smart_forms
from agent_service.tools.runtime_context import AGENT_ACCESS_SANDBOX
from agent_service.tools.builtin_jobs import ToolJobCancelled, ToolJobManager


def test_editor_context_tracks_multi_file_selection() -> None:
    """前端上报的多选路径必须去重、规范化并保留在瞬时上下文。"""

    service = EditorContextService()
    info = service.set_current_document({
        "user_id": "u1",
        "path": "docs/a.pdf",
        "selected_paths": ["docs\\a.pdf", "docs/b.docx", "docs/b.docx"],
    })

    assert info.selected_paths == ("docs/a.pdf", "docs/b.docx")
    assert info.to_dict()["selected_paths"] == ("docs/a.pdf", "docs/b.docx")


def test_tool_job_manager_reports_progress_and_cancels_at_checkpoint() -> None:
    """长任务必须可查询，并能在 runner 的安全检查点进入 cancelled。"""

    manager = ToolJobManager()
    started = threading.Event()

    def runner(update, cancel_event):
        """等待测试发出取消后通过统一异常结束。"""

        update(total=2, current=1, message="half")
        started.set()
        while not cancel_event.wait(0.01):
            pass
        raise ToolJobCancelled("cancelled")

    job = manager.start(user_id="u1", kind="ingestion_selected", runner=runner)
    assert started.wait(1)
    manager.cancel(user_id="u1", job_id=job["job_id"])
    for _ in range(100):
        status = manager.get(user_id="u1", job_id=job["job_id"])
        if status["status"] == "cancelled":
            break
        time.sleep(0.01)

    assert status["status"] == "cancelled"
    assert status["total"] == 2
    assert status["current"] == 1


def test_graph_search_returns_neighbors_and_shortest_path(monkeypatch) -> None:
    """语义节点搜索必须包含邻接信息，路径工具必须返回连接节点和边。"""

    graph = {
        "nodes": [
            {"id": "a", "label": "Alpha", "kind": "entity"},
            {"id": "b", "label": "Beta", "kind": "entity"},
            {"id": "c", "label": "Gamma", "kind": "entity"},
        ],
        "links": [
            {"id": "ab", "source": "a", "target": "b", "kind": "uses"},
            {"id": "bc", "source": "b", "target": "c", "kind": "creates"},
        ],
    }
    monkeypatch.setattr(builtin_knowledge_ops, "_current_graph", lambda limit=5000: graph)

    searched = json.loads(builtin_knowledge_ops.search_knowledge_graph_nodes("Alpha"))
    path = json.loads(builtin_knowledge_ops.find_knowledge_graph_paths("a", "c"))

    assert searched["results"][0]["adjacent_nodes"][0]["id"] == "b"
    assert [node["id"] for node in path["nodes"]] == ["a", "b", "c"]
    assert [edge["id"] for edge in path["edges"]] == ["ab", "bc"]


def test_smart_form_tools_create_both_templates_and_export_content() -> None:
    """smart/plain 两种表格必须与文献列及智能列语义一致，并可真实导出。"""

    smart = builtin_smart_forms._default_form("文献表", "smart")
    plain = builtin_smart_forms._default_form("普通表", "plain")
    smart_ids = {column["id"] for column in smart["columns"]}
    plain_ids = {column["id"] for column in plain["columns"]}

    assert {"literature_file", "literature_content", "figures", "title"} <= smart_ids
    assert "literature_file" not in plain_ids
    assert "figures" not in plain_ids
    assert next(column for column in smart["columns"] if column["id"] == "figures")["title"] == "图表"
    assert all(str(column.get("description") or "").strip() for column in smart["columns"])
    assert next(column for column in smart["columns"] if column["id"] == "title")["type"] == "smart_text"
    assert next(column for column in plain["columns"] if column["id"] == "title")["type"] == "text"
    assert "标题" in builtin_smart_forms._export_csv(plain)
    assert "| 序号 | 标题 |" in builtin_smart_forms._export_markdown(plain)


def test_csv_import_builds_editable_plain_form() -> None:
    """CSV 导入必须把首行变为列，并保留后续每个单元格。"""

    form = builtin_smart_forms._plain_form_from_csv("导入", "名称,状态\nA,完成\n")

    assert [column["title"] for column in form["columns"]] == ["名称", "状态"]
    assert form["rows"][0]["cells"]["col_1"]["value"] == "A"
    assert form["rows"][0]["cells"]["col_2"]["value"] == "完成"


def test_smart_form_agent_tools_complete_create_edit_export_import_and_fill(monkeypatch) -> None:
    """智能表格 Agent 入口必须复用正式持久化和结构化生成服务完成全链路。"""

    service = SmartFormService(engine=create_engine("sqlite:///:memory:"))
    generated_descriptions: list[str] = []

    class _GenerationStub:
        """按请求字段返回稳定生成内容。"""

        def generate_fields(self, request):
            """模拟真实结构化生成服务响应。"""

            generated_descriptions.extend(field.description for field in request.fields)
            return SimpleNamespace(results=[
                StructuredGenerationFieldResult(field_id=field.id, status="ready", value="生成标题")
                for field in request.fields
            ])

    runtime = SimpleNamespace(user_id="u1", agent_access_mode=AGENT_ACCESS_SANDBOX)
    monkeypatch.setattr(builtin_smart_forms, "get_tool_runtime", lambda: runtime)
    monkeypatch.setattr(builtin_smart_forms, "_smart_form_service", lambda: service)
    monkeypatch.setattr(builtin_smart_forms, "_generation_service", lambda: _GenerationStub())

    created = json.loads(builtin_smart_forms.create_smart_form("论文分析", "smart"))
    form_id = created["form_id"]
    row_id = created["form"]["rows"][0]["id"]
    created["form"]["columns"][-1]["description"] = "提取论文首页的正式标题"
    service.save_form(user_id="u1", form_id=form_id, asset_dir=created["asset_dir"], form=created["form"])
    patched = json.loads(builtin_smart_forms.patch_smart_form_rows(
        form_id,
        updates=[{"row_id": row_id, "cells": {
            "literature_file": {"value": "paper.pdf", "fileName": "paper.pdf", "assetPath": "docs/paper.pdf"},
            "literature_content": {"value": "这是一篇实验论文正文", "status": "ready"},
        }}],
    ))
    literature = json.loads(builtin_smart_forms.get_smart_form_literature(form_id))
    preview = json.loads(builtin_smart_forms.preview_smart_form_fill(form_id, [row_id], ["title"]))
    filled = json.loads(builtin_smart_forms.fill_smart_form_cells(form_id, [row_id], ["title"]))
    exported = json.loads(builtin_smart_forms.export_smart_form(form_id, "csv"))
    imported = json.loads(builtin_smart_forms.import_smart_form("名称,状态\nA,完成\n", "csv", "导入结果"))
    imported_json = json.loads(builtin_smart_forms.import_smart_form(
        json.dumps({"version": 1, "title": "原表标题", "columns": [], "rows": []}, ensure_ascii=False),
        "json",
    ))

    assert patched["form"]["rows"][0]["cells"]["literature_content"]["value"] == "这是一篇实验论文正文"
    assert literature["literature"][0]["asset_path"] == "docs/paper.pdf"
    assert preview["target_count"] == 1
    assert filled["ready"] == 1
    assert generated_descriptions == ["提取论文首页的正式标题"]
    assert filled["form"]["form"]["rows"][0]["cells"]["title"]["value"] == "生成标题"
    assert exported["filename"] == "论文分析.csv"
    assert imported["form"]["rows"][0]["cells"]["col_2"]["value"] == "完成"
    assert imported_json["form"]["title"] == "原表标题"


def test_business_agent_tools_complete_feedback_component_favorite_and_library_flows(tmp_path, monkeypatch) -> None:
    """业务工具适配层必须调用正式 service，并保留当前用户和所有权边界。"""

    engine = create_engine("sqlite:///:memory:")

    class _SettingsStub:
        """为组件服务提供临时 active 知识库。"""

        def ensure_user_profile(self, *, user_id: str):
            """返回组件服务需要的用户资料。"""

            return {"user_id": user_id, "active_knowledge_library": {"library_id": "l1", "knowledge_dir": str(tmp_path)}}

    class _LibraryStub:
        """记录图书馆单条查询参数。"""

        def get_item(self, *, user_id: str, item_id: str):
            """返回稳定的图书条目。"""

            return {"item": {"item_id": item_id, "user_id": user_id, "title": "Book"}}

    services = {
        "feedback": FeedbackService(engine=engine),
        "favorite": FavoriteService(engine=engine),
        "component_library": ComponentLibraryService(settings_service=_SettingsStub()),
        "library": _LibraryStub(),
    }
    runtime = SimpleNamespace(user_id="u1", agent_access_mode=AGENT_ACCESS_SANDBOX)
    monkeypatch.setattr(builtin_business_ops, "get_tool_runtime", lambda: runtime)
    monkeypatch.setattr(builtin_business_ops, "_service", lambda name: services[name])

    feedback = json.loads(builtin_business_ops.create_user_feedback("问题", "agent", "home"))
    feedback_id = feedback["feedback_id"]
    assert json.loads(builtin_business_ops.get_user_feedback(feedback_id))["content"] == "问题"
    assert json.loads(builtin_business_ops.update_user_feedback(feedback_id, "已修改"))["content"] == "已修改"
    assert len(json.loads(builtin_business_ops.list_user_feedback())) == 1
    assert json.loads(builtin_business_ops.delete_user_feedback(feedback_id))["deleted"] is True

    component = json.loads(builtin_business_ops.create_component(
        "<template><button>OK</button></template>", "buttons", "ok.vue",
    ))["component"]
    component_id = component["component_id"]
    assert json.loads(builtin_business_ops.get_component(component_id))["component"]["title"] == "ok"
    updated_id = json.loads(builtin_business_ops.update_component(component_id, title="confirm"))["component"]["component_id"]
    assert json.loads(builtin_business_ops.validate_component(updated_id))["valid"] is True
    assert json.loads(builtin_business_ops.list_components("buttons"))["components"][0]["title"] == "confirm"
    assert json.loads(builtin_business_ops.delete_component(updated_id, True))["deleted"] is True

    favorite = json.loads(builtin_business_ops.add_favorite("knowledge_path", "docs/a.pdf", "l1"))
    assert favorite["target_id"] == "docs/a.pdf"
    assert len(json.loads(builtin_business_ops.list_favorites("knowledge_path", "l1"))) == 1
    assert json.loads(builtin_business_ops.remove_favorite("knowledge_path", "docs/a.pdf", "l1"))["deleted"] is True
    component_favorite = json.loads(builtin_business_ops.add_favorite("component", "buttons/confirm.vue", "l1"))
    assert component_favorite["target_id"] == "buttons/confirm.vue"
    assert len(json.loads(builtin_business_ops.list_favorites("component", "l1"))) == 1
    assert json.loads(builtin_business_ops.remove_favorite("component", "buttons/confirm.vue", "l1"))["deleted"] is True
    assert json.loads(builtin_business_ops.get_library_item("book_1"))["item"]["title"] == "Book"


def test_knowledge_agent_tools_complete_batch_status_file_status_and_trash_flows(tmp_path, monkeypatch) -> None:
    """多文件/全量灌库、状态查询及最近删除工具必须共享同一知识库服务。"""

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.pdf").write_bytes(b"pdf")
    (tmp_path / ".mw" / "md" / "docs").mkdir(parents=True)
    (tmp_path / ".mw" / "frontmatter" / "docs").mkdir(parents=True)
    (tmp_path / ".mw" / "md" / "docs" / "a.md").write_text("# A", encoding="utf-8")
    (tmp_path / ".mw" / "frontmatter" / "docs" / "a.json").write_text("{}", encoding="utf-8")

    class _Result:
        """模拟知识库灌库结果 DTO。"""

        def __init__(self, payload):
            """保存可序列化结果。"""

            self.payload = payload

        def to_dict(self):
            """返回结果字典。"""

            return dict(self.payload)

    class _KnowledgeStub:
        """覆盖批处理和最近删除所需服务接口。"""

        def ingest_single_file(self, *, user_id: str, path: str):
            """返回单文件灌库结果。"""

            if path == "docs/fail.pdf":
                raise ValueError("failed")
            return _Result({"path": path, "files_ingested": 1})

        def rebuild_user_knowledge(self, *, user_id: str, progress_callback):
            """上报一次全量进度并返回结果。"""

            progress_callback({"total": 1, "current": 1, "message": "done"})
            return _Result({"files_ingested": 1})

        def list_files(self, *, user_id: str):
            """返回带索引和图谱状态的文件树。"""

            return [{"path": "docs", "isDir": True, "children": [{
                "path": "docs/a.pdf", "name": "a.pdf", "isDir": False,
                "indexStatus": "indexed", "graphStatus": "graphed", "ingestedAt": "now", "size": 3, "mtime": "now",
            }]}]

        def list_deleted_paths(self, *, user_id: str):
            """返回一个最近删除条目。"""

            return [{"trash_id": "trash_1", "original_relative_path": "old.md"}]

        def restore_deleted_path(self, *, user_id: str, trash_id: str):
            """返回恢复结果。"""

            return {"trash_id": trash_id, "restored": True}

        def delete_trash_entry(self, *, user_id: str, trash_id: str):
            """返回永久删除结果。"""

            return {"trash_id": trash_id, "deleted": True}

    runtime = SimpleNamespace(user_id="u1", agent_access_mode=AGENT_ACCESS_SANDBOX)
    monkeypatch.setattr(builtin_knowledge_ops, "get_tool_runtime", lambda: runtime)
    monkeypatch.setattr(builtin_knowledge_ops, "_knowledge_service", lambda: _KnowledgeStub())
    monkeypatch.setattr(builtin_knowledge_ops, "_settings_service", lambda: SimpleNamespace(
        ensure_user_profile=lambda **_: {
            "user_id": "u1",
            "active_knowledge_library": {"library_id": "l1", "knowledge_dir": str(tmp_path)},
        },
    ))

    started = json.loads(builtin_knowledge_ops.ingest_selected_knowledge_files(["docs/a.pdf", "docs/fail.pdf"]))
    for _ in range(100):
        status = json.loads(builtin_knowledge_ops.get_knowledge_job_status(started["job_id"]))
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    all_started = json.loads(builtin_knowledge_ops.ingest_all_knowledge_files())
    file_status = json.loads(builtin_knowledge_ops.get_knowledge_file_status("docs/a.pdf"))

    assert status["status"] == "completed"
    assert status["result"]["processed"] == 1
    assert status["failed_items"] == [{"path": "docs/fail.pdf", "error": "failed"}]
    assert all_started["kind"] == "ingestion_all"
    assert file_status["markdown_projection_exists"] is True
    assert file_status["frontmatter_exists"] is True
    assert json.loads(builtin_knowledge_ops.list_knowledge_trash())[0]["trash_id"] == "trash_1"
    assert json.loads(builtin_knowledge_ops.restore_knowledge_file("trash_1"))["restored"] is True
    assert json.loads(builtin_knowledge_ops.permanently_delete_knowledge_trash("trash_1", True))["deleted"] is True
