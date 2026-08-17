"""扩展业务内置工具注册定义。

使用说明:
本文件集中登记知识处理、业务管理和智能表格工具；实现分别位于对应的
``builtin_*`` 模块。``definitions.py`` 将本列表并入最终注册表。
"""

from __future__ import annotations

from typing import Any, Callable

from agent_service.tools.builtin import BuiltinToolDefinition
from agent_service.tools.builtin_business_ops import (
    add_favorite,
    create_component,
    create_custom_skill,
    create_user_feedback,
    delete_component,
    delete_custom_skill,
    delete_user_feedback,
    get_component,
    get_custom_skill,
    get_library_item,
    get_user_feedback,
    list_components,
    list_favorites,
    list_user_feedback,
    remove_favorite,
    set_skill_enabled,
    test_custom_skill,
    update_component,
    update_custom_skill,
    update_user_feedback,
    validate_component,
    validate_custom_skill,
)
from agent_service.tools.builtin_knowledge_ops import (
    cancel_knowledge_job,
    delete_file_graph,
    extract_all_file_graphs,
    extract_selected_file_graphs,
    find_knowledge_graph_paths,
    get_knowledge_file_status,
    get_knowledge_job_status,
    get_selected_knowledge_files,
    ingest_all_knowledge_files,
    ingest_selected_knowledge_files,
    list_knowledge_trash,
    permanently_delete_knowledge_trash,
    restore_knowledge_file,
    retry_failed_graph_extraction,
    retry_failed_knowledge_files,
    search_knowledge_graph_nodes,
)
from agent_service.tools.builtin_smart_forms import (
    create_smart_form,
    export_smart_form,
    fill_smart_form_cells,
    get_smart_form,
    get_smart_form_literature,
    get_smart_form_schema,
    import_smart_form,
    list_smart_forms,
    patch_smart_form_rows,
    preview_smart_form_fill,
    update_smart_form,
)


def _tool(
    name: str,
    display_name: str,
    description: str,
    function: Callable[..., str],
    properties: dict[str, Any] | None = None,
    required: tuple[str, ...] = (),
) -> BuiltinToolDefinition:
    """用统一对象 schema 创建扩展工具定义。"""

    return BuiltinToolDefinition(
        name=name,
        display_name=display_name,
        description=description,
        args_schema={"type": "object", "properties": properties or {}, "required": list(required)},
        function=function,
    )


def _string(description: str, **extra: Any) -> dict[str, Any]:
    """创建字符串参数 schema。"""

    return {"type": "string", "description": description, **extra}


def _boolean(description: str) -> dict[str, Any]:
    """创建布尔参数 schema。"""

    return {"type": "boolean", "description": description}


def _integer(description: str, minimum: int | None = None, maximum: int | None = None) -> dict[str, Any]:
    """创建带可选边界的整数参数 schema。"""

    schema: dict[str, Any] = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    return schema


def _string_array(description: str) -> dict[str, Any]:
    """创建字符串数组参数 schema。"""

    return {"type": "array", "items": {"type": "string"}, "description": description}


def _object(description: str) -> dict[str, Any]:
    """创建自由对象参数 schema。"""

    return {"type": "object", "description": description}


def _object_array(description: str) -> dict[str, Any]:
    """创建自由对象数组参数 schema。"""

    return {"type": "array", "items": {"type": "object"}, "description": description}


EXTENDED_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    _tool("get_selected_knowledge_files", "获取多选文件", "读取文件资源管理器当前多选的知识库路径；无多选时回退当前文档。", get_selected_knowledge_files),
    _tool(
        "ingest_selected_knowledge_files", "多选文件灌库",
        "为指定多个源文件启动后台灌库，返回 job_id；随后用 get_knowledge_job_status 查询进度。",
        ingest_selected_knowledge_files, {"paths": _string_array("源文件相对路径列表。")}, ("paths",),
    ),
    _tool("ingest_all_knowledge_files", "全量灌库", "扫描并灌入当前 active 知识库全部支持文件，返回 job_id。", ingest_all_knowledge_files),
    _tool(
        "get_knowledge_job_status", "查询知识任务", "查询灌库或图谱后台任务的进度、结果和逐文件失败。",
        get_knowledge_job_status, {"job_id": _string("任务 ID。")}, ("job_id",),
    ),
    _tool(
        "cancel_knowledge_job", "取消知识任务", "请求灌库或图谱任务在下一个安全检查点取消。",
        cancel_knowledge_job, {"job_id": _string("任务 ID。")}, ("job_id",),
    ),
    _tool(
        "retry_failed_knowledge_files", "重试灌库失败文件", "只重新灌入历史任务中失败的文件并返回新 job_id。",
        retry_failed_knowledge_files, {"job_id": _string("历史灌库任务 ID。")}, ("job_id",),
    ),
    _tool(
        "get_knowledge_file_status", "查询文件管线状态", "查询源文件、Markdown 投影、frontmatter、向量索引和图谱状态。",
        get_knowledge_file_status, {"path": _string("源文件相对路径。")}, ("path",),
    ),
    _tool("list_knowledge_trash", "列出最近删除", "列出当前知识库最近删除的条目及 trash_id。", list_knowledge_trash),
    _tool(
        "restore_knowledge_file", "恢复知识文件", "按 trash_id 从最近删除恢复文件或文件夹。",
        restore_knowledge_file, {"trash_id": _string("最近删除条目 ID。")}, ("trash_id",),
    ),
    _tool(
        "permanently_delete_knowledge_trash", "彻底删除知识文件", "永久删除最近删除条目，不可恢复，必须由用户明确确认。",
        permanently_delete_knowledge_trash,
        {"trash_id": _string("最近删除条目 ID。"), "confirm": _boolean("用户是否明确确认永久删除。")},
        ("trash_id",),
    ),
    _tool(
        "extract_selected_file_graphs", "多选文件图谱抽取", "自动灌库并为指定多个源文件后台抽取图谱，返回 job_id。",
        extract_selected_file_graphs, {"paths": _string_array("源文件相对路径列表。")}, ("paths",),
    ),
    _tool("extract_all_file_graphs", "全量图谱抽取", "为当前 active 知识库全部文件后台抽取语义图谱。", extract_all_file_graphs),
    _tool(
        "search_knowledge_graph_nodes", "搜索语义图谱节点", "按标签、类型和元数据搜索节点，并返回每个命中的邻接节点与边。",
        search_knowledge_graph_nodes,
        {"query": _string("节点查询文本。"), "limit": _integer("最多返回节点数。", 1, 100)}, ("query",),
    ),
    _tool(
        "find_knowledge_graph_paths", "查找图谱关系路径", "查找两个图谱节点间限定深度内的最短关系路径。",
        find_knowledge_graph_paths,
        {
            "source_node_id": _string("起点节点 ID。"),
            "target_node_id": _string("终点节点 ID。"),
            "max_depth": _integer("最大关系深度。", 1, 12),
        },
        ("source_node_id", "target_node_id"),
    ),
    _tool(
        "delete_file_graph", "删除文件图谱", "删除指定源文件对应的文档节点、实体关系和抽取状态。",
        delete_file_graph, {"path": _string("源文件相对路径。")}, ("path",),
    ),
    _tool(
        "retry_failed_graph_extraction", "重试图谱失败文件", "只重新抽取历史图谱任务中失败的文件。",
        retry_failed_graph_extraction, {"job_id": _string("历史图谱任务 ID。")}, ("job_id",),
    ),
    _tool("get_custom_skill", "读取定制 Skill", "读取一个用户定制 Skill 的完整 SKILL.md。", get_custom_skill, {"skill_id": _string("user:* Skill ID。")}, ("skill_id",)),
    _tool(
        "create_custom_skill", "定制 Skill", "创建与 Skill 页面一致的用户 Skill。",
        create_custom_skill,
        {"name": _string("Skill 名称。"), "description": _string("用途与触发说明。"), "body": _string("完整工作流正文。")},
        ("name", "description", "body"),
    ),
    _tool(
        "update_custom_skill", "更新定制 Skill", "增量修改用户 Skill 的名称、说明或正文。",
        update_custom_skill,
        {"skill_id": _string("user:* Skill ID。"), "name": _string("新名称。"), "description": _string("新说明。"), "body": _string("新正文。")},
        ("skill_id",),
    ),
    _tool(
        "delete_custom_skill", "删除定制 Skill", "删除用户 Skill，必须取得用户明确确认。",
        delete_custom_skill,
        {"skill_id": _string("user:* Skill ID。"), "confirm": _boolean("用户是否明确确认。")}, ("skill_id",),
    ),
    _tool("validate_custom_skill", "验证定制 Skill", "验证 Skill frontmatter、正文和索引可读性。", validate_custom_skill, {"skill_id": _string("user:* Skill ID。")}, ("skill_id",)),
    _tool("test_custom_skill", "测试定制 Skill", "使用真实关键词路由器测试 Skill 对给定提示的匹配。", test_custom_skill, {"skill_id": _string("user:* Skill ID。"), "prompt": _string("测试提示。")}, ("skill_id", "prompt")),
    _tool("set_skill_enabled", "切换 Skill", "启用或停用一个内置或用户 Skill。", set_skill_enabled, {"skill_id": _string("Skill ID。"), "enabled": _boolean("是否启用。")}, ("skill_id", "enabled")),
    _tool("list_user_feedback", "列出用户反馈", "列出当前用户提交的全部反馈。", list_user_feedback),
    _tool("get_user_feedback", "读取用户反馈", "按 feedback_id 读取当前用户的一条反馈。", get_user_feedback, {"feedback_id": _string("反馈 ID。")}, ("feedback_id",)),
    _tool(
        "create_user_feedback", "新增用户反馈", "以当前用户身份新增反馈。", create_user_feedback,
        {"content": _string("反馈正文。"), "source": _string("反馈来源。"), "page": _string("关联页面。")}, ("content",),
    ),
    _tool("update_user_feedback", "修改用户反馈", "修改当前用户拥有的反馈正文。", update_user_feedback, {"feedback_id": _string("反馈 ID。"), "content": _string("新正文。")}, ("feedback_id", "content")),
    _tool("delete_user_feedback", "删除用户反馈", "删除当前用户拥有的一条反馈。", delete_user_feedback, {"feedback_id": _string("反馈 ID。")}, ("feedback_id",)),
    _tool("get_library_item", "读取图书馆条目", "读取单个图书或集锦的完整元数据；筛选列表继续使用 list_library_items。", get_library_item, {"item_id": _string("图书馆条目 ID。")}, ("item_id",)),
    _tool("list_components", "筛选组件", "按组件类型筛选并列出用户组件。", list_components, {"component_type": _string("组件类型；any 表示全部。")}),
    _tool("get_component", "读取组件", "读取一个组件的完整源码和元数据。", get_component, {"component_id": _string("组件 ID。")}, ("component_id",)),
    _tool(
        "create_component", "新增组件", "创建 Vue SFC 或独立 HTML 组件。", create_component,
        {"source": _string("组件源码。"), "component_type": _string("组件类型。"), "filename": _string("可选文件名。")},
        ("source", "component_type"),
    ),
    _tool(
        "update_component", "修改组件", "增量修改组件源码、类型或标题。", update_component,
        {"component_id": _string("组件 ID。"), "source": _string("新源码。"), "component_type": _string("新组件类型。"), "title": _string("新标题。")},
        ("component_id",),
    ),
    _tool("delete_component", "删除组件", "删除用户组件，必须取得用户明确确认。", delete_component, {"component_id": _string("组件 ID。"), "confirm": _boolean("用户是否明确确认。")}, ("component_id",)),
    _tool("validate_component", "验证组件", "验证组件源码格式及 Vue/HTML 基本结构。", validate_component, {"component_id": _string("组件 ID。")}, ("component_id",)),
    _tool(
        "list_favorites", "列出收藏", "按目标类型和知识库作用域列出收藏。", list_favorites,
        {"target_type": _string("knowledge_path、library_item 或 session。"), "library_id": _string("可选知识库 ID。")},
    ),
    _tool(
        "add_favorite", "新增收藏", "收藏知识库路径、图书馆条目或会话。", add_favorite,
        {"target_type": _string("收藏目标类型。"), "target_id": _string("目标 ID。"), "library_id": _string("可选知识库 ID。")},
        ("target_type", "target_id"),
    ),
    _tool(
        "remove_favorite", "取消收藏", "取消知识库路径、图书馆条目或会话收藏。", remove_favorite,
        {"target_type": _string("收藏目标类型。"), "target_id": _string("目标 ID。"), "library_id": _string("可选知识库 ID。")},
        ("target_type", "target_id"),
    ),
    _tool("list_smart_forms", "列出智能表格", "按标题关键词列出当前用户表格。", list_smart_forms, {"query": _string("可选标题关键词。")}),
    _tool(
        "create_smart_form", "创建智能表格", "创建 smart 智能文献表或 plain 普通表。", create_smart_form,
        {"title": _string("表格标题。"), "kind": _string("smart 或 plain。", enum=["smart", "plain"])}, ("title",),
    ),
    _tool("get_smart_form", "获取智能表格", "读取表格完整列、行和单元格。", get_smart_form, {"form_id": _string("表格 ID。")}, ("form_id",)),
    _tool("get_smart_form_schema", "获取表格结构", "仅读取表格列定义、基本信息和行数。", get_smart_form_schema, {"form_id": _string("表格 ID。")}, ("form_id",)),
    _tool("update_smart_form", "更新智能表格", "使用完整表格结构覆盖更新指定表格。", update_smart_form, {"form_id": _string("表格 ID。"), "form": _object("完整表格结构。")}, ("form_id", "form")),
    _tool(
        "patch_smart_form_rows", "编辑智能表项", "按 row_id 增量修改、增加或删除表格行和单元格。", patch_smart_form_rows,
        {"form_id": _string("表格 ID。"), "updates": _object_array("行更新。"), "add_rows": _object_array("新增行。"), "delete_row_ids": _string_array("删除行 ID。")},
        ("form_id",),
    ),
    _tool(
        "get_smart_form_literature", "获取表项文献", "读取表项关联文献的文件名、知识库路径和抽取内容。", get_smart_form_literature,
        {"form_id": _string("表格 ID。"), "row_ids": _string_array("可选行 ID。")}, ("form_id",),
    ),
    _tool(
        "export_smart_form", "导出智能表格", "导出为 csv、markdown 或 json，返回文件名和完整内容。", export_smart_form,
        {"form_id": _string("表格 ID。"), "format": _string("csv、markdown 或 json。", enum=["csv", "markdown", "json"])}, ("form_id",),
    ),
    _tool(
        "import_smart_form", "导入智能表格", "从 JSON 或 CSV 内容创建新表格。", import_smart_form,
        {"content": _string("完整导入内容。"), "format": _string("json 或 csv。", enum=["json", "csv"]), "title": _string("导入后的标题。")},
        ("content",),
    ),
    _tool(
        "preview_smart_form_fill", "预览智能填充", "列出将被智能填充的单元格及文献上下文状态，不调用模型、不写数据库。", preview_smart_form_fill,
        {"form_id": _string("表格 ID。"), "row_ids": _string_array("可选行 ID。"), "column_ids": _string_array("可选智能列 ID。")},
        ("form_id",),
    ),
    _tool(
        "fill_smart_form_cells", "填充智能表项", "根据每行文献内容调用结构化生成服务并持久化智能单元格。", fill_smart_form_cells,
        {"form_id": _string("表格 ID。"), "row_ids": _string_array("可选行 ID。"), "column_ids": _string_array("可选智能列 ID。")},
        ("form_id",),
    ),
]
