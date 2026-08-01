"""
内置工具分组定义模块。

功能说明:
本文件只登记内置工具的名称、描述、参数 schema 与函数引用。实际工具函数仍在
`builtin.py` 中实现,工具注册表仍可通过 `agent_service.tools.builtin` 兼容导入。

使用说明:
新增工具时,先在 `builtin.py` 中实现函数,再在本文件对应分组中登记
`BuiltinToolDefinition`。
"""

from __future__ import annotations

from agent_service.tools.builtin import (
    BuiltinToolDefinition,
    add_todo,
    complete_task_list_item,
    create_task_list,
    create_knowledge_folder,
    delete_knowledge_file,
    delete_long_term_memory,
    delete_long_term_rule,
    delete_todo,
    download_file,
    edit_todo,
    finish_task_list,
    get_current_time,
    git_commit_files,
    git_add_remote,
    git_create_branch,
    git_diff,
    git_history,
    git_init_repository,
    git_pull_branch,
    git_push_branch,
    git_restore_files,
    git_status,
    git_switch_branch,
    get_task_list_status,
    get_current_viewing_document,
    get_knowledge_context,
    get_knowledge_file_url,
    get_long_term_memory,
    list_available_tools,
    list_skills,
    list_knowledge_files,
    list_todos,
    read_knowledge_file,
    read_multimodal_file_info,
    rebuild_knowledge_base,
    rename_knowledge_file,
    run_terminal_command,
    save_uploaded_attachment_to_knowledge,
    search_knowledge,
    show_markdown_html,
    toggle_todo,
    use_skill,
    web_search,
    web_image_search,
    write_knowledge_file,
    write_long_term_memory,
    write_long_term_rule,
)

UTILITY_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="list_available_tools",
        description=(
            "列出当前可用的全部工具(中文名、工具名、一句话用途),每行一个。"
            "当本轮仅预绑定了部分工具时,可调用本工具查看完整清单,"
            "再在回复中说出所需工具名,下一轮即可放开绑定使用。"
        ),
        args_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=list_available_tools,
        display_name="查看可用工具",
    ),
    BuiltinToolDefinition(
        name="get_current_time",
        description="获取指定 IANA 时区的当前时间。默认使用 UTC。",
        args_schema={
            "type": "object",
            "properties": {
                "timezone_name": {
                    "type": "string",
                    "description": "IANA 时区名称,例如 UTC、Asia/Shanghai。",
                }
            },
            "required": [],
        },
        function=get_current_time,
        display_name="获取当前时间",
    ),
    BuiltinToolDefinition(
        name="run_terminal_command",
        description=(
            "在项目终端沙盒中执行一个或多个结构化指令段。必须传 shell、segments、cwd; "
            "禁止传整条 shell 字符串。\n\n"
            "内部读取指令(internal_command 类型): pwd(当前目录), ls/dir(列出目录,"
            "支持 -a/R/l 和 /s/b 等标志,支持 *.docx 通配符), cat/type(读文件), "
            "head/tail -n N 文件(行窗口), stat(文件状态), wc(统计行/词/字符数,可用 -c/-l/-w 筛选"
            "但始终显示三项;未指定文件则返回总计数)。\n"
            "内部写入指令: write(覆写), append(追加), touch(创建/时间戳), "
            "mkdir(始终 -p 模式), rm/del(目录递归删除), mv/move(移动/重命名)。\n\n"
            "外部程序段(external_program 类型): 在沙盒/只读模式下需在白名单内,"
            "白名单程序包括 python/pytest/pip/git/npm/node/eslint/vitest/go/cargo/find/wc 等;"
            "find 用于搜索文件(如 find . -name '*.docx' -type f), "
            "wc 用于带标志统计(如 wc -l file.txt)。"
            "完全访问模式下所有外部程序都允许(嵌套 shell 仍禁止)。\n\n"
            "权限模式影响:\n"
            "- readonly: 仅内部读取指令(pwd/ls/cat/head/tail/stat/wc),禁止写入和外部程序。\n"
            "- sandbox(默认): 内部读取可穿透工作区根目录;写入和外部程序限制在工作区内。\n"
            "- full_access: 所有内部指令和外部程序放开限制,额外支持 kill/taskkill 杀进程,"
            "rm -rf/mkdir -p/批量 cat/mv 等都允许。\n\n"
            "注意事项:\n"
            "- 读取或解析知识库中的文档正文时, 不要使用本工具; 文本/Markdown/代码用 read_knowledge_file, PDF/图片/Office/表格/扫描件用 read_multimodal_file_info。\n"
            "- 文件搜索优先用 ls/dir *.docx /s /b 或 find . -name '*.docx'。\n"
            "- 需要标志的 wc(如 wc -l)用 external_program 类型;仅统计用 internal_command。\n"
            "- 所有 internal_command 都无需 shell 程序支持,在任何环境下可用。"
        ),
        args_schema={
            "type": "object",
            "properties": {
                "shell": {"type": "string", "description": "终端策略名: cmd、powershell 或 bash。"},
                "segments": {
                    "type": "array",
                    "description": (
                        "指令段数组。外部程序段格式为 {type:'external_program', program:'python', args:['-m','pytest']};"
                        "内部系统指令段格式为 {type:'internal_command', command:'ls', args:['.']}。"
                    ),
                },
                "cwd": {"type": "string", "description": "相对沙盒工作区的工作目录,默认当前工作区根目录。"},
                "timeout_seconds": {"type": "integer", "description": "可选单段超时时间,受沙盒最大值限制。"},
            },
            "required": ["shell", "segments"],
        },
        function=run_terminal_command,
        display_name="终端命令",
    ),
    BuiltinToolDefinition(
        name="download_file",
        description="下载文件到本地存储。注意: 展示图片时请直接使用 Markdown 热链接嵌入原始图片 URL,不要使用本工具。仅在用户明确要求保存或下载文件时才调用本工具。如果 save_to_knowledge=True,还会将文件拷贝到知识库并灌库。下载后的文件可通过 /downloads/ 路径在 Markdown 中引用。",
        args_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "待下载文件的完整 URL。"},
                "save_to_knowledge": {"type": "boolean", "description": "是否同时保存到当前 active 知识库并灌库。默认 false。"},
                "knowledge_path": {"type": "string", "description": "可选。保存到知识库时的相对路径。"},
            },
            "required": ["url"],
        },
        function=download_file,
        display_name="下载文件",
    ),
]

GIT_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="git_status",
        description="读取当前知识库仓库状态、分支、远程、更改和未跟踪文件。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=git_status,
        display_name="Git 状态",
    ),
    BuiltinToolDefinition(
        name="git_diff",
        description="读取当前知识库工作区或暂存区的 Git diff。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "可选知识库相对路径。"},
                "staged": {"type": "boolean", "description": "是否读取暂存区差异。"},
            },
            "required": [],
        },
        function=git_diff,
        display_name="Git 差异",
    ),
    BuiltinToolDefinition(
        name="git_history",
        description="读取提交历史、未推送提交和未推送文件。",
        args_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "最大提交数,默认 30。"}},
            "required": [],
        },
        function=git_history,
        display_name="Git 历史",
    ),
    BuiltinToolDefinition(
        name="git_init_repository",
        description="在当前知识库根目录初始化 Git 仓库。",
        args_schema={
            "type": "object",
            "properties": {"initial_branch": {"type": "string", "description": "初始分支名,默认 main。"}},
            "required": [],
        },
        function=git_init_repository,
        display_name="初始化 Git",
    ),
    BuiltinToolDefinition(
        name="git_restore_files",
        description=(
            "回滚选中文件。已跟踪文件恢复到 HEAD 并清理旧知识索引;"
            "未跟踪文件移入 MetaWeave 最近删除,不会永久清除。"
        ),
        args_schema={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "知识库相对路径列表。",
                }
            },
            "required": ["paths"],
        },
        function=git_restore_files,
        display_name="Git 回滚",
    ),
    BuiltinToolDefinition(
        name="git_commit_files",
        description="暂存选中的知识库文件并创建本地提交。",
        args_schema={
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
                "message": {"type": "string", "description": "提交概要。"},
            },
            "required": ["paths", "message"],
        },
        function=git_commit_files,
        display_name="Git 提交",
    ),
    BuiltinToolDefinition(
        name="git_push_branch",
        description=(
            "推送本地分支到远程。必须先获得用户明确确认并传 confirm=true;"
            "force-with-lease 还需要独立的 confirm_force=true。"
        ),
        args_schema={
            "type": "object",
            "properties": {
                "local_branch": {"type": "string"},
                "remote": {"type": "string"},
                "remote_branch": {"type": "string"},
                "confirm": {"type": "boolean"},
                "force_with_lease": {"type": "boolean"},
                "confirm_force": {"type": "boolean"},
                "all_branches": {
                    "type": "boolean",
                    "description": "为 true 时推送所有本地分支。",
                },
            },
            "required": ["local_branch", "remote", "remote_branch", "confirm"],
        },
        function=git_push_branch,
        display_name="Git 推送",
    ),
    BuiltinToolDefinition(
        name="git_create_branch",
        description="创建本地 Git 分支,可选择立即切换。",
        args_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "checkout": {"type": "boolean"},
            },
            "required": ["name"],
        },
        function=git_create_branch,
        display_name="创建 Git 分支",
    ),
    BuiltinToolDefinition(
        name="git_add_remote",
        description="为当前知识库 Git 仓库新增命名远程。",
        args_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "远程名称,例如 origin。"},
                "url": {"type": "string", "description": "HTTPS、SSH 或本地 Git 仓库地址。"},
            },
            "required": ["name", "url"],
        },
        function=git_add_remote,
        display_name="新增 Git 远程",
    ),
    BuiltinToolDefinition(
        name="git_switch_branch",
        description="切换本地 Git 分支并使实际变化文件的知识索引失效。",
        args_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        function=git_switch_branch,
        display_name="切换 Git 分支",
    ),
    BuiltinToolDefinition(
        name="git_pull_branch",
        description="获取并快进合并远程分支,不会自动创建合并提交。",
        args_schema={
            "type": "object",
            "properties": {
                "remote": {"type": "string"},
                "branch": {"type": "string"},
            },
            "required": ["remote", "branch"],
        },
        function=git_pull_branch,
        display_name="Git 拉取",
    ),
]

SKILL_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="list_skills",
        description="List all skills visible to the current user, including built-in and user-level skills, their sources, descriptions, and enabled states.",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=list_skills,
        display_name="列出技能",
    ),
]

SKILL_TOOL_DEFINITIONS.append(
    BuiltinToolDefinition(
        name="use_skill",
        description="Load one enabled Skill's SKILL.md body into the current turn when the Agent needs detailed instructions for a specific skill. Use skill_ref from list_skills, such as skill_id, name, or folder name.",
        args_schema={
            "type": "object",
            "properties": {
                "skill_ref": {
                    "type": "string",
                    "description": "Skill id, Skill name, or skill folder name returned by list_skills.",
                }
            },
            "required": ["skill_ref"],
        },
        function=use_skill,
        display_name="使用技能",
    )
)

MEMORY_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_long_term_memory",
        description="检索当前用户在长期记忆中的相关摘要信息,用于跨轮对话回忆项目目标、约束、偏好和历史事实。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "需要检索的记忆查询文本。"},
                "top_k": {"type": "integer", "description": "最多返回多少条结果,默认 3。"},
            },
            "required": ["query"],
        },
        function=get_long_term_memory,
        display_name="检索记忆",
    ),
    BuiltinToolDefinition(
        name="write_long_term_memory",
        description="向当前用户的长期记忆中写入一条记录,包含向量化后可被后续对话检索召回。可用于手动存储重要信息、项目代号、用户偏好等需要跨会话持久化的内容。",
        args_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "需要记忆的内容,建议简洁完整,以便后续检索。"},
                "memory_type": {"type": "string", "description": "记忆子类型,默认 important_fact_summary。一般无需修改。"},
                "importance": {"type": "number", "description": "重要性(0~1),默认 0.5。"},
                "authority": {"type": "number", "description": "权威性(0~1),默认 0.5。"},
            },
            "required": ["content"],
        },
        function=write_long_term_memory,
        display_name="写入记忆",
    ),
    BuiltinToolDefinition(
        name="write_long_term_rule",
        description="向当前用户的长期系统规则中追加一条必须遵守的指令,效果等同于用户在设置页手动添加系统提示词。该规则每轮都会注入系统提示词,不依赖 RAG 召回。",
        args_schema={
            "type": "object",
            "properties": {"content": {"type": "string", "description": "需要长期遵守的规则内容。"}},
            "required": ["content"],
        },
        function=write_long_term_rule,
        display_name="写入长期规则",
    ),
    BuiltinToolDefinition(
        name="delete_long_term_memory",
        description="删除当前用户的一条长期记忆。按内容文本匹配后删除,会先尝试精确匹配,再尝试包含匹配。用于清理或修正错误写入的记忆。",
        args_schema={
            "type": "object",
            "properties": {"content": {"type": "string", "description": "需要删除的记忆内容关键词或完整句子。"}},
            "required": ["content"],
        },
        function=delete_long_term_memory,
        display_name="删除记忆",
    ),
    BuiltinToolDefinition(
        name="delete_long_term_rule",
        description="删除当前用户的一条长期系统规则。按内容文本匹配后删除,会先尝试精确匹配,再尝试包含匹配。用于清理或修正不再需要的长期规则。",
        args_schema={
            "type": "object",
            "properties": {"content": {"type": "string", "description": "需要删除的规则内容关键词或完整句子。"}},
            "required": ["content"],
        },
        function=delete_long_term_rule,
        display_name="删除长期规则",
    ),
]

KNOWLEDGE_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_knowledge_context",
        description=(
            "按语义召回当前用户知识库中的正文片段,返回可直接用于回答的内容摘录和来源。"
            "适合用户已经在问某个事实、概念或文档内容,需要查正文来回答时使用。"
            "它不是文件名搜索;如果目标是找文件、按文件名关键词定位路径,请使用 search_knowledge 或 list_knowledge_files。"
        ),
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用于语义召回正文片段的问题、主题或事实查询。"},
                "top_k": {"type": "integer", "description": "最多返回多少条结果,默认 3。"},
            },
            "required": ["query"],
        },
        function=get_knowledge_context,
        display_name="检索知识",
    ),
    BuiltinToolDefinition(
        name="rebuild_knowledge_base",
        description="主动重新扫描当前用户的本地知识库并灌入向量库。用户要求刷新、重建、重新灌库或切换知识库目录后使用。",
        args_schema={
            "type": "object",
            "properties": {"knowledge_dir": {"type": "string", "description": "可选的新知识库目录。为空时使用当前用户设置里的知识库目录。"}},
            "required": [],
        },
        function=rebuild_knowledge_base,
        display_name="重建知识库",
    ),
    BuiltinToolDefinition(
        name="search_knowledge",
        description=(
            "全库联合搜索: 在当前用户知识库中同时做文件名/路径关键词匹配、全文内容匹配,并可选语义搜索。"
            "适合用户要找某个文件、确认哪些文件包含关键词、或不知道路径但记得文件名/主题时使用。"
            "如果只需要完整列出目录树和所有文件路径,请使用 list_knowledge_files;如果已经要回答正文内容,请使用 get_knowledge_context。"
        ),
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "文件名、路径关键词、正文关键词或语义描述文本。"},
                "fulltext": {"type": "boolean", "description": "是否启用全文内容搜索,默认 true。"},
                "semantic": {"type": "boolean", "description": "是否启用语义搜索,默认 false。"},
            },
            "required": ["query"],
        },
        function=search_knowledge,
        display_name="全库联合搜索",
    ),
    BuiltinToolDefinition(
        name="save_uploaded_attachment_to_knowledge",
        description="把当前会话中用户上传的附件复制到当前 active 知识库,并可立即灌库。仅当用户明确要求长期保存上传附件时使用。",
        args_schema={
            "type": "object",
            "properties": {
                "attachment": {"type": "string", "description": "可选。attachment_id、完整文件名或文件名关键词。"},
                "target_path": {"type": "string", "description": "可选。保存到知识库内的相对路径。"},
                "conflict_strategy": {"type": "string", "description": "同名冲突策略: rename、overwrite 或 skip。默认 rename。"},
                "ingest": {"type": "boolean", "description": "是否保存后立即灌库。默认 true。"},
            },
            "required": [],
        },
        function=save_uploaded_attachment_to_knowledge,
        display_name="附件存入知识库",
    ),
    BuiltinToolDefinition(
        name="get_knowledge_file_url",
        description="获取知识库中本地文件的浏览器可访问 URL。返回的 URL 可用于 Markdown 图片或链接,在回复中直接引用知识库文件。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件相对于知识库根目录的路径。例如 images/diagram.png。"},
            },
            "required": ["path"],
        },
        function=get_knowledge_file_url,
        display_name="获取文件URL",
    ),
]

FILE_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_current_viewing_document",
        description="获取当前用户在 editor 前端正在观看的文档基本信息;如需正文请继续调用 read_knowledge_file。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=get_current_viewing_document,
        display_name="获取当前文档",
    ),
    BuiltinToolDefinition(
        name="list_knowledge_files",
        description=(
            "列出当前用户知识库的完整文件树,返回所有文件和文件夹的路径、类型和修改时间。"
            "适合需要浏览目录结构、获得可传给 read_knowledge_file 的准确路径、或全面盘点文件数量时使用。"
            "它不会按关键词过滤;如果用户要按文件名、路径或正文关键词搜索,请使用 search_knowledge。"
        ),
        args_schema={"type": "object", "properties": {}, "required": []},
        function=list_knowledge_files,
        display_name="列出文件",
    ),
    BuiltinToolDefinition(
        name="read_knowledge_file",
        description=(
            "读取知识库中指定纯文本、Markdown、代码等文本文件的正文内容。"
            "这是知识库文本文件正文读取的专用入口；如果用户已经给出准确 path, 直接用该 path 读取, 不需要先列目录。"
            "PDF、图片、Office 文档、表格、扫描件等已灌库的多模态/二进制文档不要用本工具, 必须改用 read_multimodal_file_info。"
            "不要为了读取知识库文档正文而调用 run_terminal_command、get_knowledge_file_url、download_file 或 Python 库自行解析源文件。"
        ),
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件相对于知识库根目录的路径。"}},
            "required": ["path"],
        },
        function=read_knowledge_file,
        display_name="阅读文件",
    ),
    BuiltinToolDefinition(
        name="read_multimodal_file_info",
        description=(
            "读取已灌库多模态/二进制文档的结构化 JSON 提取结果。"
            "PDF、图片、扫描件、Word、PPT、Excel、表格等文件要用本工具获取内容、章节、OCR、元数据和抽取文本。"
            "这是多模态知识库文档内容读取的专用入口；不要调用 run_terminal_command、get_knowledge_file_url、download_file 或 Python 库自行解析源文件。"
            "生成文档可视化、摘要或问答时, 应基于本工具返回的 JSON 结构化结果。"
        ),
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件相对于当前知识库根目录的路径。"}},
            "required": ["path"],
        },
        function=read_multimodal_file_info,
        display_name="读取多模态文件信息",
    ),
    BuiltinToolDefinition(
        name="write_knowledge_file",
        description="在知识库中创建新文件或覆盖已有文件。用于生成文档、笔记、代码等文本文件。",
        args_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件相对于知识库根目录的路径。"},
                "content": {"type": "string", "description": "要写入的完整文件内容。"},
            },
            "required": ["path", "content"],
        },
        function=write_knowledge_file,
        display_name="创作文件",
    ),
    BuiltinToolDefinition(
        name="show_markdown_html",
        description=(
            "Display a generated Markdown/document HTML visualization in the editor front-end. "
            "Use this only after you have produced the final complete HTML for the current document visualization. "
            "The tool saves the HTML under runtime/visualizations, returns the local path and URL, "
            "and automatically triggers the front-end iframe mount. For multimodal documents, first read the JSON "
            "extraction result with read_multimodal_file_info and build the HTML from that structured result."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Visualization title shown in the front-end panel."},
                "html": {"type": "string", "description": "Complete standalone HTML document or valid HTML fragment."},
                "source_path": {"type": "string", "description": "Optional source document path in the knowledge library."},
                "filename": {"type": "string", "description": "Optional preferred HTML filename; it will be sanitized and timestamped."},
            },
            "required": ["title", "html"],
        },
        function=show_markdown_html,
        display_name="展示Markdown-HTML",
    ),
    BuiltinToolDefinition(
        name="delete_knowledge_file",
        description="删除知识库中的文件或文件夹。删除文件夹会递归删除其下所有内容,请谨慎使用。",
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件或文件夹相对于知识库根目录的路径。"}},
            "required": ["path"],
        },
        function=delete_knowledge_file,
        display_name="删除文件",
    ),
    BuiltinToolDefinition(
        name="rename_knowledge_file",
        description="重命名或移动知识库中的文件/文件夹。可以只改文件名,也可以移动到其他目录。",
        args_schema={
            "type": "object",
            "properties": {
                "source_path": {"type": "string", "description": "文件/文件夹的当前相对路径。"},
                "target_path": {"type": "string", "description": "新的相对路径。"},
            },
            "required": ["source_path", "target_path"],
        },
        function=rename_knowledge_file,
        display_name="重命名文件",
    ),
    BuiltinToolDefinition(
        name="create_knowledge_folder",
        description="在知识库中创建新文件夹(目录)。用于组织文件结构。",
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件夹相对于知识库根目录的路径。"}},
            "required": ["path"],
        },
        function=create_knowledge_folder,
        display_name="创建文件夹",
    ),
]

TASK_LIST_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_task_list_status",
        description=(
            "Read the current session task list without changing it. "
            "Use this when you need to confirm task list status, item ids, current item, "
            "or completion summaries before continuing long-running work."
        ),
        args_schema={"type": "object", "properties": {}, "required": []},
        function=get_task_list_status,
        display_name="获取任务列表状态",
    ),
    BuiltinToolDefinition(
        name="create_task_list",
        description=(
            "Create a persistent session task list for execution work that must be completed in ordered steps. "
            "Use it for coding, debugging, file operations, document processing, data analysis, tool-chain work, "
            "or any user request that needs multiple concrete steps before the final result. "
            "Task List is only for this Agent session's execution progress; it is completely unrelated to user Todo items. "
            "Do not use it for direct single-step answers or for creating, editing, completing, or deleting long-term user Todo items. "
            "After creating it, continue working toward this list until finish_task_list is called."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the task list."},
                "items": {
                    "type": "array",
                    "description": "Concrete task items to complete. Each item should be a short actionable string.",
                },
            },
            "required": ["items"],
        },
        function=create_task_list,
        display_name="创建任务列表",
    ),
    BuiltinToolDefinition(
        name="complete_task_list_item",
        description=(
            "Mark one task list item complete. You must call this after actually completing an item, "
            "and include a concrete completion summary before starting another item."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "The task list item id."},
                "completion_summary": {
                    "type": "string",
                    "description": "A concise factual summary of what was completed for this item.",
                },
                "next_item_id": {
                    "type": "string",
                    "description": "Optional id of the next item to mark in progress.",
                },
            },
            "required": ["item_id", "completion_summary"],
        },
        function=complete_task_list_item,
        display_name="完成任务项",
    ),
    BuiltinToolDefinition(
        name="finish_task_list",
        description=(
            "End the active session task list after the long-running task is complete. "
            "Do not call this until no useful task list work remains."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "final_summary": {"type": "string", "description": "Optional overall summary for the finished list."},
            },
            "required": [],
        },
        function=finish_task_list,
        display_name="完成任务列表",
    ),
]

TODO_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="list_todos",
        description="列出当前用户的所有待办事项。每行包含编号、ID(todo_xxx)、完成状态和截止日期。后续切换/编辑/删除时需要从输出中提取该 ID。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=list_todos,
        display_name="列出待办",
    ),
    BuiltinToolDefinition(
        name="add_todo",
        description="新增一条待办事项。可指定可选的截止日期。返回值包含新待办的 ID(todo_xxx),可供后续切换/编辑/删除使用。",
        args_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "待办事项的文字描述。"},
                "due_date": {"type": "string", "description": "可选截止日期,格式 YYYY-MM-DD。"},
            },
            "required": ["text"],
        },
        function=add_todo,
        display_name="新增待办",
    ),
    BuiltinToolDefinition(
        name="toggle_todo",
        description="切换待办事项的完成状态(已完成↔未完成)。需要 todo_id。",
        args_schema={
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "待办的唯一 ID,可通过 list_todos 获取。"},
            },
            "required": ["todo_id"],
        },
        function=toggle_todo,
        display_name="切换待办状态",
    ),
    BuiltinToolDefinition(
        name="edit_todo",
        description="编辑待办事项的文本或截止日期。只传需要修改的字段。不传 text 则保留原文本。",
        args_schema={
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "待办的唯一 ID,可通过 list_todos 获取。"},
                "text": {"type": "string", "description": "新的待办文本,留空则不修改文本。"},
                "due_date": {"type": "string", "description": "新的截止日期(YYYY-MM-DD),传入空字符串清除截止日期,不传则不修改。"},
            },
            "required": ["todo_id"],
        },
        function=edit_todo,
        display_name="编辑待办",
    ),
    BuiltinToolDefinition(
        name="delete_todo",
        description="删除指定的待办事项。需要 todo_id。",
        args_schema={
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "待办的唯一 ID,可通过 list_todos 获取。"},
            },
            "required": ["todo_id"],
        },
        function=delete_todo,
        display_name="删除待办",
    ),
]

WEB_SEARCH_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="web_search",
        description="通过 DuckDuckGo 搜索互联网,返回格式化搜索结果列表(标题+URL+摘要)。尽量少次搜索,每次搜索要覆盖全面——宁可一次搜完,也不要分多次搜。本工具仅返回文本结果,无法搜索图片。如需搜索图片请使用 web_image_search 工具。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词。尽量精确、全面,一次覆盖所有可能的关键词。"},
                "max_results": {"type": "integer", "description": "最大返回结果数,不传则使用用户的配置值。"},
                "region": {"type": "string", "description": "搜索区域代码,默认 cn-zh。"},
                "time_range": {"type": "string", "description": "时间范围筛选。d/w/m/y。留空表示不限时间。"},
            },
            "required": ["query"],
        },
        function=web_search,
        display_name="联网搜索",
    ),
    BuiltinToolDefinition(
        name="web_image_search",
        description="通过 DuckDuckGo 搜索图片,返回图片 URL 列表,每个结果附带标题、图片地址、缩略图地址和来源页面 URL。搜索到图片后直接用 Markdown 热链接展示,不要调用 download_file 下载。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词。尽量精确、全面,一次覆盖所有可能的关键词。"},
                "max_results": {"type": "integer", "description": "最大返回结果数,不传则使用用户的配置值。"},
                "region": {"type": "string", "description": "搜索区域代码,默认 cn-zh。"},
            },
            "required": ["query"],
        },
        function=web_image_search,
        display_name="联网搜索图片",
    ),
]

BUILTIN_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = (
    UTILITY_TOOL_DEFINITIONS
    + GIT_TOOL_DEFINITIONS
    + SKILL_TOOL_DEFINITIONS
    + MEMORY_TOOL_DEFINITIONS
    + KNOWLEDGE_TOOL_DEFINITIONS
    + FILE_TOOL_DEFINITIONS
    + TASK_LIST_TOOL_DEFINITIONS
    + TODO_TOOL_DEFINITIONS
    + WEB_SEARCH_TOOL_DEFINITIONS
)
