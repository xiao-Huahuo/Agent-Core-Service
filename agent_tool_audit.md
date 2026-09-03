# Agent 全工具验收报告

## 结论（真实 API 终验）

> 2026-09-03 纠正完成：全部工具均由真实 FastAPI lifespan 下的 `/agent/stream` 调用，模型实际生成 tool call；未使用 Service mock、HTTP 拦截或直接函数调用作为通过证据。

- 正式原生注册表：107 个工具，真实 API 通过 107/107，失败 0，遗漏 0。
- 每个工具首次通过后写入持久账本并永久跳过；后续仅复测失败项。
- 审计用户模型密钥已清空，识图/DSH/联网开关已关闭，120 个临时审计会话已删除。
- 工具实现：107/107 均有直接成功路径测试；无工具因导入、参数、路由、服务适配或返回序列化错误而不可用。
- MCP：动态工具数量取决于用户配置的外部 server，已验证发现、注册、命名隔离和同步执行完整链路。
- 实际界面：Chromium 单 worker 下 Tool/Chat 两种模式均通过，`list_available_tools` 的开始态、shimmer、图标、完成态同位更新和页面错误检查全部通过。
- 模型 API：已按用户授权调用；密钥仅临时保存到隔离审计用户设置，验收后已清空，未写入仓库、日志或报告。

## 逐工具清单

以下每一项均同时满足：注册表可见、模型经 `/agent/stream` 产生对应 tool call、收到未标记 failed 的 `tool_call_end`，且 case 指定的业务成功契约成立。

### 通用与 Git（15）

- [x] `list_available_tools`
- [x] `read_tool_result`
- [x] `run_terminal_command`
- [x] `download_file`
- [x] `git_status`
- [x] `git_diff`
- [x] `git_history`
- [x] `git_init_repository`
- [x] `git_restore_files`
- [x] `git_commit_files`
- [x] `git_push_branch`
- [x] `git_create_branch`
- [x] `git_add_remote`
- [x] `git_switch_branch`
- [x] `git_pull_branch`

### Skill、记忆与知识检索（13）

- [x] `list_skills`
- [x] `use_skill`
- [x] `get_long_term_memory`
- [x] `write_long_term_memory`
- [x] `write_long_term_rule`
- [x] `delete_long_term_memory`
- [x] `delete_long_term_rule`
- [x] `read_session_attachment`
- [x] `get_knowledge_context`
- [x] `search_knowledge`
- [x] `save_uploaded_attachment_to_knowledge`
- [x] `understand_image`
- [x] `get_knowledge_file_url`

### 图书馆与知识文件（15）

- [x] `list_library_items`
- [x] `list_library_tags`
- [x] `add_library_book`
- [x] `add_library_collection`
- [x] `update_library_item`
- [x] `remove_library_item`
- [x] `get_current_viewing_document`
- [x] `list_knowledge_files`
- [x] `read_knowledge_file`
- [x] `patch_knowledge_file`
- [x] `write_knowledge_file`
- [x] `show_markdown_html`
- [x] `delete_knowledge_file`
- [x] `rename_knowledge_file`
- [x] `create_knowledge_folder`

### 任务、子 Agent、待办与联网（15）

- [x] `get_task_list_status`
- [x] `create_task_list`
- [x] `complete_task_list_item`
- [x] `finish_task_list`
- [x] `spawn_child_agent`
- [x] `wait_for_child_agents`
- [x] `continue_child_agent`
- [x] `list_todos`
- [x] `add_todo`
- [x] `add_automation`
- [x] `toggle_todo`
- [x] `edit_todo`
- [x] `delete_todo`
- [x] `web_search`
- [x] `web_image_search`

### 知识任务与图谱（16）

- [x] `get_selected_knowledge_files`
- [x] `ingest_selected_knowledge_files`
- [x] `ingest_all_knowledge_files`
- [x] `get_knowledge_job_status`
- [x] `cancel_knowledge_job`
- [x] `retry_failed_knowledge_files`
- [x] `get_knowledge_file_status`
- [x] `list_knowledge_trash`
- [x] `restore_knowledge_file`
- [x] `permanently_delete_knowledge_trash`
- [x] `extract_selected_file_graphs`
- [x] `extract_all_file_graphs`
- [x] `search_knowledge_graph_nodes`
- [x] `find_knowledge_graph_paths`
- [x] `delete_file_graph`
- [x] `retry_failed_graph_extraction`

### 用户 Skill 与反馈（12）

- [x] `get_custom_skill`
- [x] `create_custom_skill`
- [x] `update_custom_skill`
- [x] `delete_custom_skill`
- [x] `validate_custom_skill`
- [x] `test_custom_skill`
- [x] `set_skill_enabled`
- [x] `list_user_feedback`
- [x] `get_user_feedback`
- [x] `create_user_feedback`
- [x] `update_user_feedback`
- [x] `delete_user_feedback`

### 图书条目、组件与收藏（10）

- [x] `get_library_item`
- [x] `list_components`
- [x] `get_component`
- [x] `create_component`
- [x] `update_component`
- [x] `delete_component`
- [x] `validate_component`
- [x] `list_favorites`
- [x] `add_favorite`
- [x] `remove_favorite`

### 智能表格（11）

- [x] `list_smart_forms`
- [x] `create_smart_form`
- [x] `get_smart_form`
- [x] `get_smart_form_schema`
- [x] `update_smart_form`
- [x] `patch_smart_form_rows`
- [x] `get_smart_form_literature`
- [x] `export_smart_form`
- [x] `import_smart_form`
- [x] `preview_smart_form_fill`
- [x] `fill_smart_form_cells`

## 测试证据

所有批次均单进程、单 worker、严格串行：

- `tests/test_agent_tools_complete.py`：13 passed（补齐 74 个此前缺少直接成功路径的工具，并验证 107 个 schema）。
- `tests/test_extended_builtin_tools.py`：8 passed（31 个扩展工具业务闭环）。
- `tests/test_session_attachment_vision.py`：5 passed（附件续读、本地识图；仅出现 PaddleOCR 参数提示警告）。
- `tests/test_agent_tool_registry.py`：3 passed（最终注册表与四库搜索执行器）。
- `tests/test_mcp_tool_registry.py`：2 passed（MCP 发现、注册、执行）。
- `tests/test_mcp_client.py`：2 passed（MCP 客户端协议）。
- 前端 `vite build`：通过。
- `agent-tool-preview.spec.ts` Chromium：2 passed（Tool/Chat 两种实际界面模式）。
- `tests/live_agent_api_tool_audit.py`：真实服务器、真实模型、真实 SSE 调用与断点账本。
- `tests/live_agent_api_tool_cases.json`：107 个工具的参数、前置状态和成功契约。
- 真实 API 最终状态：`registered=107 passed=107 failed=0 missing=0`。

## 修复内容

- 修正 MCP 注册测试中已经移除的示例工具 `echo_text` 断言，改为正式稳定工具 `list_available_tools`。
- Agent 工具界面冒烟改用正式注册的 `list_available_tools`，不再伪造已移除的 `get_current_time`。
- 删除已无产品实现对应的流式光标/逐词动画断言，并把 shimmer 检查更新为当前 `::after` 扫光实现。
- 工具业务 Service 显式注入 `ToolRuntimeState`，彻底移除工具线程对 REST 请求 ContextVar 的反向依赖，修复图书馆/Git/知识任务/业务/智能表格工具 503。
- 联网搜索允许未配置代理时直接连接 DDGS；配置代理时仍按用户值使用。
- 修复 DSH 内置包裁残的 OpenTelemetry Core/Resources 依赖、Windows 长路径解压、修复失败状态伪装 ready、异常 Runtime 租约泄漏。
- 修复子 Agent 快照被会话 plan 归一化丢失，并支持从持久化 tool/event 消息冷恢复旧会话。

## 未完成项

无。外部 MCP server 的业务正确性由各 server 自身负责；本项目可控的 MCP 发现、注册与调用适配层已通过协议测试。
