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
    calculate,
    create_knowledge_folder,
    delete_knowledge_file,
    delete_long_term_memory,
    delete_long_term_rule,
    delete_todo,
    download_file,
    echo_text,
    edit_todo,
    generate_uuid,
    get_current_time,
    get_current_utc_time,
    get_current_viewing_document,
    get_knowledge_context,
    get_knowledge_file_url,
    get_long_term_memory,
    json_parse,
    json_pick,
    list_builtin_tools,
    list_knowledge_files,
    list_todos,
    read_knowledge_file,
    read_multimodal_file_info,
    rebuild_knowledge_base,
    rename_knowledge_file,
    run_terminal_command,
    save_uploaded_attachment_to_knowledge,
    search_knowledge,
    text_stats,
    toggle_todo,
    update_exploration_state,
    web_search,
    write_knowledge_file,
    write_long_term_memory,
    write_long_term_rule,
)

UTILITY_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="get_current_utc_time",
        description="获取当前 UTC 时间。当用户询问当前时间或需要时间戳时使用。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=get_current_utc_time,
        display_name="获取UTC时间",
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
        name="echo_text",
        description="原样返回输入文本。用于测试工具调用链路是否正常。",
        args_schema={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "需要原样返回的文本。"}},
            "required": ["text"],
        },
        function=echo_text,
        display_name="回显文本",
    ),
    BuiltinToolDefinition(
        name="generate_uuid",
        description="生成随机 UUID4 字符串,用于临时标识或调试标识。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=generate_uuid,
        display_name="生成UUID",
    ),
    BuiltinToolDefinition(
        name="calculate",
        description="安全计算基础数学表达式,只支持数字和基础算术运算。",
        args_schema={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "数学表达式,例如 (1 + 2) * 3。"}},
            "required": ["expression"],
        },
        function=calculate,
        display_name="数学计算",
    ),
    BuiltinToolDefinition(
        name="json_parse",
        description="解析 JSON 字符串,返回结构化描述(字段列表/元素数量等),不返回原始 JSON。",
        args_schema={
            "type": "object",
            "properties": {"json_text": {"type": "string", "description": "需要解析的 JSON 字符串。"}},
            "required": ["json_text"],
        },
        function=json_parse,
        display_name="解析JSON",
    ),
    BuiltinToolDefinition(
        name="json_pick",
        description="从 JSON 字符串中按点分路径读取字段值,返回人类可读的值描述。",
        args_schema={
            "type": "object",
            "properties": {
                "json_text": {"type": "string", "description": "需要读取的 JSON 字符串。"},
                "path": {"type": "string", "description": "点分路径,例如 user.name 或 items.0.title。"},
            },
            "required": ["json_text", "path"],
        },
        function=json_pick,
        display_name="提取JSON字段",
    ),
    BuiltinToolDefinition(
        name="text_stats",
        description="统计文本字符数、非空白字符数、行数、词数和粗略 token 数,返回人类可读的统计结果。",
        args_schema={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "需要统计的文本。"}},
            "required": ["text"],
        },
        function=text_stats,
        display_name="文本统计",
    ),
    BuiltinToolDefinition(
        name="list_builtin_tools",
        description="列出当前注册的全部内置工具名称和描述。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=list_builtin_tools,
        display_name="列出工具",
    ),
    BuiltinToolDefinition(
        name="run_terminal_command",
        description=(
            "在项目终端沙盒中执行一个或多个结构化指令段。必须传 shell、segments、cwd; "
            "禁止传整条 shell 字符串。支持 external_program 外部程序段,以及 pwd/ls/dir/cat/type/head/tail/stat/wc "
            "等内部读取指令和 write/append/touch/mkdir/rm/mv 等内部写入指令。沙盒模式允许内部读取穿透目录外,"
            "但写入和外部程序执行仍限制在终端工作区内。完全访问模式下还额外支持 kill/taskkill 杀进程,"
            "且内部指令参数限制大幅放宽(如 rm -rf、mkdir -p、多文件 cat/stat/wc、批量 touch 等)。"
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
        description="检索知识库中的相关片段,用于回答事实性、说明性和文档型问题。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "需要检索的知识查询文本。"},
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
        description="在用户知识库中联合搜索文件,支持文件名匹配、全文内容匹配和语义搜索。当用户需要根据关键词或语义描述在知识库中查找特定文件时使用。",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或语义描述文本。"},
                "fulltext": {"type": "boolean", "description": "是否启用全文内容搜索,默认 true。"},
                "semantic": {"type": "boolean", "description": "是否启用语义搜索,默认 false。"},
            },
            "required": ["query"],
        },
        function=search_knowledge,
        display_name="搜索知识库",
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
        description="列出当前用户知识库的完整文件树,返回所有文件和文件夹的路径、类型和修改时间。",
        args_schema={"type": "object", "properties": {}, "required": []},
        function=list_knowledge_files,
        display_name="列出文件",
    ),
    BuiltinToolDefinition(
        name="read_knowledge_file",
        description="读取知识库中指定文本文件的内容。先调用 list_knowledge_files 查看文件列表,再读取感兴趣的文件。",
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
        description="读取已灌库的多模态文件结构化信息,返回标题、模态、元数据、章节列表和内容预览。",
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

STATE_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = [
    BuiltinToolDefinition(
        name="update_exploration_state",
        description="更新 Agent 自身的知识探索状态,记录已覆盖的主题、建议方向和是否信息充足,用于跨轮次追踪探索进度。",
        args_schema={
            "type": "object",
            "properties": {
                "covered": {"type": "string", "description": "逗号分隔的新增已覆盖主题。"},
                "suggested": {"type": "string", "description": "逗号分隔的建议继续探索方向。"},
                "sufficient": {"type": "string", "description": "当前信息是否足够回答用户问题,true 或 false。"},
                "hint": {"type": "string", "description": "给下一轮的一两句策略提示。"},
            },
            "required": [],
        },
        function=update_exploration_state,
        display_name="更新探索状态",
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
        description="通过 DuckDuckGo 搜索互联网,返回格式化搜索结果列表。尽量少次搜索,每次搜索要覆盖全面——宁可一次搜完,也不要分多次搜。",
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
]

BUILTIN_TOOL_DEFINITIONS: list[BuiltinToolDefinition] = (
    UTILITY_TOOL_DEFINITIONS
    + MEMORY_TOOL_DEFINITIONS
    + KNOWLEDGE_TOOL_DEFINITIONS
    + FILE_TOOL_DEFINITIONS
    + STATE_TOOL_DEFINITIONS
    + TODO_TOOL_DEFINITIONS
    + WEB_SEARCH_TOOL_DEFINITIONS
)
