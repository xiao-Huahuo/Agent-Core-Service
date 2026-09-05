# Notes: Agent 大块输出与滚动性能

## Hypotheses
- provider本身以数百或数千字符chunk返回，50ms草稿层只能原样提交。
- SSE网络层仍有缓冲或心跳期间只产生reasoning/tool事件。
- 完成长对话的所有Markdown和工具结果都在同一滚动容器内参与layout/paint。
- 折叠工具结果只把高度压成0,但正文DOM仍挂载。
- 每次scroll同步读取scrollHeight并更新Pinia/父组件。

## Evidence
- 最新真实长回答的`streamed_content_chars == final_content_chars`,且`reconciled_content_chars == 0`,排除终态补齐复发。
- 前端正文和thinking此前固定每50ms提交一次,会把快速token合成明显大块;已改为每动画帧提交。
- ToolCallInline和ChildAgentEventInline折叠时仍完整创建解析后的大结果DOM;已改为展开时才挂载。
- 所有历史Markdown/工具消息原先持续参与布局与绘制;已增加Chromium原生`content-visibility:auto`及记忆式固有尺寸。
- scroll处理原先每个事件同步读取布局;已按requestAnimationFrame合并为每帧一次。
- provider终态诊断新增content chunk数量与最大chunk字符数,用于区分provider整块与客户端批量。
- 真实页面冒烟：60个5ms间隔单字符事件产生53次可见更新,单次最大增量2字符；24轮超长历史往返滚动121帧,最大帧间隔18.4ms且无Long Task；6个收起工具正文均未挂载。

---

# Notes: 子 Agent 终态提示与 DeepSeek 400

## 初步证据
- `ChildAgentManager._emit` 会把每次生命周期事件放入 session 队列，同时回调持久化同一事件。
- `GraphRunnerMixin` 在活动 SSE 中排空 session 事件队列并推给前端。
- 前端 `checkChildAgentsForWakeup` 另行轮询 `/children`，在主流结束后自动发起带 `child_agent_event` 的新 Agent Turn。
- 当前前端去重集合 `seenChildStatus` 只存在于单个 store 内存，无法作为跨窗口/重载的幂等依据。
- 当前 `DeepSeekChatOpenAI` 已尝试在 `_get_request_payload` 中回填 `reasoning_content`，但测试未覆盖 tool-call 续轮。

## 已确认根因
- 多窗口或多个 session store 可同时观察到同一个活动态→终态变化；原实现只有各自内存中的 `seenChildStatus`，没有服务端原子幂等点。
- 主窗口已通过 SSE 显示终态时，镜像窗口的轮询状态不会自动消费该终态，因此仍可能额外触发一次唤醒。
- `DeepSeekChatOpenAI` 仅在模型名以 `deepseek` 开头时启用；`unsloth/deepseek-v3.2` 等命名空间模型落入普通 `ChatOpenAI`，工具续轮丢失必需的 `reasoning_content`。

## 修复策略
- `ChildAgentManager` 按 `run_id + Turn 编号` 原子领取终态唤醒；DSH 追问递增 Turn 后可重新领取。
- 活动 SSE 渲染终态时也领取一次，阻止其他窗口轮询重复唤醒。
- 前端轮询唤醒仅在 claim 成功后发送；终态后的新运行态重新进入监测。
- DeepSeek 适配器按模型路径段识别直连名和命名空间名。

## 最终验证
- 子 Agent 管理器：12 passed；并发 claim 结果固定为一真一假，DSH 新 Turn 可再次领取。
- 调度器：17 passed；真实 tool-call 序列化含 `reasoning_content`。
- 前端 Chat/API：26 + 2 passed。
- Chromium 实际 Agent 页面：2 created、2 completed、2 claim，视觉检查完成。
- 宽回归 `test_agent_core_service.py`：60 passed、10 个无关既有失败。
- 全量 TypeScript 检查仍有无关既有错误；过滤复检确认本次前端文件没有类型错误，定向测试均通过。

---

# Notes: Agent 历史重复

## 用户可见症状
- 会话“子Agent结果等待中”重载后，同一 `wait_for_child_agents` 空结果和“已收到 3/4”回答被连续恢复多次。
- 重复单元同时包含思考、工具等待行与回答，需区分真实多轮保存和前端重复渲染。

## 数据库取证
- session_id=`sess_01766784eac443e898f44e021be2553c`，原始 926 行。
- assistant=469、tool=437、user=10、system=10。
- 空等待 418 次，相同 3/4 回复 383 次；第 10 Turn 有 339 assistant + 339 tool。

## 最终实现与验证
- session 级等待跨越自动唤醒产生的新 parent run。
- 当前用户 Turn 累计 4 次工具调用后解绑工具。
- 历史 API 使用语义投影，原始事件继续供上下文/观测读取。
- 旧会话只读投影 926 → 69；不迁移、不删除用户原始数据。
- Python：2 + 13 + 22 passed；Vitest：27 passed；Chromium 重载：1 passed。

---

# Notes: Agent 对话来源、结果块布局与库菜单

## 待核对链路
- 来源区块：来源点击事件如何从消息组件传递到编辑工作区，以及现有主区/右侧区打开参数。
- 四类内容块：Agent 消息元数据如何合并挂载文件、图书馆、文献阅读和组件库结果；搜索页分裂模式使用的布局结构。
- 库菜单：按钮、二级菜单宿主及现有 click-outside 模式。

## 验证证据
- `KnowledgeSources.openSource` 对本地节点调用 `setMainView('editor') + selectFile`，直接导致离开Agent主区。
- `workspace.openEditorSidebar` 已是搜索页预览和Agent页挂载文件共用的右侧编辑区入口。
- `AgentSearchResultBlocks` 当前将所有source放进同一个 `auto-fit` grid；`SearchPage`分裂模式则按source渲染独立section及原生布局。
- `ActivityBar` 的 `activeMenu` 没有document级外部点击监听，现有 `closeActivityMenu` 只覆盖菜单项导航且management模式刻意不关闭。
- 失败基线：新增的来源侧栏、四库分行、外部点击用例各失败1项，其余17项通过。
- 实现后回归：3个测试文件共21项全部通过。
- Chromium实际界面：来源打开后右侧编辑区可见且Agent主区保留；四个source section顺序和纵向几何正确；库菜单点击顶栏后隐藏，2项通过。
- 桌面截图视觉检查：四类原生卡片独立分段，没有混排和横向溢出。
- `npm run build-only`通过；全量`vue-tsc --build`仅报告仓库既有错误，本次文件未出现在错误列表。
- 定向ESLint为0错误；既有E2E的`force: true`保留1条无关warning。
- Playwright复用了PID 12816的既有5173 Vite服务；该Node进程累计CPU时间8分钟以上，并非本轮短暂冒烟创建，故保留运行。

---

# Notes: 四库 K 引用侧栏导航

## 已确认链路
- `search_knowledge` 已把四库原生结果写入 `citation_map[K#].search_result`，历史消息恢复时 `asSourceMap` 会保留该字段。
- 挂载结果块已通过 `workspace.openAgentSearchResult`/`openSearchResultSidebar` 支持四库原生导航。
- 正文 `[K#]` 当前只把 `source_uri` 交给本地文件/网页回调，丢失 `search_result`，因此非文件库点击无响应。
- 底部 `KnowledgeSources` 同样只接收 URI；本地文件侧栏修复已存在，但尚未消费四库 `search_result`。

## 修复边界
- 正文与来源区优先使用完整 `search_result` 打开共享右侧侧栏。
- 无 `search_result` 的旧引用保留附件预览、网页打开和本地文件兼容路径。

## 回归结果
- 失败基线：正文四库 K 引用测试得到 0 次侧栏调用，准确复现缺陷。
- 修复后：`MarkdownContent.spec.ts` 13项通过，`FinalTurnSummary.spec.ts` 4项通过。
- 图书馆测试使用 HTTP locator，确认 `search_result` 优先于普通网页跳转。
- 后端四库注册回归：`test_agent_tool_registry.py` 3项通过。
- 历史消息引用恢复：`MessageListAttachmentCitation.spec.ts` 3项通过。
- 生产构建：`npm run build-only`通过；定向ESLint 0错误。
- Chromium实际界面：依次点击 `[K1]` 至 `[K4]`，四类侧栏均正确显示且Agent主区保留，1项通过。
- 视觉检查：1440×900暗色界面的文献侧栏完整可见，标题、字段/内容切换和关闭入口无截断。
# Notes: Agent 全工具可用性审计（2026-09-02）

## 验收口径
- 清单来源：运行时正式工具注册链路。
- 可用标准：schema 可构建、executor 可路由、参数校验正确、成功路径返回规范结果；外部依赖使用受控替身，另选少量安全工具做真实 Agent 冒烟。
- 资源约束：单进程、单 worker、按模块串行，无全量并发测试。

## 初始状态
- 工作区既有未提交文件：`editor/e2e/wiki-links.spec.ts`，本任务不触碰。
- 临时模型 key 仅在确有必要时通过进程环境注入，不落盘。

## 最终发现
- 正式原生注册表共 107 个工具，107 个均可转换为 LangChain StructuredTool。
- 新增定向测试覆盖此前缺少直接成功路径的 74 个工具；既有扩展闭环覆盖 31 个；附件续读与识图覆盖余下 2 个。
- MCP 动态层完成发现、注册、命名隔离、调用和结果转换测试。
- 首个基线失败来自 MCP 测试残留 `echo_text` 断言，属于测试失真；已改为正式 `list_available_tools`。
- 浏览器测试残留已移除的 `get_current_time`、不存在的 stream DOM class 和旧 shimmer CSS 断言；均已对齐当前实现。
- 该条仅描述初始单元审计；真实 API 纠正轮已按授权使用模型，并在结束后清空隔离审计用户凭据。

## 最终验证
- 后端定向批次：13 + 8 + 5 + 3 + 2 + 2，全部通过。
- Vite 生产构建通过。
- Chromium 单 worker Tool/Chat 两种模式：2 passed；截图人工检查工具 pending 行可见且布局正常。

---
# Notes: Agent 全工具真实 API 验收（纠正轮）

## 验收红线
- 禁止 monkeypatch Service、HTTP route fulfil、直接调用 definition.function 作为通过证据。
- 每个工具必须由真实 `/agent/stream` 模型循环调用并出现成功 `tool_call_end`。
- 已通过工具写入账本后不再发送给模型复测。

## 已知真实失败
- 用户报告：经 API 调用图书馆工具得到 HTTP 503。
- 高概率路径：工具线程调用 `api.rest.deps._require_library_service()`，但 request-scoped `ApplicationServices` ContextVar 未传播或未绑定。

## 最终 API 结果
- `registered=107 passed=107 failed=0 missing=0`。
- 真实共享根因：SSE 图线程无法继承 REST ContextVar；改为 ToolRuntimeState 显式 Service 注入。
- DSH 连续根因：内置 OpenTelemetry Core/Resources 半包、MAX_PATH 解压、修复失败状态被旧安装掩盖、失败句柄租约未释放、子 Agent 快照被 plan 归一化丢失。
- 联网工具根因：无代理配置被硬拒绝；改为代理可选后真实网页与图片搜索均返回 Citation。
- 最后单独执行本地识图，真实返回视觉描述；未与其他高内存测试并行。
- 清理：审计 key 已清空，功能开关复原，120 个审计会话删除。

---

# Notes: 组件库绘图脚本类型

## 现有链路
- 组件源文件位于活动知识库 `.mw/components/<tag>/`，标签由一级目录表示。
- `ComponentPreview` 只支持 Vue SFC/HTML；普通上传会在持久化前强制编译。
- 图书馆已有 `LibraryCoverUploader` 和 `/library/assets/cover`，封面资产由 `LibraryAsset` 表与运行时资产文件正式持久化。
- 组件库目前无扩展元数据表，需为脚本语言与可选封面关联新增正式模型/迁移。

## 实施边界
- 绘图脚本必须有组件名、源码和脚本语言；图片为可选。
- 脚本以 `.script` 文件保存，API 明确返回 `source_format: script`，不使用 Vue/HTML 内容推断。
- 卡片封面优先使用已持久资产 URL；无资产时使用组件名文字封面。

## 最终验证
- 后端：组件服务、schema、REST、gRPC 与 Alembic 迁移共 18 项通过。
- 前端：API、卡片、详情、上传表单和共享封面上传共 36 项通过，定向 ESLint 通过，Vite 构建通过。
- 真实 API：经 5174 Vite 代理调用 8003 隔离后端，成功创建 2 条 `source_format=script` 记录；自定义/内置语言均持久化，封面状态为一无一有。
- 视觉：1440 桌面为左代码右图片；768 平板和 480 移动尺寸字段、图片区、标签、模式按钮与提交操作均可见。
- 清理：8003、5174、50052 端口已关闭，隔离验收数据已删除，仅保留截图证据。

---
