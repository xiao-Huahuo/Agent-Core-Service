# CHANGE HISTORY

## 2026-05-17
- 修复 Obs 面板在工具模式下所有卡片数据不完整的问题: `useObsData.js` 中 `currentMessageTraces` 原来只取最后一条 assistant 消息的 trace, 在工具模式下每个图节点 (planner/agent/action/reflection) 各自一条 assistant 消息, 导致语言轨迹、节点执行时间线、工具轨迹和运行时路径都只展示最后一个节点的数据。改为从尾部向前扫描, 收集最后一条 user 消息之后的所有 assistant trace, 使语言轨迹/节点时间线/工具轨迹/运行时路径在工具模式下正确聚合整个轮次的数据。(对话模式行为不变)
- 修复 Obs 面板上下文拼装在流式过程中只显示用户 prompt 的问题: 后端 `agent_core.py` 的 `stream_session_prompt()` 在启动图执行前新增 `system_prompt` SSE 事件, 将 ContextBuilder 构建的完整系统提示 (含记忆索引、知识库索引、重要事实摘要、检索指标) 下发给前端; 前端 `chat.js` 接收该事件后将系统消息注入 `messages` 数组, `useObsData` 的 `contextAssembly` 和 `ragMetrics` 即可实时解析完整上下文拼装。
- 新增上下文镜像机制, 让 Obs 面板 Raw 视图与可读格式视图均展示模型收到的真实完整消息列表: 后端在 `runtime_context.py` 新增 `context_mirror_callback`, `model_decision.py` 在流式调用 LLM 前将 `[system_message, *state["messages"]]` 序列化并通过回调推送到 `agent_core.py` 的主循环, 作为 `context_mirror` SSE 事件下发; 前端 `chat.js` 存入 `contextMirror` ref, `useObsData.js` 的 `contextAssembly` 优先使用镜像消息构建可读格式视图 (回退到旧解析逻辑), `LanguageTraceCard.vue` 的 Raw 视图优先展示镜像 JSON。
- 修复长对话流式输出卡顿: 问题根因是每个 token (~30-60次/秒) 都直接写入响应式 `last.content`, 触发 `visibleMessages` 全量重算 (reduce 整个消息列表创建新对象)、模板全量重渲染和 vdom diff, 随消息累积导致 GC 压力持续增大。修复方案: `chat.js` 新增流式内容节流 (50ms 间隔), `updateStreamContent` 将最新内容存入非响应式缓冲, 按固定频率批量写入响应式对象, node/tool_calls/trace 等结构性字段仍立即写入; 流式中断/结束/异常时 `forceFlushContent` 确保最终内容不丢失。
- [x] 除了记忆机制,还应该有状态机制(status).状态由Agent自己来管理,作为Planner节点的参考依据和修改能力.
  - 同一个session不同对话拥有连续的状态机制,因此状态应该存到session.
  - Compress节点不影响状态,状态作为衔接压缩前和压缩后的衔接性的一个桥梁.
## 2026-05-16
- [x] 增加"Agent思考轨迹",展示agent在思考过程中的所有中间状态输出和工具调用,以免agent在思考中将对话框占用然后又清除来显示最终回答的问题.应该在对话框内有这样的效果:
  - 用户: 帮我查一下有没有海洋相关的知识,然后立一个待办.
  - Agent对话框:
    - 好的,先让我查一查海洋的知识库知识.                              (Planner节点的输出)
    - （agent调用了检索工具,并且展示了检索工具的输入和输出）
    - 很好,我得到了海洋的知识库知识.这些知识很有用.                    (Reflection节点的输出)
    - 接下来我准备使用待办工具来添加待办:                             (Planner节点的输出)
    - （调用待办工具,并展示待办工具的输入和输出）
    - 我已经完成了用户的任务,接下来进行最终回复.                       (Reflection节点的输出)
    - 好的,我已经帮你查到了海洋相关的知识,并且立了一个待办,内容是....          (最终回复)
  - 这样用户就能清楚地看到agent的思考过程,而不是在等待中觉得agent没有反应或者卡住了,也能让用户更有信任地使用agent,因为他们能看到agent在做什么.
- [x] 可观测面板,展示agent的决策过程,切换到可观测面板时对话面板不刷新且仍需继续接受后台信息,可以在对话时实时更新.以下几点需要同步化展示:
  - agent的LangGraph图以及当前所在节点,节点高亮,边切换也高亮
  - 节点执行轨迹和工具调用轨迹展示
  - 上下文拼装的内容与来源,不同来源的内容用不同颜色区分
  - 长期记忆召回+rerank结果前后对比+状态+知识库召回+摘要工具结果展示
  - 多级队列实时任务状态
  - RAG召回率,命中率和置信度等各项指标的本次数值展示和对话曲线图
  - 按时刻和模型的的token用量变化柱状-曲线图
  - 每次message的思考时间耗时折线图,点击一个耗时则放大并划分为每个步骤的耗时占比
  - agent超参数可视化展示
### 前端 - Obs 饼图重叠修复
- 调整 `console/src/components/dashboard/RagMetricsCard.vue` 的环形图配置: 收紧 donut 半径并下移图内标签文案,同时将三图并排布局改为可按断点换行的响应式网格,修复 Obs 面板窄宽度下饼状图图形与文字重叠的问题。
- 进一步调整 `console/src/components/dashboard/RagMetricsCard.vue` 的 donut 标签布局: 去掉图心覆盖文字,改为在饼图外侧通过标签线显示百分比和指标名称,并左移图心为外侧标签留出空间,避免数字和文字继续压在图形内部。
- 将 `console/src/components/dashboard/RagMetricsCard.vue` 的 donut 文案展示方式改为原生 DOM 布局: ECharts 仅负责绘制环形图,百分比和指标名由卡片右侧独立渲染,避免 `overflow: hidden` 裁掉图表外侧标签导致文字消失。
- 继续调整 `console/src/components/dashboard/RagMetricsCard.vue` 的三指标排布: 每个指标块改为“上方环形图 + 下方数值/名称”的纵向结构,避免右侧文案挤压图形,使三个饼图的视觉主体尺寸重新大于数字文本。
- 修正 `console/src/components/dashboard/RagMetricsCard.vue` 的移动端 donut 布局: 手机端保持三列紧凑排布,限制单图最大宽度并收紧文字尺寸,避免窄屏下单个饼图被拉得过大且视觉偏移。

### 前端 - Obs 召回卡片语义纠偏
- 调整 `console/src/components/dashboard/LongTermMemoryCard.vue` 与 `KnowledgeRecallCard.vue`: 去掉误导性的 “ReRank 前 / ReRank 后” 切换,改为明确展示当前已注入 system context 的记忆/知识索引提示。修复前端用同一份注入后摘要伪造“前后对比”导致界面语义与后端真实数据不一致的问题。

### 前后端 - Obs 真实召回快照
- 扩展 `agent_service/services/memory/retrieval_service.py`、`context_builder.py` 与 `agent_core/agent_core.py`: 在构建上下文时保留长期记忆与知识库的真实 `pre_rerank` / `post_rerank` 快照,并随 system message metadata 一起持久化。
- 扩展 `agent_service/api/rest/agent.py`、`protos/agent_service.proto` 与 `agent_service/api/grpc/servicer.py`: 新增 Obs 召回详情能力,返回最近一次真实召回快照而不是前端推断的索引摘要,并同步补齐 gRPC 接口。
- 调整 `console/src/router/api_routes.js`、`src/api/agent.js`、`components/dashboard/MemoryKnowledgePanel.vue`、`LongTermMemoryCard.vue` 与 `KnowledgeRecallCard.vue`: 前端改为请求真实召回快照,恢复真正的 “ReRank 前 / ReRank 后” 切换,展示真实条目正文与评分信息。

### 前端 - 聊天气泡即时占位恢复
- 调整 `console/src/stores/chat.js` 与 `console/src/components/chat/MessageBubble.vue`: 用户发送消息后立即插入 assistant 占位消息,并让空内容流式阶段直接渲染闪动光标气泡,修复 agent 需要等到首个回复 chunk 或最终回复才显示气泡的问题。
- 进一步调整 `console/src/stores/chat.js`: 在插入 user / assistant 占位消息后显式 `await nextTick()`,先让浏览器完成首帧渲染,再进入流式请求循环,缩短“用户发送消息”和“占位气泡出现”之间仍然存在的可感知延迟。
- 继续调整 `console/src/stores/chat.js`: 在 `nextTick()` 之后额外等待一次浏览器绘制帧 (`requestAnimationFrame`),确保 assistant 占位气泡在网络请求正式推进前已经真正绘制到屏幕上,进一步压缩发送瞬间的空档。

### 前端 - 暗色聊天气泡配色
- 调整 `console/src/assets/ui-system.css` 与 `console/src/components/chat/MessageBubble.vue`: 仅在暗色主题下将用户气泡改为磨砂玻璃发光蓝色,将 AI 气泡改为磨砂玻璃发光红色; 亮色主题继续保持原有低干扰样式。
- 进一步修正 `console/src/assets/ui-system.css`: 将暗色主题下用户气泡的底色与边框也切换到蓝色系,避免只改发光层但主体仍残留原橙色的问题。
- 继续调整 `console/src/assets/ui-system.css`: 为亮色主题下的用户 / AI 气泡也补上蓝 / 红主体配色,但保持无发光效果,避免亮色界面过于刺眼。
- 修正 `console/src/components/dashboard/MemoryKnowledgePanel.vue` 的召回快照刷新时机: 不再依赖前端消息列表中已被过滤掉的 `system` 消息作为刷新键,改为在 assistant 消息落库且流式结束后重新拉取 `recall-details`,解决 Obs 面板长期记忆 / 知识库召回长期空白的问题。
- 调整 `console/src/components/dashboard/LongTermMemoryCard.vue` 与 `KnowledgeRecallCard.vue` 的 ReRank 切换按钮样式: 将按钮从标题栏移到正文工具条,并复用 `RagMetricsCard` 同款切换视觉,避免原先标题栏里的小按钮过丑且不统一。
- 修正 `agent_service/api/rest/agent.py` 与 `agent_service/api/grpc/servicer.py` 的召回详情接口: 新增共用的 `agent_service/api/recall_details.py`,当历史 system message 没有持久化 `recall_details` 时,使用最近用户问题实时补算长期记忆和知识库的 `pre_rerank` / `post_rerank` 快照,避免旧会话或未携带快照的消息在 Obs 面板中显示空白。
- 修正 `agent_service/api/grpc/agent_service_pb2_grpc.py` 的生成代码导入路径: 将顶层 `import agent_service_pb2` 改为包内绝对导入,避免从 `main.py` 启动时出现 `ModuleNotFoundError: No module named 'agent_service_pb2'`。
- 修复 `console/src/components/dashboard/LatencyCard.vue` 的数据来源问题: 调整 `useObsData.js` 的耗时轮次派生逻辑,支持流式中的 pending turn、过滤空 assistant 消息,并让 Obs 页面补拉最多 200 条历史消息; 同时将 `chat.js` 的流式请求与历史加载拆成独立 AbortController,避免补拉历史时误中断当前发送状态,导致“每次 message 思考耗时”卡片显示无数据。
- 修正 `console/src/views/DashboardView.vue` 直接进入 Obs 页面时没有当前会话的问题: 当 `currentSessionId` 为空时自动加载会话列表并选中最近会话,再补拉消息历史,避免刷新或直接打开 `/dashboard` 后所有基于消息的 Obs 卡片显示空数据。
- 进一步修正 Obs 页面无数据时的入口状态: `DashboardView.vue` 在未设置 `user_id` 时直接显示 Obs 专用输入框,避免直接打开 `/dashboard` 后静默空白; `LatencyCard.vue` 的空态补充当前 session 与消息数量,方便确认是未选会话、未加载消息还是确实没有完整轮次。
- 修正 `console/src/components/dashboard/LatencyCard.vue` 在无耗时数据时整块图表消失的问题: 折线图容器现在始终渲染,即使没有 turn 数据也会显示坐标轴和占位刻度,避免卡片内部看起来完全空白。

### 前端 - Obs 面板响应式适配
- 为 Obs 面板新增 `console/src/composable/useObsData.js` 统一观测数据派生层，集中从 chat/session store 提取当前节点、trace、上下文来源、RAG 指标、Token 趋势、耗时趋势、运行路径和调度池快照，避免每张卡片重复解析消息与 trace。
- 重做 `console/src/components/dashboard/LanguageTraceCard.vue`、`ExecutionTraceCard.vue`、`RagMetricsCard.vue`、`TokenUsageCard.vue`、`LongTermMemoryCard.vue`、`KnowledgeRecallCard.vue`、`LatencyCard.vue` 与 `StateGraphCard.vue` 的卡片内容：由原先的占位文案改为真实 Obs 面板，分别展示思考轨迹、上下文拼装、节点时间线、工具输入输出、调度池状态、RAG 命中指标、large/small token 估算柱图、长期记忆/知识线索切换视图以及每轮消息耗时拆分。
- 重写 `console/src/components/dashboard/StateGraphCard.vue` 的状态图刷新逻辑：LangGraph Mermaid 图结构改为首次挂载时只渲染一次，后续 `currentNode` 变化仅通过 DOM class 更新节点与边高亮，不再因状态切换重复执行 `mermaid.render()`，修复状态切换时整图闪烁、短暂消失和布局抖动的问题。
- 调整 `console/src/views/DashboardView.vue` 的 Obs 页面外层结构,新增 `dashboard-content` 容器,补充 `min-height` 与移动端滚动策略,并让顶部 tab 在窄屏下支持换行与粘性定位,避免移动端切页后内容被固定高度容器截断。
- 调整 `console/src/components/dashboard/AgentTracePanel.vue` 的桌面三栏布局为断点响应式网格: 宽屏保持三列,中屏改为“状态图整行 + 语言轨迹/执行轨迹双列”,小屏改为单列顺序堆叠,使 Agent 轨迹页同时适配桌面端与手机端。
- 调整 `console/src/components/dashboard/MemoryKnowledgePanel.vue` 的双层固定横向布局为断点响应式布局: 宽屏保留原有信息分区,中屏改为上层纵向堆叠与下层两列网格,小屏改为全部卡片单列堆叠,避免记忆/知识面板在移动端横向溢出。
- 放大桌面端 `StateGraphCard` 的展示空间: 提升 `AgentTracePanel` 左栏宽度,并收紧状态图卡片桌面端内边距与最小图宽,修复状态转移图在桌面端看起来过小的问题。
- 修复 Obs 面板在移动端单列布局下卡片未拉满容器宽度的问题: 为 `AgentTracePanel` 与 `MemoryKnowledgePanel` 的列容器及其直接子卡片补充 `width: 100%` 和 `min-width: 0`,避免卡片按内容宽度收缩后在右侧留下空档。
- 进一步修复 Obs 面板移动端右侧留白问题: 将 `DashboardView.vue` 中移动端的 `dashboard-content` 从横向 flex 容器切换为 `block + width: 100%`,并强制其直接子页面面板占满宽度,避免整页 panel 作为 flex item 按内容宽度收缩。
- 调整桌面端状态转移图的尺寸判定策略: 超宽桌面布局下改为优先参考视口高度推导 `AgentTracePanel` 左栏宽度,使状态图更接近按竖直空间放大; 普通桌面宽度区间继续维持按横向宽度分配列宽,移动端布局保持不变。
- 收紧桌面端“按高度优先”触发条件: 仅在超宽且横向比例明显大于方屏的桌面环境下启用高度优先的状态图布局,避免 `1:1` 或接近方屏的桌面错误进入高度优先模式,这些桌面继续按宽度优先布局处理。

## 2026-05-14

### 后端 — Bug 修复
- 修复 `safety_service.py` 中 `audit_output()` 访问不存在的 `result.scrubbed` 属性的 bug,改为正确的 `result.sanitized`（`OutputAuditResult` 的属性名为 `sanitized`）。此 bug 导致 safety_output 节点每次执行都抛出 `AttributeError`,Agent 流式对话在输出审核阶段异常终止。
- 修复 `rerank.py` 中 `RerankService.rerank()` 每次调用都创建新的 `SentenceTransformerCrossEncoderProvider` 实例导致 CrossEncoder 模型被反复加载（每次 ~4s）的性能问题。改为在 `RerankService` 实例上缓存 provider,首次创建后复用,与 Embedding 模型的延迟加载缓存策略对齐。
- 修复 `scheduler.py` 中 `ChatOpenAI` SDK 层重试与调度器 `_run_with_retries` 双重重试叠加导致 Moonshot API 429 雪崩的问题。为 `ChatOpenAI` 设置 `max_retries=0`,将重试控制权完全交给调度器统一管理（指数退避 + 熔断器）。
- 修复 SSE 流式推送失效问题：将 `routes.py` 中 `/agent/stream` 的 `async def _event_generator()` 改为 `def _event_generator()`,避免 `agent.stream_session_prompt()` 的同步阻塞在事件循环中导致流式失效；在 `vite.config.js` 代理中移除 `accept-encoding` 防止压缩缓冲、强制保留流式响应头；在 `client.js` 中增加 `response.body` 空值防御。

### 前端 — Agent Console 聊天面板
- 新建 `console/` Vue 3 前端项目,实现 Agent 对话面板。
  - **基础架构**: 新增 `package.json` 依赖 `lucide-vue-next` 功能图标库; 配置 `vite.config.js` 代理 `/sessions`、`/agent` 到 `localhost:8000`; 更新 `index.html` (lang=zh-CN, title=Agent Console); 更新 `main.js` 引入全局样式与主题初始化。
  - **设计系统**: 新增 `src/assets/ui-system.css` (CSS 自定义属性:明暗主题配色、字体栈、间距尺、动画参数) 与 `src/assets/main.css` (全局 reset、直角边框、毛玻璃 `.glass-panel` 工具类、滚动条样式)。
  - **数据层**: 新增 `src/api/client.js` (fetch 封装、`ApiError`、SSE `streamLines` AsyncGenerator 解析器、`getUserId`/`setUserId` localStorage 管理)、`src/api/session.js` (会话列表/创建/消息历史 API)、`src/api/agent.js` (SSE 流式对话 `streamPrompt`)。
  - **用户管理**: 新增 `src/composable/useUserId.js` — 响应式 user_id 管理,读写 localStorage,不涉及认证。
  - **状态管理 (Pinia)**:
    - `src/stores/settings.js` — 明暗主题切换,通过 `data-theme` DOM 属性驱动 CSS 变量,持久化到 localStorage。
    - `src/stores/session.js` — 会话列表、当前选中会话、加载/创建/选中方法。
    - `src/stores/chat.js` — 消息列表、SSE 流式状态、`send()` 方法逐块更新助手回复。
  - **通用组件**: `ThemeToggle.vue` (Sun/Moon 图标切换)、`AppTopBar.vue` (macOS 风格毛玻璃顶栏,三色圆点+标题+Chat/Obs 标签导航+主题按钮)。
  - **会话组件**: `SessionDrawer.vue` (毛玻璃左侧滑出抽屉,新建按钮+会话列表)、`SessionItem.vue` (单条会话行,选中高亮)。
  - **聊天组件**: `MessageBubble.vue` (user/assistant 差异化气泡)、`MessageList.vue` (自动滚底容器)、`StreamingIndicator.vue` (脉冲点加载指示器)、`ChatInput.vue` (输入框+Send 按钮,Enter 发送/Shift+Enter 换行)。
  - **路由与页面**: 新增 `src/router/api_routes.js` (API 端点路径常量); 更新 `src/router/index.js` (ChatView + DashboardView 路由,`/` 重定向到 `/chat`); 新增 `ChatView.vue` (聊天主页面,组合抽屉+消息+输入+流式指示器,首次使用提示输入 user_id); 新增 `DashboardView.vue` (观测面板占位页)。
  - **外壳**: 更新 `App.vue` 为 AppTopBar + router-view。

### TODO 实现 — 工具分组分离
- 将 `builtin.py` 中单一 `BUILTIN_TOOL_DEFINITIONS` 拆分为三个明确分组: `UTILITY_TOOL_DEFINITIONS`（通用工具 9 个）、`MEMORY_TOOL_DEFINITIONS`（长期记忆工具 2 个: `get_long_term_memory`、`write_long_term_memory`）、`KNOWLEDGE_TOOL_DEFINITIONS`（知识库工具 1 个: `get_knowledge_context`）。`BUILTIN_TOOL_DEFINITIONS` 保留为三个分组的合并列表,`ToolRegistry` 无需修改。新增分组名称在 `tools/__init__.py` 中一并导出。

### TODO 实现 — 模型加载日志围栏
- 为所有模型下载和加载操作添加 `====` 格式日志横幅,使操作过程可观测:
  - `scripts/download_model.py`: `_download_from_huggingface()` 下载前/后打印横幅+模型名+目标目录; `ensure_model()` 已存在时打印跳过提示。
  - `services/memory/rag/embedding.py`: `SentenceTransformerEmbeddingProvider._get_model()` 加载前/后打印横幅+模型名+路径。
  - `services/memory/rag/rerank.py`: `SentenceTransformerCrossEncoderProvider._get_model()` 加载前/后打印横幅+模型名+路径。

### TODO 实现 — 前端 Markdown 渲染
- 新增 `console/package.json` 依赖 `marked ^15.0.0`。
- 新建 `components/chat/MarkdownContent.vue`: 用 `marked.parse()` 渲染 Markdown 为 HTML,scoped 样式遵循"去AI化"设计系统（直角无阴影、JetBrains Mono 等宽、低饱和冷色、细线边框）,覆盖代码块、表格、引用、标题、列表等全部 Markdown 元素。
- 修改 `components/chat/MessageBubble.vue`: assistant 气泡中的 `<pre>` 替换为 `<MarkdownContent>`,user 气泡保持不变。

### TODO 实现 — 流式推送修复 (token 级)
- **scheduler.py**: 新增 `stream_chat()` 公开方法和 `_stream_chat_request()` 私有实现,使用 `model.stream()` 逐 token yield `AIMessageChunk`,Redis 后端自动降级为 `invoke_chat()` + 单 chunk。
- **runtime_context.py**: 新增 `set_agent_token_callback()` / `get_agent_token_callback()` / `clear_agent_token_callback()`,通过 `threading.local` 在线程间传递 token 回调,避免通过图构建器传参。
- **model_decision.py**: `__call__()` 检测 thread-local token 回调,有则走 `_streaming_call()` 使用 `stream_chat()` 并逐 token 触发回调,无则使用原 `invoke_chat()` 路径。
- **agent_core.py**: `_stream_events()` 改为双线程+队列模式: 创建 `queue.Queue`,设置 token 回调推入队列,后台 daemon 线程执行 `graph.stream()`,主线程从队列读取并 yield token 事件和节点事件;异常通过队列传播,finally 清理回调并 join 线程。
  - **关键修复**: 将 `set_tool_runtime()` 和 `set_agent_token_callback()` 移入 `run_graph()` 内部(graph 线程),因为 Python `threading.local()` 不会跨线程继承。初始实现将 thread-local 设在了主线程,导致 graph 线程中的 ModelDecisionNode 永远拿不到 token 回调,回退到非流式 `invoke()` 路径,流式推送完全失效。
- HTTP SSE 和 gRPC 共用同一 `_stream_events()` 核心,无需修改路由或 servicer。
- 前端 `chat.js` 现有累积式内容更新逻辑已兼容 token 级流式,无需改动。

### TODO 实现 — Markdown 代码语法高亮
- 新增 `console/package.json` 依赖 `highlight.js ^11.11.0` + `marked-highlight ^2.2.0`。
- 更新 `components/chat/MarkdownContent.vue`: 集成 `marked-highlight` 插件,注册 13 种常用语言 (python/javascript/typescript/java/go/rust/c/sql/bash/json/yaml/xml/css),在 marked 解析阶段对围栏代码块自动应用 `hljs.highlight()`。高亮配色采用非 scoped 独立 `<style>` 块定义 `.hljs-*` 类,低饱和冷色工业风 (注释灰色、关键字棕红、字符串暗绿、数字暗金、函数暗蓝、变量暗紫),与 Agent Console 设计系统协调。
  - 删除 `src/stores/counter.js` (示例 store)、`src/view/` (拼写错误目录)。

### 后端
- 新增 `AgentConfig.ServerConfig` 子配置,将 FastAPI HTTP 端口(默认 8000)和 gRPC 端口(默认 50051)纳入统一配置管理,注册 `AGENT_HTTP_HOST/PORT` 与 `AGENT_GRPC_HOST/PORT` 环境变量,并更新 `main.py` 从配置读取监听地址。
- 扩展 REST 接口层: 为前端对话面板与观测面板补齐 5 个 HTTP 端点。
  - `GET /sessions?user_id=xxx` — 列出用户的所有会话(按更新时间倒序)。
  - `POST /sessions` — 创建新会话,body 传入 user_id 和可选 session_name。
  - `GET /sessions/{session_id}/messages?user_id=xxx&limit=50` — 获取会话消息历史(按时间正序,未摘要消息),供前端聊天面板加载历史记录。
  - `GET /agent/stream?prompt=xxx&user_id=x&session_id=x` — SSE 流式对话接口,复用 `AgentCore.stream_session_prompt()` 逐节点推送 Agent 执行事件,以 `data: [DONE]` 结束流。
  - `GET /agent/events?session_id=x&user_id=xxx` — 查询会话中带有 node trace 信息的消息事件列表,供前端观测面板还原智能体思考轨迹。
- 更新 `main.py`: lifespan 启动阶段创建 `MessageService` 并将 `AgentCore`、`SessionService`、`MessageService` 注入 `routes` 模块,关闭阶段清理注入引用。
- 新增统一日志系统: 在 `AgentConfig` 中新增 `LoggingConfig` 子配置类,管理全局日志级别、控制台/文件双通道输出、日志格式(plain/json/stuctured)、文件轮转策略(按大小/按天)以及各模块独立日志级别覆写,并注册 `AGENT_LOG_*` 系列环境变量。
- 新增 `agent_service/services/logging_service.py`,提供 `setup_logging(config)` 统一日志初始化入口,支持控制台 `StreamHandler` + 文件 `RotatingFileHandler`/`TimedRotatingFileHandler` 双输出、JSON 行格式文件日志和 structured 控制台格式,日志文件写入 `runtime/logs/agent_service.log`。
- 更新 `main.py`: 在 `_lifespan` 最早阶段调用 `setup_logging()`,将原有 `print()` 调用全部替换为结构化 logger 输出,覆盖 gRPC 启动/关闭、AgentCore 初始化完成、配置加载等关键生命周期事件。
- 更新 `agent_service/agent_core/agent_core.py`: 为 `AgentCore.__init__`、`stream_run`、`stream_session_prompt`、`close` 和 `_stream_messages` 添加 INFO/DEBUG 级别日志,记录模型名称、session/user、prompt 长度、图节点执行等核心链路信息。
- 更新 `agent_service/agent_core/graph.py`: 为 `AgentGraphBuilder.build()` 添加图构建开始/完成日志,记录最终编译图的节点数量。
- 更新 `agent_service/services/safety/safety_service.py`: 为三层安全审核(敏感词拦截、意图审核拦截、输出审核)添加 WARNING 级别日志,记录拦截类型、风险类别和内容长度。
- 更新 `agent_service/services/scheduler/scheduler.py`: 为 `LLMTaskScheduler` 初始化、`invoke_chat` LLM 调用和 `shutdown` 资源释放添加日志,记录 Redis 启用状态、模型池并发数、任务类型与模型 tier 等关键调度参数。
- 更新 `agent_service/services/__init__.py` 导出 `setup_logging` 和 `is_initialized`,便于外部模块统一引用。

## 2026-05-13
- 将 MCP 正式接入 Agent 工具链: 新增 `agent_service/tools/mcp/registry.py` 作为配置驱动的 MCP 工具注册适配层,按 `AgentConfig.MCPConfig` 发现外部 MCP Server 工具,为每个工具生成带 server 隔离前缀的稳定工具名,并包装成现有 `BuiltinToolDefinition` 兼容结构。
- 升级 `ToolRegistry.with_builtin_tools(config=...)` 为“原生工具 + MCP 工具”统一注册入口,同时让 `AgentCore` 和 `LLMTaskScheduler` 在创建默认工具注册表时显式传入全局配置,确保模型绑定工具与 `ToolExecutor` 使用的是同一份 MCP/原生混合工具视图。
- 新增 `tests/test_mcp_tool_registry.py`,通过伪造 MCP 工具发现和工具调用结果,回归验证 MCP 工具会被统一注册,且能通过现有同步 `ToolExecutor` 正常执行,无需依赖真实 MCP server 或真实 `mcp` Python SDK。
- 修正 MCP 客户端落点: 将第一版最小异步 `MCPClient` 从误建的 `agent_service/mcp/` 迁回 `agent_service/tools/mcp/`,同时删除错误主目录包并同步修正 `tests/test_mcp_client.py` 的导入路径。
- 在 `agent_service/tools/mcp/client.py` 与 `agent_service/tools/mcp/__init__.py` 中补齐第一版最小异步 `MCPClient`,支持 `connect / disconnect / list_tools / call_tool` 四个核心能力,为后续接入外部 MCP Server 做准备。
- 新增 `tests/test_mcp_client.py`,通过假 MCP SDK 验证最小客户端的连接初始化、工具发现与工具调用结果规范化逻辑。
- 在 `README.md` 第 12 条“多级队列与并发”下补充大小模型分流子条目,明确 `foreground_agent -> large`、`compress/summary/fact extraction -> small` 的默认路由,并说明 small 模型配置完整时会真正物理隔离到独立小模型。
- 更新 `README.md` 的“#### 任务调度机制”文档图示: 将原本合并的“上下文压缩 / 重要事实摘要流程”拆分为 `compress` 与 `summary` 两条独立 Mermaid 流程图,并把模型池调度图更新为主 Agent 走 `large`、compress/summary/fact extraction 走 `small` 的实际分配关系。
- 为 `AgentConfig.ModelConfig` 增加 Kimi `kimi-k2.*` 温度兼容逻辑: 新增 `resolve_primary_temperature()` 与 `resolve_small_temperature()`，自动将该系列模型的 temperature 归一为接口要求的固定值 `1.0`，修复 `invalid temperature: only 1 is allowed for this model` 导致的主链路与摘要链路 400 错误。
- 将 `LLMTaskScheduler`、`ModelDecisionNode`、`SessionSummaryService`、`MemoryResolver` 以及 `test_small_model.py` 的 `ChatOpenAI` 构造统一切换为走配置层温度兼容函数,避免同类 provider 约束在不同调用入口重复踩坑。
- 在 `tests/test_agent_core_service.py` 新增 `kimi-k2` 温度归一回归测试,防止后续模型配置重构时重新把不兼容温度透传到 Kimi API。
- 扩展 `AgentConfig.ModelConfig` 增加 `small_model_provider`、`small_model_name`、`small_model_api_key`、`small_model_base_url`、`small_model_temperature` 与 `small_model_timeout_seconds`，并补充对应 `AGENT_SMALL_MODEL_*` 环境变量映射,为后续小模型调度与轻量语义任务接入预留统一配置入口。
- 新增 `agent_service/scripts/test_small_model.py`，用于直接读取 `.env` 中的小模型配置并执行一次最小 `ChatOpenAI` 联通性测试，快速验证本地小模型或 OpenAI 兼容小模型服务是否可用。
- 修复长期记忆检索中 ReRank 过度降权 active fact 的问题: `MemoryRetrievalService` 现在将最终相关性分解释为 `max(rerank_score, merged_score)`，避免当前有效事实因 CrossEncoder 低分被阈值过滤后错误回退到旧 `session_summary`。
- 在 `tests/test_memory_rag.py` 新增低分 ReRank 回归测试,覆盖“active fact 已存在但 ReRank 低于混合召回分时仍必须保留”的检索场景。
- 修复 `MemoryResolver` 在已知事实键上的时效性覆盖漏洞: 规则抽取现在优先于 LLM 结果,避免模型把旧值或上下文噪声错误写回当前事实。
- 扩展 `MemoryResolver.PROJECT_CODE_PATTERNS`，补齐 `更改为`、`改为`、`变更为` 等更新型句式,修复“1111111 -> 2222222 -> 3333333”连续更新时第三次代号无法落库的问题。
- 在 `tests/test_agent_core_service.py` 新增两条回归测试,分别覆盖“LLM 输出错误旧值时规则覆盖”和“三次连续代号更新后仅最新值保持 active”的场景。
- 补全 `agent_service/services/memory/rag/hybrid_retrieval.py`，实现生产链路所需的关键词抽取、关键词召回、向量召回候选与关键词候选去重合并，正式落地 README 中的“混合检索 / 多路召回”能力。
- 补全 `agent_service/services/memory/rag/rerank.py`，新增基于本地 `sentence-transformers CrossEncoder` 的 ReRank 服务与可注入 provider 接口，使混合召回结果能够进入真实精排阶段。
- 重写 `agent_service/services/memory/retrieval_service.py` 的主工作流，将长期记忆与知识库检索统一切换为“embedding -> vector recall -> keyword recall -> hybrid merge -> rerank -> relevance/freshness/authority final rank”链路，并保留 pgvector / JSON 向量双路径回退。
- 更新 `agent_service/services/memory/rag/__init__.py` 导出项，正式对外暴露 `HybridRetrievalService`、`HybridRetrievalCandidate` 与 `RerankService`，便于后续 `ContextBuilder` 和其他模块复用统一检索组件。
- 在 `requirements.txt` 中补充 `sentence-transformers` 依赖，用于本地 Embedding 与 CrossEncoder ReRank 模型的生产推理。
- 新增 `tests/test_memory_rag.py`，覆盖关键词召回命中与 `MemoryRetrievalService` 已接入 hybrid retrieval + rerank 工作流的回归测试。
- 为 `AgentConfig` 增加小模型池与上下文压缩相关配置,包括 `important_fact_summary_system_prompt`、`context_compression_tail_messages`、`large_model_max_concurrency` 与 `small_model_max_concurrency`,并补充对应环境变量读取逻辑。
- 扩展 `LLMTaskScheduler` 与 Redis 序列化协议,为所有可序列化 LLM 请求新增 `model_tier=large/small` 路由能力,并在调度器内部加入独立的大模型池/小模型池并发闸门。
- 新增 `ImportantFactSummaryService`,统一封装“小模型重要事实摘要 + 向量库长期记忆入库”能力,供会话摘要和上下文压缩两条链路复用。
- 将 `SessionSummaryService` 的摘要生成逻辑改为复用重要事实摘要服务,摘要继续写入 `session_summary`,随后仍由 `MemoryResolver` 执行 `session_fact` 提取与时效裁决。
- 将 `MemoryResolver` 的结构化事实抽取 LLM 调用切换到 `small` 模型池,与摘要和压缩任务保持一致的轻量模型调度策略。
- 新增 `CompressNode`,把 Agent 图升级为 `compress -> agent -> action -> compress -> ... -> summary -> END`,在上下文 token 估算触顶时生成重要事实摘要、写入 `important_fact_summary`,并用“摘要 + 最近消息”重写当前工作上下文。
- 升级 `ContextBuilder`,增加重要事实摘要注入、字符启发式 token 估算和上下文超限时的尾部消息重建逻辑,使后续轮次能够直接消费 `important_fact_summary`。
- 调整 `MemoryRetrievalService`,在 `session_fact` 之后新增 `important_fact_summary` 召回层,并补充 `get_latest_important_fact_summary()` 供 `ContextBuilder` 使用。
- 调整 `AgentCore` 的工具运行时上下文注入逻辑,优先复用 `ContextBuilder` 已持有的统一检索服务,避免同一轮执行里重复构造检索依赖。
- 更新 `README.md` 的记忆机制与任务调度机制说明,补充 `compress` 节点、重要事实摘要流和 `large/small` 双模型池调度 Mermaid 图。
- 新增并更新测试,覆盖小模型路由解析、`compress` 节点消息重写、上下文超限时的重要事实摘要注入等关键行为。

## 2026-05-12
- 将 `SummaryNode -> summarize_session(user_id, session_id)` 升级为真正的 Redis 持久化业务任务: 新增专用 summary job Stream、独立 worker、结果回写和去重,使服务实例关闭后 summary 任务仍可由其他实例或重启后的实例继续处理。
- 为调度器新增 `submit_summary_job(...)` 入口和 `SerializedSummaryJobRequest/Result` 协议,将“Summary 业务任务分布式化”与“内部 LLM 调用 Redis 化”分层解耦。
- 修复 `main.py` 退出阶段后台 summary 任务偶发报出 `cannot schedule new futures after interpreter shutdown` 的问题: 为调度器增加 `atexit` 关闭钩子,在 `main.py` 末尾主动重置 scheduler,并在解释器收尾阶段静默忽略 summary 后台任务异常。
- 在 `README.md` 的“#### 任务调度机制”小节补充 Mermaid 流程图,展示 Summary 业务任务持久化、LLM Chat 请求持久化、本地回退路径以及 worker / semaphore / retry / circuit breaker 的实际运行链路。
- 将 `task_schedule` 升级为“Redis Stream 生产模式 + 本地 generic 队列双通道”结构: 真正的 LLM 请求改为可序列化 chat request,写入 Redis Stream 由 consumer group worker 消费,结果回写 Redis 后由调用方轮询等待。
- 扩展 `TaskScheduleConfig` 新增 Redis consumer group、Stream 长度、结果 TTL、去重 TTL、visibility timeout 与结果轮询间隔等配置项,用于支撑生产级别的 Redis 调度参数。
- 将 `ModelDecisionNode`、`SessionSummaryService` 与 `MemoryResolver` 的 LLM 调用统一切换到 `LLMTaskScheduler.invoke_chat(...)`,不再向调度器传入不可跨进程序列化的 Python lambda 作为真正的 LLM 执行单元。
- 新增 `task_schedule/redis_backend.py` 并扩展 `tests/test_task_scheduler.py`,覆盖无 Redis 配置时的本地 Chat 回退路径,为后续接入真实 Redis 环境留出稳定协议层。
- 修复 `memory_resolver.py` 中事实提取正则被错误写成 Unicode 转义串的问题,恢复为可读的中文模式文本,避免源码层面出现“像乱码”的内容。
- 新增 `agent_service.task_schedule` 包中的第一版统一 `LLMTaskScheduler`,为 LLM 调用提供主 Agent / Summary / Fact Extraction 多级队列、全局并发闸门、超时、指数退避重试和熔断能力,并允许通过 `TaskScheduleConfig` 与可选 Redis 状态共享配置统一管理。
- 扩展 `AgentConfig` 增加 `TaskScheduleConfig` 及对应 `AGENT_TASK_SCHEDULE_*` 环境变量,用于统一配置 LLM 调度器的 worker、队列、超时、重试和熔断参数。
- 将 `ModelDecisionNode`、`SummaryNode`、`SessionSummaryService` 与 `MemoryResolver` 的 LLM 调用全部收口到统一调度器,同时把 Summary 后台触发从裸线程改为调度器异步队列。
- 新增 `tests/test_task_scheduler.py` 覆盖调度器的重试与 Summary 去重能力,防止 LLM 调用入口回退成直接 `invoke()`。
- 修复 `MemoryRetrievalService` 与 `LongTermMemoryService` 在 SQLite 环境下比较 `valid_until` 时出现的“offset-naive / offset-aware datetime”异常: 统一将数据库读回的无时区时间按 UTC 处理,避免 `main.py` 演示链路在长期记忆预览阶段崩溃。
- 在 `tests/test_agent_core_service.py` 新增 SQLite 回归测试,覆盖带 `valid_until` 的长期记忆检索场景,防止时区比较问题再次出现。
- 重建 `README.md` 为正常 UTF-8 中文内容，修复此前文档被错误写入后出现的整份乱码问题，并保留最新的记忆系统、RAG、`MemoryResolver` 与“信息时效性”结构说明。
- 将 `README.md` 的“记忆时效性机制”小节改为 Mermaid 流程图，展示 `session_summary -> session_fact -> 覆盖/追加/失效 -> active fact 检索 -> summary 回退` 的处理链路。
- 重写 `main.py` 的本地演示场景为“四个 session 的高强度记忆时效性测试”,加入三次连续代号更新、最终跨 session 综合查询与知识库灌库预热,用于同时验证 MemoryResolver 覆盖链和长期记忆/知识库联合召回链路。
- 为 `AgentConfig.StorageConfig` 新增 `frontmatter_dir` 和 `AGENT_FRONTMATTER_DIR`,将知识库结构化中间产物路径纳入统一配置管理,默认输出到 `runtime/frontmatter`。
- 新增 `scripts/frontmatter_bootstrap.py` 和 `FrontmatterBootstrapService`,先将 `resources/knowledge` 下的原始 Markdown/TXT 结构化为统一知识 JSON,再供后续灌库链路消费。
- 重构 `KnowledgeIngestionService` 和 `knowledge_bootstrap.py`,改为只读取 `runtime/frontmatter` 中的结构化文档 JSON 执行章节切块、Embedding 和长期记忆入库,不再直接消费原始文本文件。
- 调整 `ContextBuilder` 的记忆注入策略,新增“同 session 双保底”机制: 优先使用短期历史消息,若长期记忆检索未命中则强制补入最近一条当前 session 摘要记忆。
- 明确上下文拼装优先级为“短期历史消息 -> 当前 session 摘要记忆 -> 外部知识库片段”,并同步写入 `README.md` 说明。
- 将检索增强用的系统提示词迁入 `AgentConfig.ModelConfig.retrieval_context_system_prompt`,并新增 `AGENT_RETRIEVAL_CONTEXT_SYSTEM_PROMPT` 环境变量,避免 `ContextBuilder` 硬编码提示文案。
- 调整长期记忆检索范围为“同用户跨 session 召回”,并在排序中补充“当前 session 匹配优先、更新时间更新优先”规则,让新事实覆盖旧事实的场景更稳定。
- 重写 `main.py` 本地演示为三个不同 session 的时效性测试: 第一轮写入代号 `1111111`,第二轮写入更新代号 `2222222`,第三轮在新 session 中查询当前代号。
- 同步修正 `MemoryRetrievalService` 注释与参数语义说明,明确 `session_id` 现在用于“当前 session 优先排序”而非“限制检索范围”。
- 新增 `MemoryResolver`,把 `session_summary` 进一步解析为结构化 `session_fact`,并为事实打上 `active/superseded/expired` 状态,用于处理单值覆盖、多值追加和时序失效。
- 扩展 `LongTermMemoryService` 以支持读取有效事实和更新事实状态,同时让 `SessionSummaryService` 在摘要入库后自动触发记忆时效性解析。
- 调整 `MemoryRetrievalService` 的长期记忆召回策略为“优先 `session_fact`,过滤 superseded/expired 旧事实,无事实命中时再回退到 `session_summary`”,并把 `MemoryResolver` 的处理方法补充进 `README.md`。
- 将 `MemoryResolver` 的事实抽取策略升级为“优先 LLM 按 schema 输出结构化 facts,失败时回退到规则提取”,与 `README.md` 中的事实类型裁决方法保持一致。

## 2026-05-11
- 新增 `agent_service/core/agent_config.py` 中的分层配置体系，包含 `Constants`、`StorageConfig`、`ModelConfig`、`MemoryConfig` 与 `AgentConfig.load_config()`。
- 配置支持默认值、环境变量覆盖、显式 `overrides` 覆盖以及运行目录自动创建，作为后端统一常量与环境变量入口。
- 按结构要求将子配置类收敛为 `AgentConfig` 的内部类，并为每个子配置类补充职责注释，避免配置定义分散在模块顶层。
- 为每个配置字段补充集中式说明,并为配置加载、路径解析、目录创建和环境变量解析函数补充注释。
- 修正 `StorageConfig.base_data_dir` 字段缺失和默认值不一致问题,确保直接实例化与 `load_config()` 的运行目录语义一致。
- 将知识库配置从单文件 `knowledge_file_path` 调整为项目根目录下的 `resources/knowledge` 目录,并根据现有 `runtime` 结构新增关系库、向量库、Embedding 模型和 ReRank 模型运行目录配置。
- 为 `ModelConfig` 增加 `embedding_model_name` 字段和对应环境变量覆盖项,并统一 `system_prompt` 的字段默认值与加载默认值。
- 将默认配置映射改为从 dataclass 默认实例生成,减少字段默认值与加载默认值重复维护导致的配置漂移。
- 新增 `scripts/download_model.py` 模型检查与下载脚本,并在 `AgentConfig.load_config()` 中默认检查 Embedding 与 ReRank 模型,缺失时自动调用下载逻辑。
- 调整 `scripts/download_model.py` 命令行入口为四参数形式,支持手动指定 Embedding/ReRank 的模型名称和本地绝对下载目录。
- 按最新开发规范为 `scripts/download_model.py` 增加文件头部功能说明和命令行使用说明。
- 按最新开发规范为 `core/agent_config.py` 增加文件头部功能说明、配置加载说明和模型检查说明。
- 新增最基础的 LangGraph Agent 循环骨架,包含 `agent -> action -> agent -> summary -> END` 图结构,并按每个节点文件只实现一个节点的要求拆分模型决策、工具调用和摘要节点。
- 新增 `scripts/draw_agent_graph.py` 静态 SVG 绘图脚本,并让 `AgentCore` 每次初始化时在项目根目录生成 `agent_graph.svg` 节点流程图。
- 修正绘图脚本硬编码图结构的问题,改为读取 `CompiledStateGraph.get_graph()` 的真实节点和边来生成 SVG。
- 将绘图脚本调整为从实际图结构生成 Mermaid 文本,并在存在 Mermaid CLI 时自动渲染 SVG,避免维护手写 SVG 坐标逻辑。
- 为 `AgentCore` 增加测试用编译图注入入口,并在 `tests/test_agent_core_service.py` 中补充初始化绘图、流式输出和 Mermaid 生成测试。
- 在 `main.py` 中新增 AgentCore 本地演示调用和 `/agent/test` 接口,用于直接查看 Mermaid 图生成结果和流式输出包装结果。
- 将 `main.py` 从测试假图演示调整为真实 LLM 调用入口,默认通过 `AgentCore(config=config)` 构建真实图并执行 `ModelDecisionNode` 的 ChatOpenAI 决策。
- 调整 `main.py` 本地演示输出,在保留原始流式 chunk 和节点事件的同时提取并打印最终智能体回复。
- 调整 `main.py` 命令行展示顺序,先输出完整裸 JSON,再输出可观测工具调用过程,最后输出最终智能体回复。
- 将 Agent 执行结果整理、SSE 解析、最终输出提取和可观测过程格式化逻辑下沉到 `AgentCore`,让 `main.py` 只负责接口和命令行展示。
- 更新 `agent_core.py` 文件头部说明,补充 `AgentCore` 的执行入口、结构化结果和可观测事件整理职责。
- 在 `README.md` 可观测性设计中补充前端轨迹面板可消费 LangGraph 结构化事件的实现思路。
- 为 `AgentConfig.load_config()` 增加项目根目录 `.env` 加载能力,进程环境变量优先于 `.env`,避免本地运行时模型配置无法读取。
- 实现内置工具层基础逻辑,包含 `builtin.py` 工具书写、`tool_registry.py` 工具注册和 LangChain 工具转换、`executor.py` 工具执行,并让 AgentCore 默认加载内置工具。
- 将 `ToolExecutor` 接入 Agent 图的 `action` 节点,使内置工具调用走项目自己的注册-执行链路,并补充工具注册、执行和节点调用测试。
- 扩展内置工具集,新增指定时区时间、UUID 生成、安全计算、JSON 解析、JSON 路径取值、文本统计和内置工具自查能力。
- 新增 PostgreSQL 版 Session 会话管理基础实现,包含 `models/session.py` 数据库模型、`schemas/session.py` DTO 和 `services/session_service.py` 业务服务。
- 新增 `MessageRecord` 会话消息模型和 DTO,通过 `session_id` 外键关联 Session,用于保存会话原始消息和工具调用轨迹。
- 新增统一长期记忆结构 `LongTermMemorySpec` 和 DTO,用 `tag`、`memory_type`、source、validity、confidence、importance、authority 等字段统一承载长期会话记忆和知识库记忆。
- 新增 `MessageService` 和第一版 `ContextBuilder`,支持按 session 读取最近消息、滑动窗口截断、LangChain 消息转换和当前 prompt 追加。
- 为 `AgentConfig.MemoryConfig` 增加 `max_context_messages` 配置和 `AGENT_MAX_CONTEXT_MESSAGES` 环境变量,用于控制第一版上下文滑动窗口。
- 为 `AgentCore` 增加 `run_session_prompt()` 正式 session 级入口,支持通过 ContextBuilder 加载历史上下文并通过 MessageService 保存本轮消息。
- 更新 `main.py` 本地演示,创建两个 session 并分别执行 2 轮和 5 轮前后关联 prompt。
- 将默认 PostgreSQL DSN 密码调整为本地配置 `1111`,并让 `main.py` session 演示直接使用正式配置而非 SQLite 演示库。
- 将 PostgreSQL 默认 DSN 密码拆分为独立配置字段和环境变量,未显式配置完整 DSN 时按密码字段自动组装 DSN。
- 在 `scripts/db_init.py` 中实现 PostgreSQL 初始化逻辑,支持先创建缺失的业务数据库再初始化 SQLModel 表结构,并让 `main.py` 通过该脚本初始化数据库。
- 在 `resources/knowledge` 中新增 10 个 Markdown 和 10 个 TXT 知识库样本文档,覆盖气候、健康、AI、城市、网络安全、能源、睡眠、农业、海洋和地球观测等主题。
- 将默认 PostgreSQL DSN 调整为 SQLAlchemy psycopg3 方言 `postgresql+psycopg://`,与 `psycopg[binary]` 依赖保持一致。
- 扩写 `resources/knowledge` 中 10 个 TXT 知识库样本文档,将每篇长度补足到约 500 字以满足 RAG 样本语料要求。
- 新增 RAG 入库第一版能力,包含文本重叠切片、本地 Embedding 服务、知识库文件入库服务和 `knowledge_bootstrap.py` 手动灌库脚本。
- 新增 `LongTermMemoryService`,支持将统一长期记忆写入 SQLModel 表,并在 PostgreSQL 下动态初始化 pgvector 扩展、向量列和 ivfflat 索引。
- 将 `summary` 节点从占位改为异步会话摘要调度,通过 LLM 提取未摘要消息的长期摘要,Embedding 后写入向量库并标记原始消息已摘要。
- 将 Embedding/ReRank 模型检查绑定到 `AgentCore.__init__()`,确保启动 AgentCore 时一定调用 `scripts/download_model.py` 的检查下载逻辑。
- 修正真实 Embedding 模型加载路径,让 `EmbeddingService` 加载 `download_model.py` 实际下载的模型子目录,并强化模型完整性校验。
- 增强 pgvector 初始化逻辑,在写入向量前检查既有向量列维度,避免不同 Embedding 维度混写导致向量库损坏。
- 更新 `main.py` 本地会话测试 prompt,让演示内容明确覆盖短期上下文、SummaryNode 调度和长期摘要入库场景,并在命令行输出当前 AgentCore Mermaid 图。
- 压缩 `main.py` 真实 LLM 演示轮次,避免主 Agent 与后台 summary 在短时间内产生过多模型请求导致 429,并为 SummaryNode 后台任务增加异常捕获。
- 修正本地演示输出,恢复 raw JSON 和 Mermaid 图打印,并在 PostgreSQL 未安装 pgvector 扩展时降级保存 JSON 向量,避免 summary 后台任务输出长堆栈。
- 新增专供项目使用的 `agentservice-pgvector` 容器并绑定 `localhost:5433`,同时将 `.env` 的关系库和向量库 DSN 显式切换到该容器。
- 在 `scripts/db_init.py` 中增加 `ensure_vector_extension()`,初始化数据库时自动执行 `CREATE EXTENSION IF NOT EXISTS vector`。
- 新增 `MemoryRetrievalService`,支持对 `session_summary` 和 `knowledge_chunk` 执行统一向量召回,优先走 pgvector,不可用时回退到 JSON 向量余弦相似度检索。
- 将 `ContextBuilder` 升级为自动召回长期记忆和知识库片段并注入系统上下文,同时新增 `get_long_term_memory` 与 `get_knowledge_context` 两个 builtin 工具走同一检索链路。
- 将 `main.py` 改为长期记忆与知识库召回验证脚本: 启动时自动灌知识库,首轮对话后同步生成 summary,第二轮调用前打印召回上下文预览以便确认 Memory 和 Knowledge 是否同时命中。
- 调整聊天发送链路: 将新会话创建从 `ChatView.vue` 前移到 `chat.js` 的占位气泡渲染之后执行。现在用户发送首条消息时,前端会先立即插入 assistant 占位气泡并完成首帧绘制,再异步创建 session 和发起流式请求,避免首条消息在后端思考期间看起来像“没有回复”。

## 2026-05-15

### 后端 — Agent 思考轨迹 (trace human_readable)

- 为 `PlannerNode` 的所有 trace 事件增加 `human_readable` 字段,包含人类可读的规划描述（如"我需要分3步来完成这个任务"、"这是一个简单问题,直接作答"等）。
- 为 `ToolCallNode` 拆分工具调用 trace：每个工具调用生成两条独立 trace（`tool_call_start` + `tool_call_end`）,分别描述正在调用哪个工具及参数摘要、以及工具返回结果摘要。同时为 fallback 路径（LangGraph ToolNode 和未注册工具）增加 `human_readable`。
- 为 `ReflectionNode` 的所有 trace 事件增加 `human_readable` 字段,根据不同决策（answer/compress/continue）输出不同描述文本。
- 为 `CompressNode` 的所有 trace 事件（`compression_skipped`、`compression_empty`、`compression_applied`）增加 `human_readable` 字段,描述当前 token 数量和压缩决策。
- 为 `ModelDecisionNode` 增加 `human_readable` trace,根据模型是否产生 tool_calls 输出"模型决定调用工具：X"或"模型生成最终回复"。
- 修改 `AgentCore._stream_events()` 在单轮对话中累积 `_turn_traces`,并在保存 assistant 消息时将累积 trace 注入 `metadata_json.trace`。同时修改 `_save_state_update_messages()` 和 `_message_to_create()` 传递 `turn_traces` 参数,使思考轨迹随消息持久化,支持前端历史回显。

### 前端 — 思考步骤展示组件

- 新增 `src/components/chat/ThinkingSteps.vue` 组件：接收 trace 数组,将每个节点的思考过程渲染为可折叠步骤卡片。步骤头部显示节点名（彩色标签）+ human_readable 描述文本,工具调用步骤可展开查看详细参数和返回结果。整体采用直角边框 + 单色系 + functional 旋转动画,符合开发规范。
- 修改 `MessageBubble.vue` 集成 `ThinkingSteps`：在 assistant 气泡中,最终回复内容上方渲染思考步骤组件,仅展示含 `human_readable` 且去重的 trace 条目。
- 修改 `chat.js` store 的 `updateLastMessage()` 将 trace 从替换改为追加累积,确保多个节点产生的思考步骤按序保留在同一消息中。

### 后端 — 修复工具输出标记泄露 + 工具调用流式化

- 修复 `builtin.py` 中 `get_long_term_memory()` 输出格式中的 `[Memory]` 标签和 `get_knowledge_context()` 中的 `[来源: X]` 标签，改为纯文本格式，避免内部标记泄露到前端对话框。
- 强化 `system_prompt`：新增规则明确要求用户搜索类请求必须主动调用工具；禁止输出方括号标签格式（如 `[Memory]`）；禁止反问用户。
- 增强 `_sanitize_streaming_content()` 和 `_sanitize_agent_output()`：新增正则检测 `^[标签]` 格式的内部标记输出并拦截。
- 新增工具调用流式推送机制：在 `runtime_context.py` 增加 `set_tool_trace_callback` / `get_tool_trace_callback` / `clear_tool_trace_callback`，遵循与 `agent_token_callback` 一致的线程本地模式。`ToolCallNode` 在每个工具执行前后通过 callback 实时推送 trace 事件到 `token_queue`，`_stream_events` 主循环处理新的 `tool_trace` 事件类型并作为 SSE 事件产出，使工具调用轨迹（工具名、参数、返回摘要）在前端流式展示。

### 前端 — 调整思考步骤样式

- 将 `ThinkingSteps.vue` 边框从左侧粗线改为 1px 圆角矩形（`border-radius: var(--radius-md)`），与外部气泡风格一致；步骤项之间用分割线分隔，最后一项无底线，展开区域增加暗色背景。

### 后端 — 流式输出缓冲防止内容闪现

- 将 `_sanitize_streaming_content()` 中方括号标签检测从 20 字 guard 之后提前到最前面，确保 `[Memory]` / `[Knowledge]` 等内部标记在 `]` 闭合的第一时间即被拦截，不再漏过。
- 修改 `_stream_events()` 中 `on_token` 回调增加缓冲窗口（40 字符）：在前 40 字内不向 token_queue 推送任何内容，仅累积；若在缓冲期内触发 sanitization 则直接发送清理消息并永久阻塞后续 token 推送（`_token_blocked`）；若缓冲期满且内容干净则一次性释放全部累积文本，之后恢复正常流式。消除工具/记忆标记在流式早期闪现后被清除的不良体验。

### 后端 — ContextBuilder 从全文注入改为索引提示

- 将 `ContextBuilder._build_retrieved_context()` 中长期记忆和知识库的检索结果从注入全文改为注入条数提示：`"系统中检索到 N 条与当前问题相关的长期记忆，如需查看具体内容请调用 get_long_term_memory 工具"`。重要事实摘要（CompressNode 输出的压缩上下文）保持全文注入不变。这解决了"模型看到预注入答案后直接复述、跳过工具调用"的问题，迫使模型在需要记忆/知识内容时主动调用工具，从而触发 Planner → ToolCall → Reflection 完整思考链路。
- 同步更新 `retrieval_context_system_prompt`：从"参考材料 — 用自己的话总结"改为"上下文索引 — 使用工具获取详细内容"，明确告知模型哪些内容已直接提供、哪些需调工具获取。
- 同步更新主 `system_prompt` 中【核心机制】段落：从"系统自动注入上下文"改为"系统预检索条目数量作为索引提示，详细内容需调工具获取"。

### 前端 — 修复 SSE 中 action 节点内容污染 assistant 气泡

- 修复 `chat.js` 的 `send()` 中 SSE chunk 处理逻辑：当 `chunk.node === 'action'` 且有内容时，将工具返回结果写入独立的 `role: 'tool'` 消息，不再覆盖 assistant 占位气泡。同时 action 节点的 trace（工具调用开始/结束描述）仍附加到 assistant 消息的 trace 数组中供 ThinkingSteps 展示。planner/reflection/compress 等纯 trace 节点事件也改为仅附加 trace 而不触发 content 更新。解决了流式过程中工具返回全文在对话框主体闪现、重进后才正确归位到 tool 灰框的同步/异步渲染不一致问题。

### 前端 — 聊天区流式滚动改为仅在贴底时自动跟随

- 修改 `console/src/components/chat/MessageList.vue` 的自动滚动逻辑：新增“是否仍贴底”状态与滚动监听。只有当用户原本停留在底部时，新消息和流式 token 才会自动滚到底部；如果用户主动向上滚动查看历史消息，则不再强制抢回滚动位置，直到用户再次滚回底部为止。改善流式对话时的阅读体验。

### 前端 — Obs 上下文拼装模块改为块级拼装视图

- 修改 `console/src/composable/useObsData.js`：新增 `contextAssembly` 派生数据，按真实拼装顺序拆出系统提示、重要事实摘要、长期记忆索引、知识库索引、短期历史窗口和当前问题，并附带块数量、总行数、记忆/知识数量等统计信息。
- 修改 `console/src/components/dashboard/LanguageTraceCard.vue`：将“上下文拼装”从简单来源列表升级为块级结构展示。可按顺序查看每个上下文块的来源颜色、类型状态、行数和具体内容，更接近真实 `ContextBuilder` 的送模拼装效果；保留原有来源列表作为兜底回退视图。

### 前端 — 修复 Obs 上下文拼装标签无法点击

- 调整 `console/src/components/dashboard/LanguageTraceCard.vue` 标题栏局部布局：覆盖卡片标题栏的 `space-between` 排布，改为左对齐流式布局，并让 `window-status` 自动顶到最右侧。同步提升标签按钮的点击层级，修复“上下文拼装”标签被右侧状态文本挤压导致无法点击的问题。
- 进一步将 `LanguageTraceCard` 标题栏拆成 `titlebar-content` 双区结构：左侧独立承载 tabs，右侧单独承载状态文本，并为标签按钮显式添加 `type=\"button\"`。避免浏览器默认按钮行为或标题栏布局挤压继续影响“上下文拼装”标签点击。
- 最终将 `LanguageTraceCard` 的切换 tabs 从标题栏中完全移出，改为卡片正文顶部的独立 `card-tabs` 条，标题栏仅保留窗口标题与状态文本。彻底规避 macOS titlebar 布局和覆盖层对“上下文拼装”按钮点击的干扰。
- 为 `LanguageTraceCard` 的上下文分支增加兜底空值保护：`assemblyBlocks` 和 `assemblyStats` 改为可空读取并提供默认值，避免切到“上下文拼装”时因 `contextAssembly` 尚未准备好而触发渲染异常，表现为“按钮点击无响应”。
- 调整 `AgentTracePanel.vue` 三列容器层级与裁剪：为 `col-mid` 提升 `z-index`，同时给左右三列都加 `overflow: hidden`，防止相邻卡片内容越界覆盖中间列点击区域。
- 调整 `StateGraphCard.vue` 的状态图 SVG：为 `graph-svg` 增加裁剪，并将渲染出的 Mermaid `svg` 设为 `pointer-events: none`。状态图仍可展示，但不再因为 SVG 越界而吞掉中间 `LanguageTraceCard` 的标签点击事件。
- 最终通过自动化复现定位到真实原因：点击“上下文拼装”后浏览器运行时报 `Cannot read properties of undefined (reading 'value')`。修复 `LanguageTraceCard.vue` 中对 `obs.contextAssembly.value` 的直接访问，改为先安全读取 `obs.contextAssembly?.value ?? {}`，再派生 `assemblyBlocks` 和 `assemblyStats`，避免分支切换时因 composable 字段暂未挂载而导致整块视图回退成“按钮无响应”。

### 前端 — Obs 页面自动补拉当前会话历史，修复上下文拼装空白

- 修改 `console/src/stores/chat.js`：新增 `loadedSessionId` 状态，记录当前消息列表对应的已加载会话；历史加载时同时保留服务端返回的 `metadata` 字段，供后续 Obs 面板扩展使用。
- 修改 `console/src/views/DashboardView.vue`：进入 Obs 页面时，若当前存在选中 session 且 `chatStore` 尚未载入该会话历史，则自动调用 `loadHistory()` 补拉消息。这样观测面板不再依赖“必须先留在 Chat 页并保持 store 热状态”，可直接获得当前会话的消息数据源，避免“上下文拼装”与其他 Obs 卡片空白。

### 前端 — 修复 Obs 耗时卡内容区空白

- 修改 `console/src/components/dashboard/MemoryKnowledgePanel.vue`：为下层三列卡片补齐 `height: 100%` 和 `min-height: 0`，修复 `LatencyCard` 在 grid 第三列中高度链不完整、正文区域可能被压空的问题。
- 修改 `console/src/components/dashboard/LatencyCard.vue`：无耗时数据时不再依赖 ECharts 占位渲染，改为直接输出固定高度的 SVG 坐标骨架与示意折线，保证至少可见坐标轴、网格线和占位图形；有真实数据时仍使用 ECharts 折线图和步骤明细视图。

### 后端 — 修复 LLM 内容安全拦截导致 SSE 流异常崩溃

- **问题**: Kimi/Moonshot API 返回 `content_filter` (400 high risk) 时,`scheduler.py` 抛出 `RuntimeError`,经 `agent_core.py` 的 `_stream_events()` 中 `raise item["error"]` 直接传播到 `agent.py` SSE 端点,被 `except Exception` 捕获后只返回模糊的 `internal server error`,客户端无法获知真实原因。
- **修复**:
  - 新增 `_extract_friendly_error()` 模块级函数,识别 `content_filter`、`rate_limit`、`timeout` 等典型 API 错误类型,提取 API 返回的具体 `message` 字段,组装为用户可理解的中文提示(如 `内容安全拦截: The request was rejected because it was considered high risk`)。
  - 修改 `agent_core.py` 的 `_stream_events()`: 队列收到 `error` 事件时不再 `raise item["error"]`,改为 `yield` 一个 `node="error"` 的 SSE 事件并 `break` 终止流,使错误消息通过标准 SSE 通道传递给客户端。
  - HTTP SSE (`agent.py`) 和 gRPC (`servicer.py`) 共享同一 `_stream_events()` 核心,无需额外修改。
- **影响**: 敏感内容拦截不再导致服务端异常日志,客户端可收到有意义的错误提示并据此引导用户修改输入。

