# CHANGE HISTORY

## 2026-07-16
- 将 Agent auto 模式路由从硬编码关键词判断改为小模型入口分类: auto 先调用 small tier 输出 `simple/react/plan`,显式模式保持直通,并要求小模型在自身能力不足、不确定、需要事实核验或外部信息时至少选择 `react`;小模型失败或输出不可解析时才回退本地规则,补充测试覆盖“GTA 最近新内容”这类时效短问题进入 `react`。
- 完成 Agent 回答来源精确挂载: 自动 RAG 和知识库工具召回统一进入 `citation_map`,工具结果新增 `K1/K2` 引用号,最终 assistant 消息按正文实际出现的 `[1]`/`[K1]` 过滤并保存 `used_citations`;editor 聊天气泡改为按消息 metadata 与锚点渲染来源,历史消息不再复用当前轮全局来源。
- 修复 Agent 自动 RAG 注入的知识库作用域问题: `ContextBuilder._build_retrieved_context()` 调用 `retrieve_knowledge_with_debug()` 时传入当前 `user_id`,避免自动召回默认落到 `system` 知识库,并新增回归测试覆盖该调用参数。
- [x] 引用溯源: Agent检索知识库会产出TOP N,Agent对话框侧边栏和大对话页需要将这些块的文章来源指出并展示给用户,用户可以点击后跳转到这个文章(的这一段 if 是markdown).
  - [x] 现在的状态是无论召回的来源是否真正被Agent采用,都会挂在气泡下面,这并不好.应该要让agent回答时提供来源中真正被用到的文档,只把这些被用到的文档挂在气泡上面.
- [x] 引用锚点: 在前端实现像ChatGPT一样的"[1] [2]"这样的答案-来源锚定，需要做两件事：
    1. 后端让模型在回答时携带 citation（可以在 system prompt
    中要求每次引用知识库内容时标注来源序号，然后将序号映射回具体片段）
    2. 前端解析这些标注并渲染为可点击的脚注
    3. 点击后跳转到此文章(的这一段 if 是markdown)
- [x] 添加agent对话时用户中断功能,在agent输出过程中发送按钮会变成圆中有方的"中断"图标,中断后agent的思考轨迹和用户的上个输入仍然会进入上下文.
- [x] 修复文件树操作的一系列问题:
  - [x] 修复拖拽文件夹到文件树不能正确复制的问题.
  - [x] 修复从文件树中复制文件不能粘贴到外部去的问题.
- [x] 扩展引用溯源能力:
  - [x] Agent回复的文档名也要渲染成蓝色,可点击跳转.这可能要求Agent回复的文件名必须要含有全路径,而不能仅仅是一个单纯的文件名.
  - [x] 联网搜索也要溯源,将联网搜索的结果(url来源,也应该是被使用的,而不是所有都放进去)也放在气泡下面,联网的行内索引则使用[N1],[N2]这种来表示,点击后用默认浏览器打开此网页.
- [x] 增加"上传"功能,可以拖拽到智能体页面并上传文件,上传文件会保存在`runtime/uploads/{user_id}/{library}/{session_id}/`文件夹里面.
- [x] 美化Agent思考过程UI.
## 2026-07-14
- 调整知识库灌库前端超时与进度条: `apiPost` 支持单请求 `timeoutMs`,全库/目录/单文件灌库请求超时放宽到 10 分钟,避免 OCR 长任务被 30 秒 Abort;灌库进度条改为等待期间缓慢推进到 86%-88%,完成后再跳到 100%,不再固定瞬跳 44%/92%。
- 修复 PaddleOCR Windows CPU 推理异常被误判为“无文字”的问题: 图片 OCR 推理异常现在记录 warning 并返回 `engine_unavailable`;启动预热和图片 OCR 延迟导入 PaddleOCR 前默认设置 `PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False`,规避部分 PP-OCRv5 模型在 oneDNN/MKLDNN 路径下的 `ConvertPirAttribute2RuntimeAttribute` 异常。
- 修复单文件图片灌库 0 chunk 时前端误报“不支持或已屏蔽”的问题: 后端 `KnowledgeLibraryRebuildResult` 新增 `skip_reason/status_message`,区分屏蔽、不支持后缀、OCR 未识别到文字、OCR 引擎不可用和无可入库切片;前端单文件灌库 toast 优先展示后端状态说明。
- 修复 PaddleOCR 首次预热失败问题: PaddleOCR 的 `*_model_dir` 表示已存在的本地模型目录,空目录会直接查找 `inference.yml` 并失败;现在仅当本地模型目录完整时才传入目录参数,首次启动改为按模型名自动下载,下载后再尝试同步到 `runtime/models/paddleocr`。
- 将图片 OCR 引擎整体迁移为 PaddleOCR: 移除运行时可执行体和语言数据下载逻辑,新增 `runtime/models/paddleocr` 模型缓存目录与 `ensure_paddleocr_models` 启动预热入口,检测/识别模型分别落在 `text_detection` 和 `text_recognition` 子目录;OCR 配置改为中英文检测/识别模型名、语言、设备和置信度阈值,图片 OCR 服务兼容 PaddleOCR 新旧输出结构并按行列位置重排表格截图文本。
- [x] 制作知识图谱可视化:
  - 要美观均匀动态,针对同层子节点特别多的情形还可以自动分层力导分成几层,而不是一起被斥力挤在一圈.
  - 点击图谱节点跳转到编辑区.当鼠标悬浮在文件图谱节点上的时候,要将此文件或文件夹进行高亮对比.
  - 包含: 
    - [x] 文件树的图谱,以根目录为根节点,文件夹节点为虚线球,文件为实心球,不同后缀名文件按照不同颜色分类. 
    - [y] 知识库的图谱,展示各文档之间展示的隐藏联系.和文件树图谱展示方式有点不同,不同的节点之间可以孤立存在,相互吸引而相互排斥,点云看起来像圆形,像obsidian图谱一样.
      - 完成方法: 不使用Neo4j(需要docker容器装着服务),直接使用SQLite建表(节点表+边表).
      - 在多模态文档转化为Json之后,分成两路:一路是灌库流程,一路则是"实体关系解析"流程:调用小模型,从知识库文档（frontmatter JSON 里的 sections）中抽取实体和关系(排队抽取),存储到专门的知识图谱表,然后送到前端进行D3可视化.
    
## 2026-07-13
- 修正图片 OCR 状态语义: 当缺少 OCR 依赖或模型导致 OCR 引擎不可用时,图片 frontmatter/preview 返回 `ocr_status=engine_unavailable`,不再误标为 `no_text`,便于区分“确实无文字”和“OCR 没跑起来”。
- 接入普通图片 OCR 基础链路: 新增 `ImageOcrService` 按用户 OCR 开关、模型目录、语言、置信度和超时配置识别图片文字;图片预览接口返回 OCR 文本、状态、词数和平均置信度;图片入库在识别到文字/表格文本时生成语义章节,无文字时不生成向量语义内容;editor 对有 OCR 文本的图片在 Edit/Split 显示只读识别文本,Preview 显示原图,无文字图片锁定为 Preview。
- 增强非扫描型 PDF 处理: 新增 PyMuPDF 文本层提取工具,PDF 预览接口会返回提取到的正文、页数、图片数和基础表格数;多模态 cleaner 入库时优先使用 PDF 文本层,扫描型 PDF 继续标记为待 OCR;editor 打开有文本层的 PDF 时 Edit 显示只读提取文本,Preview/Split 继续使用浏览器内置 PDF 预览。
- 新增 OCR 默认关闭与重启生效基础设施: 用户知识库灌库设置增加 `ocr_enabled`,保存变更返回 `restart_required`;服务启动后若发现已有用户开启 OCR,会检查并预热 OCR 模型;frontmatter 写入 `ocr_enabled` 元数据,文件树在 OCR 开启后会把图片/PDF/含内嵌 media 的 Office 旧索引标记为需重灌。
- 隐藏 Agent 聊天区中的内部规划/审视硬编码状态文案: 后端 planner/agent/observation trace 标记为 `chat_visible: false`,工具结束 trace 标记为 `chat_visible: true`;editor/console 的 chat/tool 思考展示只渲染工具结果或显式可见 trace,避免“正在更新探索策略”“模型正在决策下一步”“正在审视工具结果”“已找到...”等内部状态句反复出现在工具模式输出中。
- 重做 editor Agent 输入框右下角的思考模式选择下拉栏: `ChatInput.vue` 去掉原生 `select/option`,改为组件内自定义 dropdown trigger 与菜单项,保留 `set-agent-mode` 事件契约并显式控制暗色模式下文字、背景、hover 和选中态颜色。
- 彻底移除 Agent tool 模式首尾异常出现的 `ASSISTANT` 兜底气泡: tool 气泡不再渲染任何非 user/assistant 可见消息和 role 标签,chat 气泡也隐藏 `node=assistant` 的节点标签;思考过程开关改为原生 `details/summary` 下拉栏,保留自定义灰色控制条样式并隐藏浏览器默认 marker。
- 修复 tool 模式中无可见内容的 assistant 被兜底渲染成虚线 system 气泡的问题;美化 chat 模式思考过程折叠栏,改为紧凑灰色控制条并使用固定中性灰文字,避免暗色模式下文字发白。
- 修复 Agent 聊天区流式过程中空气泡和虚空间距: chat 模式下只有思考 trace 时不再额外渲染空 assistant 气泡,仅显示思考过程;tool 模式下无内容的非 action 节点改为显示紧凑状态行,没有任何可见内容时整行不渲染;action 工具行只有存在工具 start/end trace 时才占位,避免每一步思考产生空白换行。
- 修复 Agent 长时间无前端反馈后一次性蹦出大量思考过程的问题: 后端在 planner/agent/observation 进入阻塞 LLM 请求前即时下发轻量 trace,前端收到 trace-only SSE 时立即创建当前节点 assistant 消息并按 trace identity 去重,不再等到节点完成或最终回答才把 buffered trace 一次性挂载;工具模式在 `tool_call_start` 时先显示“正在调用工具”,工具结束后替换为结果摘要,让联网搜索等工具轨迹在执行阶段持续可见。
- 修复 editor 开发环境 Agent SSE 被代理缓冲的问题: editor Vite `/agent` 代理改为与 console 一致,移除 `accept-encoding` 并补齐 `cache-control`、`x-accel-buffering` 和 `connection` 响应头,避免后端持续产出请求/响应时前端聊天区与 Agent 观测页一直转圈、只在流结束后一次性显示最终回答。
- 修复 Agent 前端工具模式流式显示问题: console 对 `type: "delta"` 的 SSE 内容改为追加写入,对节点最终完整内容仍执行替换,避免后续 token 覆盖前文或最终内容重复;工具模式合并连续 assistant 消息时同步追加 content/tool_calls,工具调用条不再只识别记忆/知识两个工具,会优先展示后端 `human_readable/display_name` 并保留未知工具记录,修复“搜索到 N 个内容”等工具调用记录不显示的问题;editor 状态转移图在 auto 模式等待后端真实模式期间保持上一张稳定图,避免发送 prompt 瞬间闪成 plan 最大图;新增 console 单测覆盖 delta 追加、最终完整内容替换和搜索类工具记录显示。
- 隐藏 Agent 对话框中的工具返回结果: action 节点 payload 不再携带工具返回 content,前端流式处理 action trace 时只缓存到观测数据,不再创建“阅读文件/搜索知识库/列出文件”等工具结果气泡,避免大块文档内容和工具列表导致对话区闪烁;同时 ModelDecisionNode 在入模前压缩 ToolMessage,最近工具结果最多保留 900 字符、旧工具结果最多 240 字符,降低长文件和联网搜索结果累积导致的模型 token limit 400 错误。
- 修复 plan 模式信息收集时读多份文件后容易触发 `Connection error` 的问题: 调度器将 `Connection error.` 纳入可重试错误,流式 LLM 调用在首个 chunk 输出前支持按配置退避重试;工具节点限制单轮最多执行 4 个工具调用,超出的 tool_call 返回 deferred ToolMessage 供下一轮继续,避免一次性读取过多文件放大上下文和请求压力;`read_knowledge_file` 对超长文件返回前 6000 字符并提示精确续读。
- 修复 plan 模式下 planner/observation 内部内容泄露到用户聊天流的问题: `planner_content` 和 `observation_content` 不再作为普通聊天内容下发,planner/observation 节点返回的内部 AIMessage 不再持久化为 assistant 消息,最终节点 payload 也会清空内部节点 content;前端历史加载同时过滤旧的 planner/observation assistant 消息,保留 trace 给 Agent 观测面板展示,避免用户看到 JSON 或 `Observation decision=...`。
- 完成 Agent Loop 的 planner/observation 强化: plan 模式下 planner 输出 `sub_questions/current_index/status` 状态机并读取 observation 决策历史,observation 输出结构化 `continue/answer/retry/abandon` 决策;LangGraph 根据 observation 结果分别回到 planner、交给 agent 生成最终回复、重试工具或说明边界,前端 Agent 观测面板新增 observation 决策历史页展示每次选择、原因、下一步建议和置信度。
- 调整 Agent Loop auto 路由: simple 只处理极短闲聊,react 成为默认轻量 Agent 模式,仅在引用、多步骤、分析、规划、设计、修复、重构等明显复杂任务时进入 plan 图;修复“你有哪些工具”这类简单请求误进 plan 的问题。
- 修复 Agent 429 后台放大问题: simple/plan/react 对话结束后只有最近一条 assistant 是真实回复时才启动会话自动重命名,若本轮保存的是 error 或 429 限流提示则跳过后台小模型命名,避免主请求已限流后继续由后台命名任务追加多次小模型请求。
- 完成 Agent Loop ReAct 模式和前端模式切换: 后端同时构建 plan 与 react 两张 LangGraph,react 图只保留 safety/agent/action/output 审核链路,工具结果直接回到 agent 节点继续决策,不再注册 planner 和 observation;REST/gRPC 的 RunRequest 增加 `agent_mode`,前端输入框新增 auto/simple/react/plan 胶囊选择器并持久化,Agent 观测面板状态图按实际执行模式切换为 simple/react/plan 三套图,并兼容旧的 deep 入参。
- 新增 Agent Loop 短问直答路径: 对“你好”“你是谁?”等明显不需要工具的短输入,`stream_session_prompt` 在 ContextBuilder 完成后直接走一次 `FOREGROUND_AGENT_TASK + SMALL_MODEL_TIER` 流式回复,绕过 planner/action/observation 循环,保留用户自定义系统提示词、上下文观测和消息持久化,减少简单对话被多次 LLM 调用放大 429 的概率。
- 修复 Agent Loop 中 planner 和 observation 节点误用大模型的问题: 两个节点的 LLM 调用都显式切换为 `SMALL_MODEL_TIER`,保留用户 small_api_key 为空时回退主模型配置的能力,并新增回归测试防止后续重新走 large tier。
- [x] 修复tool模式下后面的输出取代了前面的输出而不是追加并列,而且还不显示工具调用的问题.
- [x] 修复状态转移图在用户发送prompt的瞬间闪现为plan模式的最大图的问题.
- [x] 修复工具调用记录(比如"搜索到N个内容")不显示的问题.
- [x] 多模态查看:
  - editor编辑区不仅提供Markdown编辑器功能,还提供代码高亮功能(`textarea` + `highlight.js`),实现md模式和代码编辑模式的切换.可设置支持高亮的代码文件格式,如`cpp`,`c`,`py`,`java`等.
  - 可以查看图片(`.png`/`.jpg`/`.jpeg`/`.webp`/`.gif`/`.svg`,`<img>`标签)和PDF(`<iframe>`标签),EXCEL/CSV(后端解析成表格),甚至可以尝试查看WORD(后端用`mammoth`转换成HTML后查看)这样的二进制文档.

- [x] 当前agent只能写可召回可不召回的"长期记忆",应该让agent再配备一个"写长期规则"的工具(即追加系统提示词,效果和用户手动去设置里面填写系统提示词的效果一样),这些规则不是RAG召回的,而是系统提示词,属于是agent必须遵守的.
- [x] 给图谱右上角加个按钮,切换显示文字/不显示文字(当鼠标悬浮在某节点上才显示节点名).
- [x] 给agent也提供读取多模态文件的信息的功能:若该文件已灌库则直接找到该文件对应的json文件,读json即可获取基本信息.
- [x] 当有新文件灌库时在header上显示一个小小的进度条.
- [x] 解决Agent Loop的问题:
  - [x] planner和observation没有用小模型,这是个bug,属于代码错误.
  - [x] 图太大,调用LLM次数太多,planner,agent,observation都要用LLM.
    - 解决方案: 将当前图(ReAct + Plan-And-Execute 融合模式)视为"深度思考模式",即分为3个模式:
      - [x] 简答模式: 对明显不需要工具的短输入不经过循环,只保留 RAG 上下文构建器`ContextBuilder`,然后用小模型直接输出.
      - [x] ReAct模式: 不经过planner节点和observation节点,标准的ReAct图.agent节点同时充当观察者和决策者,一个循环只需要调用一次LLM.
      - [x] 深度思考模式(Plan-and-Execute模式): 经过规划-执行-观察的循环,适合长时间思考.
      - [x] 前端提供 auto/simple/react/plan 模式切换,Agent 观测面板状态图按实际执行模式切换.
      在图之前添加一个入口节点,调用一次小模型,按照用户提问内容区分三种模式的入口,以达成用户在同一session前后提出简单和困难的问题的情形.
  - [x] planner和observation真正发挥的用处并不大,planner每轮都调用,即使没必要,复杂问题并没有给出复杂的解决方案,反而容易背离原本的计划.
    - 解决方案: 加强节点能力:
      1. planner节点: 应具备全局规划思想,拆解问题, 跨轮保持计划 + sub_question 状态机 + 绕圈检测,成为agent执行节点的"调度者".
      2. observation节点: 根据观察选择路径,可选性的规划而不是每次都进入planner节点. 产出四种状态.
      首次: planner（拆解问题，出 sub_questions）
      agent → action → observation（精炼结果 + 提取事实 + 判方向）
      │ 针对observation的不同输出
      ├─ [continue] → planner（更新计划）→ agent（继续）
      ├─ [answer]   → agent（出最终回复）
      ├─ [retry]    → agent（换参数重试同一工具）
      └─ [abandon]  → agent（承认查不到，给出已有信息）
- [x] **惰性灌库**: 用户应该要可设置是否在文件入库时自动灌库,默认关闭,点击header的刷新按钮时才进行主动灌库.用户也可以手动点击文件上的某个按钮让单个文件入库.
- [x] (依赖于惰性灌库)增加功能: 屏蔽单个文件/建立屏蔽区.
  - [x] 屏蔽的文档禁止入库,入了也要出库,文档被写入屏蔽区之后也要把以他为来源的切片删除.
  - [x] 灌库函数自动忽略屏蔽的文档和屏蔽区子树全部文档.
  - [x] 屏蔽区可以通过设置来进行配置,设置里面专门提供一块屏蔽区文本块来设置,写法类似于gitignore.
  - [x] 应该在文件树的每个文件右边加上一个简单的入库状态图标,图标为绿色的的表示已经进入向量库,没有进库的图标为红色,屏蔽(不可进向量库)的为灰色.
- [x] 将左侧agent点击效果从触发agent右边栏变为真正的一个页,此页包裹在左边栏和header里,但是不允许文件树或者agent侧边栏等其他的页或边栏出现,只允许自己一个页面存在.
  - 主要组件和agent侧边栏相同,可复用,仅仅是扩展成一个单独页.对话历史也可以从左侧边抽屉伸缩.
  - 背景和agent侧边栏不同,背景应该采用supercomponents里面的一种动态背景(比如光弦背景),这样就更高级.
  - agent侧边栏新增一个扩展按钮,点击后将agent侧边栏平滑的扩展成agent页,排开其他的页.
  - 这个对话页内部需要有隐藏的针对气泡的限宽,大约是最大屏幕宽度的1/3,对话只在这个宽度内进行,不要让气泡过左和过右.
## 2026-07-12
- 新增知识库惰性灌库流程: 上传文件默认只写入 active 知识库目录并刷新文件树,不再自动触发全量向量入库; 设置页新增“自动灌库”开关并默认关闭,开启后上传文件只灌库本次上传的单个文件; header 刷新按钮继续执行全量灌库; 文件树文件行和右键菜单新增“灌库此文件”,通过 `/knowledge/files/ingest` 只重建该文件的 frontmatter JSON 和 knowledge_chunk,不会误删其他文件切片。
- 修复启动灌库重复扫描用户库 frontmatter 的问题: `KnowledgeIngestionService` 在扫描全局 `runtime/frontmatter` 时会跳过 `users/<user>/<kb>` 子树,避免把用户隔离 frontmatter 输出再次作为全局输入,导致已入库文档启动时重复入库; 显式扫描某个用户库 frontmatter 目录时仍正常生效。
- 修复中文路径文档 ID 碰撞导致哈希锁失效的问题: frontmatter `document_id` 在可读 slug 后追加相对路径短 hash,避免“带图word.docx”“简单word.docx”等中文文件名被清洗成相同 source_id; 知识库哈希锁改为按 `source_id + source_hash + user_id` 判断,避免不同路径同内容或旧 document_id 记录造成误跳过/反复删除重建。
- 调整 header 灌库入口与刷新流程: 原右侧刷新图标改为知识库标题右侧的红色 `Ingest` 胶囊按钮,图标换为数据库灌入语义; header 主动灌库前只刷新文本 tab 内容,当前打开 PDF/DOCX/图片等预览文件时不再调用文本读取接口,避免 415 导致 `Refresh failed`; 失败 toast 会显示真实错误信息。
- 完善文件树便携操作: Electron 拖拽外部文件/文件夹时通过 `webUtils.getPathForFile` 获取真实路径并递归复制目录,修复拖入文件夹只得到占位文件的问题; 文件树复制/剪切写入系统文件剪贴板时过滤真实绝对路径并补写 Windows `FileName/FileNameW/Preferred DropEffect` 格式,提高粘贴到资源管理器的兼容性; 外部拖入、上传和粘贴遇到同名项时会询问覆盖/跳过/重命名,重命名格式统一为 `file (1).txt`。
- 新增知识库屏蔽区: 用户设置中新增 gitignore-like 屏蔽规则文本块,支持注释、目录规则、通配符和 `!` 反向取消; 全量灌库会跳过屏蔽文件并删除旧 frontmatter,随后通过 stale-source 清理已入库切片; 单文件灌库遇到屏蔽文件时只执行出库; 文件删除/移动会同步清理旧来源切片; 文件树新增入库状态点,绿色表示已入库、红色表示未入库、灰色表示被屏蔽。
- 调整文件树入库状态展示与屏蔽规则保存行为: 入库状态从小圆点改为明确图标,已入库显示绿色勾选、未入库显示红色提示、屏蔽显示灰色禁止; 保存屏蔽区规则时立即按新规则清理 active 知识库中已被屏蔽文件的 frontmatter 和向量切片,并刷新文件树状态。
- 文件树右键菜单新增“屏蔽此文件/屏蔽此文件夹”: 点击后自动把文件相对路径或文件夹目录规则追加到知识库屏蔽区文本中,去重保存并刷新文件树,复用已有屏蔽清理流程删除对应入库切片。
- 文件树右键菜单补齐反屏蔽: 已屏蔽节点显示“取消屏蔽此文件/文件夹”,若存在精确屏蔽规则则删除该规则,若是被父目录或通配符命中则追加 `!path` / `!path/` 反规则,保存后刷新文件树状态。
- 优化文件树状态区布局: 将未保存红点和入库状态图标合并到独立的右侧状态簇,通过固定双列间距和细分隔线区分编辑保存状态与索引状态,避免二者看起来处于同一列或互相冲突。
- 修复文件树复制到外部资源管理器无粘贴内容的问题: Electron 43 没有稳定的 `clipboard.writeFiles/readFiles` API,主进程改为在 Windows 下通过系统剪贴板 `FileDropList` 写入真实文件列表和 `Preferred DropEffect`,让资源管理器右键菜单能识别“粘贴”。
- 覆盖策略先删旧文件再复制: 在 `importFilesToPath`、`importExternalPathsToPath` 和 `pasteExternalClipboardPaths` 中,策略为 `overwrite` 时先调用 `deleteKnowledgePath` 触发后端向量库切片清理,再写入新文件。避免旧文件的向量切片残留。
- 修复主动灌库状态反馈: header `Ingest` 和单文件灌库完成后会重新拉取文件树状态; 不支持或被屏蔽的文件按 skipped 处理,不再显示 `File Indexing failed`; header 灌库进度改为红色细长胶囊,展示百分比、成功/总数和失败数,仅在主动灌库期间显示并在完成 1 秒后隐藏。
  - 将冲突询问从 `window.prompt()` 替换为 Vue 模态对话框: `workspace.ts` 新增 `conflictDialog` 响应式状态和 `resolveConflict`/`cancelConflict` 方法,`promptConflictStrategy` 改为返回 Promise;`FileTreePanel.vue` 新增模态框显示冲突文件名列表,提供覆盖/跳过/重命名/取消四个按钮。

## 2026-07-11
- 新增验收 Git 历史重建方案与脚本: `docs/Git验收历史重建方案.md` 说明如何从当前最终快照生成干净的功能分块提交历史,`scripts/rebuild_acceptance_history.ps1` 会创建备份分支和临时 worktree,按四位成员职责拆分 commit,用于验收前整理 main 分支历史。
- 细化独立 Agent 页侧边栏交互: `New Chat` 胶囊内容居中,对话模式切换移到右侧圆形图标按钮并提供悬停提示,折叠侧栏图标替换为更轻量的左栏图标;光弦背景、Agent 页底色和页面模式会话侧边栏补齐亮/暗主题适配。
- 调整独立 Agent 页 UI: 页面模式移除内部矩形外框和顶部对话 titlebar,将新建对话与对话模式切换迁入会话侧边栏;侧边栏默认展开、可关闭,关闭后左侧 hover 热区可重新打开;会话侧边栏按 DeepSeek 风格重构为顶部 AI 标识/折叠按钮、胶囊新对话按钮、历史列表和底部用户 ID。
- 新增独立 Agent 页: 左侧 ActivityBar 的 Agent 入口改为打开主工作区 Agent 页面,该页面保留 header 和左侧栏但折叠文件树与右侧 Agent 栏;复用 `AgentPanel` 的聊天主体、输入框和会话抽屉,侧边栏新增扩展按钮可切到页面模式;页面背景新增 supercomponents 光弦动态背景,并在页面模式下将对话区域限制到约屏幕宽度三分之一。
- 完成图谱/多模态入库小功能: 图谱右上角新增文字显示切换按钮,可切到仅 hover 节点时显示节点名;Agent 新增 `read_multimodal_file_info` 工具,可读取已灌库文件对应的 frontmatter JSON 并返回模态、元数据和章节预览;editor header 在上传新文件和手动刷新灌库时显示细进度条。
- 修复 PDF 预览触发系统下载目录的问题: `/knowledge/files/raw` 返回 `FileResponse` 时显式设置 `Content-Disposition: inline`,避免 Electron/Chromium 将 iframe 内 PDF 当附件下载。
- 修复多模态导入/预览异常: CSV/TSV/JSON/HTML/XML 清洗和 CSV 预览增加 UTF-8/UTF-8-SIG/GB18030/GBK fallback,避免非 UTF-8 测试文件导致 `/knowledge/files/preview` 422;Frontmatter 结构化改为单文件失败跳过并记录日志,避免上传/刷新被某个坏文件拖垮;PDF 预览改用 `/knowledge/files/raw` 原始文件流 URL,提升扫描件 PDF iframe 兼容性。

## 2026-07-10
- 新增 editor 多模态查看能力: 后端新增 `/knowledge/files/preview` 预览接口,支持图片/PDF data URL、CSV/TSV/XLSX 表格预览、DOCX 通过 mammoth 转 HTML 且依赖缺失时回退 OOXML 文本;前端编辑区按文件类型切换 Markdown/Vditor、代码 textarea+highlight.js、图片/PDF/表格/DOCX 只读预览,并为二进制预览禁用保存/撤销按钮。
- 修复 Agent 流式运行中 small-tier 模型调用未继承用户 LLM 配置导致的 `Connection error`: 输入安全审核、拦截回复、上下文压缩和会话自动重命名的小模型调用现在会传入用户 api_key/base_url,small_api_key 为空时自动回退到主模型配置;同时优化 429、缺 Key、连接失败的错误提示,避免前端只显示裸 `Connection error`。
- 新增 Agent 内置工具 `write_long_term_rule`: Agent 现在可以在用户明确要求长期遵守规则时,把规则追加到用户自定义系统提示词条目中,效果与设置页手动添加系统提示词一致;该规则每轮作为系统提示词必注入,不走长期记忆 RAG 召回链路,并新增回归测试验证不会写入向量记忆。
- 调整 README 多模态入库流程图: 明确 docx/xlsx/pptx 会先解包为 OOXML,读取 document.xml、worksheets XML、slides XML 等核心 XML 后再统一进入 sections 清洗链路。
- 补全 README 中空置的多模态文件入库流程图: 用 Mermaid 描述 active library 扫描、按文件类型清洗、统一 StructuredKnowledgeDocument.sections、写入 runtime/frontmatter、语义切块、Embedding、knowledge_chunk 入库和 Agent RAG 召回的完整链路。
- 完善 editor 文件树便携文件操作: 新增文件树多选状态与 Shift 连续选择、Ctrl/Meta 离散选择,支持对多选文件/文件夹批量 Ctrl+C/Ctrl+X/Ctrl+V;文件树节点支持内部拖拽移动到文件夹或根目录;Electron 剪贴板桥接新增读取系统文件剪贴板与外部文件复制/剪切导入能力,使资源管理器复制/剪切文件后点击文件树 Ctrl+V 可落入当前知识库目标目录。
- 新增多模态知识源清洗第一版: 增加 `MultimodalDocumentCleaner`,支持 JSON/JSONL/CSV/TSV/HTML/XML/DOCX/XLSX/PPTX/PDF/图片等文件先清洗为统一 `StructuredKnowledgeDocument.sections`,并接入 `FrontmatterBootstrapService`;默认知识库后缀白名单扩展到常见文档、表格、演示、网页、结构化数据和图片/PDF 资产,后续灌库函数继续统一消费 frontmatter JSON。
- 调整观测面板 UI: 工具注册表页改为单个红绿灯小圆角无阴影卡片,搜索框移动到标题右侧并使用胶囊形态,统计数字合入标题栏;记忆与知识页统一去除内部卡片阴影。
- 修复工具注册表 fallback 直连后端时触发 CORS 预检失败: 前端 fallback 改为无自定义 header 的简单 GET,后端 `/agent/tools` GET/OPTIONS 返回 CORS 允许头,避免 `OPTIONS /agent/tools 405` 导致 `Failed to fetch`。
- 修复工具注册表观测页在部分前端运行环境中请求到 `index.html` 的问题: `fetchAgentTools()` 在相对路径返回 HTML/JSON 解析失败时自动回退到 `http://127.0.0.1:8002/agent/tools`,避免出现 `Unexpected token '<'` 后无法刷新显示。
- 在 Agent 观测面板新增“工具注册表”页: 后端从 AgentCore 最终工具注册表导出 `/agent/tools` 与 gRPC `GetRegisteredTools`,前端新增工具清单/详情双栏视图,可查看工具名称、说明、参数 schema 和注册数量统计。
- 修复知识库内容搜索漏命中: `/knowledge/search` 和 Agent 工具 `search_knowledge` 在索引全文搜索之外增加当前 active 知识库磁盘文本直搜保底,避免文件内容已存在但尚未灌库或索引未更新时搜不到;同时按完整路径去重,避免同名文件互相吞结果。
- 补齐引用发送后的用户气泡展示: `ChatBubble.vue` 和 `ToolBubble.vue` 都会在用户消息气泡上方渲染浅灰引用文本块,并增加回归测试确认引用内容显示在用户消息之前。
- 修复 SSE 流式 Delta 推送的文本叠加/替换问题: 后端 `_stream_chat_request` 在 `status: "complete"` 的最终 chunk 中会再次发送 `content_delta: full_content`，导致前端 on_token callback 收到完整文本作为 delta，与之前逐 token 累积的文本叠加/覆盖。修改 `model_decision.py` 和 `observation.py` 的流式循环：当 `is_complete` 时跳过 `content_delta`，直接使用 `chunk.get("message")` 作为最终消息对象。前端 `chat.ts` 同步修改：delta 事件直接 `last.content += content`（同步追加），非 delta 事件先取消 pending flush 再替换，移除 50ms debounce 定时器。
- 修复联网搜索引擎不可用问题: `duckduckgo_search` v8.1.1 完全失效（所有查询返回 0 结果），替换为 `ddgs` v9.14.4。`builtin.py` 中改为 `from ddgs import DDGS`，修复 API 参数变化（`keywords=` → 位置参数 `query`，`proxies=` dict → `proxy=` 字符串），增加 3 次重试。`requirements.txt` 移除 `duckduckgo_search`，仅保留 `ddgs`。
- 修复 ObservationNode "Missing credentials" 错误: 观察节点在调用 LLM 时未传入用户的 API Key 配置，导致大模型服务返回凭证错误。改为通过 `get_user_llm_overrides(state)` 从 state 读取 LLM 配置。
- 根据用户反馈添加端口管理记忆规则：用完开发服务器后必须主动关闭端口（backend 8002、frontend 5173 等），8082 端口为重要服务不可触碰。
- 修复安全输出审核节点误杀正常内容问题: politics 分类下的 regex `(台|藏|疆|港).*(独|独立)` 使用 `.*` 跨任意距离匹配，导致包含"港+独"（如"璃月港……独特"）的正常段落被拦截。改为 exact 精确匹配"台湾独立"等具体短语。violence 分类同理: `(获取).*(武器)` 会拦截游戏讨论中"获取武器"等正常表述，改为 exact 匹配"购买武器"等明确违规短语。
- 图谱暗色模式背景新增点阵效果: 新建 `editor/src/supercomponents/DotGridBackground.vue` 可复用点阵 SVG 组件，暗色模式下图谱 Canvas 背景为透明，点阵通过 CSS 层渲染在 Canvas 下方，亮色模式网格背景保持不变。
- 修复 editor header 设置图标点按后白屏: `TopCommandBar.vue` 设置按钮原本使用 `<RouterLink to="/settings">`，但路由表中只有 `/` 一条路由，Vue Router 无法匹配导致白屏。改为 `<button>` emit `openSettings` 事件，由 `EditorWorkspace.vue` 通过 `workspaceStore.setMainView('settings')` 切换视图；同步修复 `CommandPalette.vue` 中 `router.push('/settings')` 同一问题，改为 `workspaceStore.setMainView('settings')`。
- 美化设置页所有输入框、按钮和勾选框样式: `SettingsView.vue` 所有 `border-radius: 0` 改为 `border-radius: 999px` 胶囊形，原始终复选框改为自定义 pill toggle 开关；主题按钮激活态配色按开发规范使用主色蓝宝石 #4224EB 与点缀色 #EB2463，跟随系统按钮使用左红右蓝渐变。
- 新增编辑区文本选择工具栏: 新建 `SelectionToolbar.vue` 浮动工具栏，选中文本后出现，提供复制/剪切/粘贴/提问四个按钮。点击"提问"将选中文本作为引用发送到 Agent 对话区，在输入框上方显示灰色引用条。
- 后端新增引用文本上下文注入: `context_builder.py` 的 `build_messages()` 增加 `reference` 参数，注入为 `SystemMessage` 告知模型用户引用的内容；`agent_core.py` 的 `stream_session_prompt()` 和 REST `/agent/stream` 端点同步透传该参数。
- 前端引用流: `ChatInput.vue` 新增 `reference` prop 和引用条显示；`AgentPanel.vue` 监听 `workspaceStore.pendingAgentReference`，消费后打开 Agent 侧栏并将引用文本传给 ChatInput 和 chatStore；`chat.ts` 的 `send()` 增加 `reference` 参数透传到 API；`agent.ts` 的 `streamPrompt()` 增加 `reference` 参数。
- 修复 Agent 引用链路未真正生效: 发送时将引用固化为本轮消息快照并改用 POST body 传输；用户消息 metadata 持久化 `reference`，历史加载和用户气泡可恢复显示；ContextBuilder 将引用材料与问题组合为 HumanMessage，并在上下文压缩及后续历史轮次中保留；gRPC `RunRequest` 同步增加 `reference` 字段。
- 修复 editor 中 `Ctrl+Z` 无响应: Electron 主进程不再抢占 Vditor 的撤回/重做快捷键，编辑器包装层统一将 `Ctrl+Z`、`Ctrl+Y` 和 `Ctrl+Shift+Z` 路由到 Vditor 历史栈，并补充主进程和组件回归测试。
- [x] 增加内置联网搜索引擎duckduckgo,配备搜索结果筛选链条;并在设置中添加用户可配置的代理端口(梯子端口).
- [x] 小功能: 当选择了文档中的一部分话时,会出现一个框,按钮包括: 复制,剪切,粘贴,提问. 点击提问时会将这段话放在agent对话框进行"引用",然后用户可以自行输入prompt来提问.
  - "引用"的含义是在输入框上面挂载一段浅灰色的文本,在上下文看来,这个引用是需要被送入上下文构建器的一起喂给agent来回答的.
- [x] 在agent观测中加一个页,展示agent的所有工具的基本信息,从工具最终的注册表中获取,不区分来源.
- [x] 修好agent的密钥的各种bug,让项目可以免于使用env文件来启动.
- [x] 修复搜索框按内容搜却搜不到的问题.

## 2026-07-09
- 修复知识库搜索串库问题: 全文搜索和语义搜索结果新增 active library root 目录前缀过滤(`_is_in_library`),防止用户多知识库时搜索结果显示非当前库的文件。REST endpoint 和 Agent 内置工具 `search_knowledge` 均已修复。
- 新增搜索页视图(`SearchPage.vue`),嵌入 workspace 三栏布局中心区(通过 ActivityBar 搜索图标或 header 搜索框 Submit 按钮进入): Google 式初始态(标题+搜索框居中),提交后搜索框平滑上移至顶部(`350ms cubic-bezier(0.4, 0, 0.2, 1)`,参考 ChatInput 动画),下方可滚动结果列表; 支持"搜索分离"与"联合搜索"切换,联合模式按文件名合并多路命中; 文件名/snippet 匹配部分用 `<mark>` 高亮; 语义结果标红色「语义」标签; 点击结果切回编辑区并打开对应文件。
- ActivityBar 新增搜索图标(Search),点击切换到搜索视图。
- 新增 `highlightMatch` 工具函数(`editor/src/utils/highlight.ts`),用于搜索结果中文件名和 snippet 的高亮标记。
- Header 搜索框 Search 按钮改为切换到搜索页视图(`setMainView('search')`,保留当前 query); 小搜索框新增联合/分离搜索切换按钮,通过 store 的 `searchUnified` 与搜索页共享。
- 新增 Agent 知识库搜索工具 `search_knowledge`: 工具内部调用三路联合搜索(文件名/全文/语义)并返回格式化文本结果; 语义搜索按文件名去重避免同一文档多个切片重复出现。
- 前端搜索新增历史记录功能: localStorage 持久化最近 20 条搜索词,聚焦搜索框且无输入时在下拉面板显示历史列表,可点击回填并重新搜索,支持一键清空。
- 将搜索框从全屏模态浮层改为 header 内联搜索: 搜索输入框始终显示在 TopCommandBar 正中,brand 左侧、actions 右侧; 聚焦且有查询内容时在输入框下方弹出下拉结果面板; 增加 loading 转圈动画(搜索中时显示在输入框内); 搜索框背景色与主题色相反(暗色主题白底黑字,亮色主题黑底白字); 聚焦时边框高亮为主题色,非聚焦时使用普通边框。
- 修复图谱视图下点击文件树不会回到编辑区的问题: 文件树选择文件或文件夹时会先切换中心工作区到 editor; 同时增强 KnowledgeGraphCanvas 节点 hover 高亮,当前节点显示外晕与更粗描边,相邻关系保留高亮,非相关节点降低透明度以提高对比。
- 修复 editor Preview/Split Markdown 渲染回退风险: `MarkdownPreview.vue` 改为在 Vue DOM 更新和浏览器布局帧完成后队列式触发 Vditor 内部预览渲染,并在 `renderPreview()`、`preview.mode/actions`、Split 双 surface 布局和 Edit 模式 Vditor 配置处增加防回退注释,明确禁止改回静态 `Vditor.preview()`、传参 `renderPreview(markdown)`、全局隐藏 `.vditor-preview` 或启用 Edit 内部双栏预览。
- 继续修复 editor Preview/Split 不渲染: 根据 Vditor 实现补齐 `preview.element.style.display = 'block'` 的 inline 状态修正,因为 Vditor 渲染前检查的是内部 DOM 的 `style.display` 字段而不是 CSS 计算值; 在代码旁加入注释说明该行不能删除。
- 设计并实现 editor 知识图谱第一版前端组件: 新增 `components/knowledge_graph` 模块,将通用图谱类型、文件树适配器、分层 D3 force 布局、Canvas 绘制和几何命中测试拆分为独立文件,`KnowledgeGraphView.vue` 仅负责页面组合和 store 适配; 图谱支持文件树 root/folder/file 节点、同层多节点分 ring 的分层力导、Canvas 缩放/平移/拖拽/hover/选中/双击打开,并新增最小依赖 `d3-force` 与 `@types/d3-force`。
- 为 Agent 增加当前正在观看文档基本信息工具: 新增 editor context 内存服务与 `/agent/editor-context/current-document` REST 端点,editor workspace 在选中文件、切换 tab、保存、删除、重命名和编辑 dirty 状态变化时同步当前文档 path/name/knowledge_dir/size/mtime/dirty/open_tab_count; 新增内置工具 `get_current_viewing_document`,只返回基本信息并提示如需正文继续调用 `read_knowledge_file`。
- 将知识图谱改为三栏工作区内嵌视图: 新增 `GraphPane.vue`,ActivityBar/TopCommandBar/CommandPalette 通过 workspace `mainView` 在编辑器和图谱之间切换,删除独立 `/graph` 页面路由和单页式图谱外壳; 点击图谱节点会切回编辑区并打开对应文件/文件夹。三栏布局的编辑区最小宽度改为 0,Agent 侧栏可拉到剩余空间最大宽度; Agent 输入框与聊天气泡最大宽度限制为 500px。
- [x] Preview又坏了,找codex修掉
- [x] 右键菜单增加一个"打开于",可以用系统资源管理器和系统默认编辑器(VScode)来打开.
- [x] 右键菜单增加一个"在图谱中显示(Ctrl+G)"并绑定快捷键,可以打开图谱页.
- [x] 右键菜单增加一个"问问Agent",自动打开编辑区,并自动agent侧边栏并提问"帮我看看当前打开的文件".
- [x] header上的刷新按钮,点击后刷新文件列表状态和文件内容并将差别内容重新灌库,免得agent写了大量文件之后前端文件状态不刷新或看不到新文件.
- [x] 文件复制到文件树:可以拖拽到文件树或者文件树的一个文件夹,并复制进去.
- [x] 解决文件复制失败的问题: 任何文件都可以复制,但是只有规定的类型的文件才会灌库,类型可以写在全局常量里面且可以配置.
- [x] 将console的所有内容都搬运到editor中,弃用console这个前端.
- [x] 为从console搬过来的这些agent观测条目的滚动条都配备明暗切换.
- [x] 修复agent工具的别名不能正确的在前端agent对话区出现的问题.
- [x] 为文件树上面加一个搜索框:
  - 可以进行 文件名部分匹配搜索+文件内容部分匹配搜索+文件内容语义搜索(RAG) 大搜特搜.
  - 把搜索功能包装成工具给agent.
  - 可以显示搜索历史.
  - 可以逐字输入的时候进行搜索,不必等到输入完
  - 语义搜索可启动可不启动
  - 搜索框右边加一个圆形的"AI帮你搜"按钮,点击后打开Agent对话区,自动发送"在知识库里面找一个文件,特征是[搜索框已经输入的文本]".如果搜索框没有输入文本,则不发送任何东西.
- [x] 基于搜索框,可以进一步做一个单独的搜索页面:
  - 搜索页面初始状态是十分简洁的谷歌浏览器式搜索页,一个搜索框上面加一个大标题.
  - 搜索框是header的小型搜索框的扩大版.搜索结果预览也和小型搜索框是一个东西.
  - 当点击搜索按钮时,搜索框平移到上方,下面分条显示真搜索结果,分为三种搜索结果:
    - 文件名搜索: 标题显示文件名和匹配部分高光,下方小文字显示绝对路径和相对路径,右侧显示内容(可...)
    - 文件内容搜索: 标题显示文件名,下方留一行写内容中的第一个匹配部分"...XXX[匹配部分(高光)]XXX...",下方小文字显示绝对路径和相对路径,右侧显示内容(可...)
    - 语义搜索: 标题显示文件名,下方小文字显示绝对路径和相对路径,右侧显示内容(可...),要打一个"语义"红色圆角标签.
  - 点击搜索结果即可跳转到相应内容的编辑区.
  - header的小搜索框当点击搜索按钮时跳转到这个搜索页面.
  - 升级:搜索页面还可以选择"搜索分离"与"联合搜索":
    - 如果是搜索分离,则上述即是结果的显示;
    - 若为联合搜索,则**不同搜索结果但同一文件**的搜索结果统一显示为: 
      - 标题显示文件名(若文件名匹配则部分高光),下方小字显示相对路径和绝对路径,再下方显示内容,默认显示的是开头之后的部分内容,若为内容匹配命中则显示的是...XXX[匹配部分(高光)]XXX..."这样的中间部分内容.如果是语义搜索出来的,则应该打一个"语义"圆角标签.
      - 如果多种搜索都指向一个文件,那么此文件搜索结果应该是上面结果的特征的并集.即所有命中的特征都要体现.
  - 小型搜索框也要继承这个升级,在语义搜索按钮和让ai搜按钮之间加一个混合搜索开关.

## 2026-07-08
- [x] 新前端的后端设施五步走:
  - [x] 首先在新前端要增加一个像console里面未登录状态一样的简单的输入user_id的输入框,不输入user_id不可进入.
  - [x] 配备灌库函数,重新读取知识库,并灌入向量库:
    1. Agent主动灌库工具,调用是主动调用灌库函.
    2. api,配备前端上传文件的功能.
    要求: 两个前端的知识库应该是相同的,且都可以被用户显式设置.重设知识库时可自动重新扫描和灌库.
  - [x] 扩展用户设置,使得用户可设置知识库目录.一个用户可以拥有很多个知识库,同一个知识库只允许有一个配置,不能让不同的知识库相互有任何干涉,知识库之间独立.
  - [x] 知识库文件API: 针对本地知识库文件的增删改查,以及对于文件夹以及批量文件操作的api.
  - [x] 文件监听: watchdog监听文件的实时变化,实时通知前端并刷新文件树,用户切换根目录时重启监听.
- [x] 编辑器的Edit模式不知为何会在右半边显示预览,而且固定是Agent architecture;Preview模式也有问题,不知为何预览只在左半边出现,而且也是Agent architecture;Split模式和Edit模式一样,但是预览也是这东西.应该修正这些,每个模式有每个模式的不同功能.
- [x] 编辑区的已打开文件横条里面,关闭的叉出现在了文件长度结束的右边,但是需求是把叉固定的放在每个已打开文件条的右边.文件名不用动,不要把文件名居中了.
- [x] "重命名"的快捷键可以是Ctrl+M,包括对文件夹的重命名和对文件的重命名.
- [x] 右键菜单应该像Pycharm一样在每个条目的右边加上操作,比如"新建 (Ctrl+N)".
- [x] 复制路径这个功能不要了,变成三个: 复制文件名,复制绝对路径,复制相对于知识库的路径.
- [x] 知识库路径那一块应该分两行,第一行放知识库名(用户可编辑),第二行用较浅的一行写完整的绝对路径;
- [x] 切换知识库的按钮,以及右边两个按钮,图标都太小了,放大一些.
- [x] 根据开发规范,进行样式调整;
  - Edit/Preview/Split三切换toggle,被选中的一个的圆角矩形应该为蓝色.切换时应该有平滑过渡动画.
  - header上的右侧按钮之中,console的底色应该换为蓝色,文字和图标换成白色.
- [x] 在编辑文件时,当焦点在编辑器内Ctrl+S的时候应该保存,而不是在文件树里面保存.
- [x] 已打开的文件列表的文件名较长的情况下可以用...隐藏,不要搞得文件名和叉子重叠了,或者甚至是冲出框子之外.
- [x] 右键菜单中,复制和剪切和粘贴没有写快捷键.
- [x] 已打开的文件的文件名居中了,应该像原来一样靠左.
- [x] 已打开的文件列表无论打开多少文件,每个文件的宽度是固定的,不应该缩小.
- [x] 干脆去掉editor toolbar按钮吧.
- [x] 已修改但是未保存的文件还应该在文件树的右边也显示红点;且当用户退出而未保存时,应该先冒一个提示框提问要不要保存所有.
- [x] 多选文件按钮右边那个像指纹一样的图标是干什么的,何意味,删掉.
- [x] "复制"对应的是复制文件,而不是复制文件名,应该是说复制了之后可以在真正的文件资源管理器里面粘贴,也可以在文件树的根目录和任何文件夹里面真正的粘贴.
- 美化 editor Agent 对话区: 移除标题栏左侧红绿灯,将 sessions 抽屉切换按钮移至该位置; 无对话时显示居中欢迎屏("MetaWeave"大字 + "在知识库XXX中有什么问题?"小字),输入框居中,发送消息后输入框平滑沉到底部; 气泡配色改为用户红色(#EB2463)发光、Agent蓝色(#4224EB)发光,明暗主题下发光亮度不同; 面板背景改为与编辑区一致的纯白/纯黑(var(--color-canvas-soft))。
- 编辑 `AgentPanel.vue`: 新增 `hasMessages`/`knowledgeTitle`/`isDark` computed,模板增加欢迎屏和 theme class 绑定,重写气泡 CSS 变量和背景色。
- 编辑 `ChatInput.vue`: 新增 `centered` prop,居中定位通过 absolute + translate 实现,与底部常态间用 350ms cubic-bezier 过渡。
- 修复 editor Agent 输入框动画: 改为始终 absolute + left:50% + translateX(-50%),两态都使用 bottom 数值(16px ↔ 50%),width 同步过渡(calc(100%-32px) ↔ min(90%,400px)),解决 auto↔数值无法 CSS 动画的问题; 欢迎屏底部定位改为 calc(50%+100px) 紧贴居中输入框上方; MessageList 增加 padding-bottom:80px 防止消息被底部输入框遮挡。
- 修复删除文件后同级文件及文件夹内文件错误显示红点: `ignoreNextTreeEvent` 从 boolean 改为 counter(`ref(0)`),所有文件系统变更操作(`saveFileByPath`/`importFilesToPath`/`deleteNode`/`createFileAt`/`createFolderAt`/`pasteNode`/`renameNode`)在执行前递增计数器,`tree_dirty` 事件处理中递减并仅在计数器归零时调用 `markOpenTabsDirty()`,避免单个操作触发多次 SSE 事件导致兄弟文件被错误标记为 dirty。
- [x] 增加用户本机文件服务MCP(已被自带的文件管理系统API优化,不需要了)
- [x] 把console的agent对话区和逻辑复制到editor中来(删掉当前的占位agent对话区内容),也就是ChatView那一块,不包括可观测面板和Settings区,只要Chat区.与此同时,会话记录也搬,作为editor的agent对话区旁边的一个按钮点击后平滑移动出的抽屉侧边栏,稍微高一点样式.
- [x] 修复Preview以及Split的markdown无法渲染的问题(观察到从Edit切换到Preview的时候底下的蓝色块没有动),并将默认模式设置为Edit模式.
- [x] 将文件系统管理API的函数对接到Agent的内置工具,如此即可不使用文件MCP却让Agent拥有操作文件系统的能力吗?
- [x] 美化Agent对话区,具体美化:
  - [x] 将背景变为和编辑区一致的纯白色/纯黑色,气泡则遵循开发规范的双主色系模式,用户发出红色气泡,Agent发出蓝色气泡,都要发光,且明暗色下亮度有不同.
  - [x] 初始无对话状态下,输入框应该居中,放在Agent对话区的正中间偏下一点,然后上面像KIMI一样写大字"MetaWeave",一行小字"在知识库XXX中有什么问题?",当用户输入并发送消息时输入框平滑平移地沉下去.
  - [x] 去掉Agent对话区标题左边的红绿灯,将右边的展开侧边栏按钮放在这个位置.
- [x] 让编辑区已打开的文件列表下面横向的滑动条也可以明暗切换.
- [x] 修复删除一个文件后同级文件及文件夹内文件会错误的重新在文件树中显示红点的问题.
- [x] 修复对话框会遮住对话气泡的问题,对话气泡应该以对话框输入框的上半部分作为边界.



## 2026-07-07
- 更新 PyInstaller `AgentService.spec`: 打包清单补齐 `editor/dist`,并改为显式校验 `console/dist`、`editor/dist` 与 `resources` 目录存在后再构建,产物仍输出为 `dist/AgentService.exe`。
- 修复 editor Agent 会话框亮色主题仍显示暗色的问题: `AgentPanel.vue` 的面板、标题栏、assistant 气泡和输入框背景改为消费 editor 全局主题变量; 同时将 Agent 会话框右上角两个图标按钮改为圆形、模式按钮改为胶囊形。
- 细化 editor 顶栏明暗切换按钮: 亮色状态改为白底红边红太阳,暗色状态改为深黑底淡黄边与淡黄色实心月亮,降低亮色按钮饱和度。
- 调整 editor 顶栏明暗切换按钮: 亮色主题显示开发规范红色按钮与太阳图标,暗色主题显示深黑按钮与淡黄色实心月亮图标,继续复用现有 Lucide Sun/Moon 图标。
- 修正 editor 顶栏 Console 按钮语义: 恢复原实心蓝色样式,点击行为改为复用左侧 ActivityBar 的 Agent 按钮逻辑,用于展开/收起右侧 Agent 对话栏,不再跳转 `/console`。
- 调整 editor IDE 顶栏与 Agent 侧栏样式: 右侧 Agent 对话区去掉浮动卡片外边距、圆角和上下/右侧外框,改为与工作区矩形栏直角融合; 顶栏 Command/Console 使用胶囊按钮,中间图标按钮与主题按钮使用圆形按钮; 顶栏左侧标题从 `Editor` 改为 `知识库-[知识库名]`。
- 调整 editor Electron 开发启动行为: `npm run dev:electron` 不再默认打开 detached Developer Tools; 如需临时调试,可设置 `ELECTRON_OPEN_DEVTOOLS=true` 后再启动。
- 修正 editor Agent 面板迁移偏差: 消息渲染层改回 console 的 `MessageBubble -> ChatBubble/ToolBubble` 路由结构,补齐 `ThinkingInline`、`ToolCallInline` 与 `LoaderCube`; tool 模式 action 节点只显示聚合后的工具调用条,不再显示节点名或重复思考过程。会话选择改为父层显式执行 `select -> clear -> loadHistory`,输入框在流式过程中保持可输入并复用 chat store 的中断上一轮逻辑。
- 将 console 的 Agent Chat 核心能力迁入 editor 右侧 Agent 面板: 新增 editor 侧 `/sessions`、`/agent/stream` API 封装、会话 store、聊天 store、Markdown 渲染和流式消息组件; `AgentPanel.vue` 删除旧占位问答,改为 console 风格聊天区、会话历史抽屉、新建会话和聊天/工具渲染模式切换,同一 `user_id` 与 console 共享会话历史。
- 修复 editor Preview 渲染成原始 Markdown 且顶部出现 Desktop/Wechat/知乎按钮的问题: `MarkdownPreview.vue` 不再向 `renderPreview()` 传入 Markdown 原文,而是先同步 Vditor value 后无参触发解析渲染; 同时设置 `preview.actions = []` 禁用 Vditor 内置导出/平台预览按钮。
- 修复 editor 三态切换需要点第二次蓝色底块才移动的问题: 模式按钮改为在 pointerdown 阶段直接写入 `editorMode` 并用当前按钮元素同步计算指示块宽度和位置,键盘触发则保留 click 路径,避免依赖 watcher 下一帧反查 active 按钮。
- 修复 editor 三态切换状态不响应的问题: `EditorPane.vue` 通过 `storeToRefs` 显式读取并写入 `editorMode`,避免模板和脚本读取 Pinia proxy 时出现状态未可靠触发的情况; 蓝色切换指示块禁用 pointer events,防止遮挡模式按钮点击。
- 修复 editor Preview/Split 仍不显示预览的问题: `MarkdownPreview.vue` 改为创建只显示 preview pane 的 Vditor 实例,复用 Vditor 内部渲染管线而不是静态 `Vditor.preview()` 脚本加载路径; `EditorPane.vue` 将 Edit/Preview 两个 section 改为受限 flex 容器,避免 Split 中 Vditor 编辑器撑满整行。
- 恢复 editor Edit 模式的 Vditor 所见即所得体验: `VditorEditor.vue` 从源码 `sv` 模式改回 `wysiwyg`,重新启用代码块与数学块预览,并移除全局隐藏 `.vditor-preview` 的 CSS,避免标题井号不隐藏、PlantUML/代码块预览被禁用; `MarkdownPreview.vue` 增加渲染失败 fallback 便于定位预览异常。
- 修复 editor Preview/Split 首次切换时 Markdown 预览可能为空或不渲染的问题: `MarkdownPreview.vue` 在 DOM 挂载后补执行 Vditor preview 渲染,避免 watcher 早于预览容器 ref 执行后丢失首帧渲染; 同时将 editor 默认模式从 Split 改为 Edit,并完成对应 TODO。
- 修复 editor Preview 模式 Markdown 渲染不完整的问题: `MarkdownPreview.vue` 不再使用只识别 `#`/`##` 的临时行级字符串规则,改为调用 Vditor preview 渲染器,使 `###` 及更低级标题、列表、代码块等 Markdown 语法按完整规则渲染。
- 优化 editor 左侧活动栏交互: 文件树与 Agent 侧边栏不再通过 `display:none` 瞬间隐藏,改为布局列宽、透明度和位移的平滑收缩/展开动画; 拖拽调整侧栏宽度时临时关闭过渡,保持 resize 手感稳定。
- 统一 editor 蓝色交互样式: 移除文件树 hover/选中、拖拽投放、活动栏激活态和文件类型图标中的天蓝色残留,改用开发规范规定的主蓝 `#4224EB` 及浅主蓝变量; Edit/Preview/Split 三段切换指示块改为按当前按钮真实宽度和位置滑动,避免 Edit 状态下覆盖到 Preview。
- 调整 editor 细节动效: Edit/Preview/Split 三段切换改为蓝色指示块平滑滑动; 文件树条目 hover 改为浅蓝主题色; 根目录右侧新建和多选按钮 hover 改为圆形浅蓝主题反馈。
- 移除 editor workspace store 中残留的 `agent_architecture.md` mock 文件树、mock 内容和默认打开 tab,避免后端文件树加载竞态或失败时回退显示固定的 `Agent architecture` 文本; 编辑区无打开文件时改为显示空态提示。
- 修复 editor Edit/Preview/Split 间歇性混入 Vditor 内置预览的问题: Vditor 改为 source-view 编辑模式,初始化参数和 after 回调都强制 `preview.mode='editor'` 并清理内部缓存; 同时在全局样式中隐藏 Vditor 自带旁路预览容器,确保 Edit 只显示编辑器、Preview 只显示自定义预览、Split 才显示双栏。
- 修复 editor 已打开文件 tab 的长文件名溢出: tab 使用固定宽度网格布局,标题列强制 `ellipsis` 截断,dirty 红点和关闭按钮固定在右侧列,避免长文件名与关闭按钮重叠或冲出 tab。
- 为 editor 文件树增加按后缀切换的 Material 风格文件图标: 代码、数据、图片、表格、压缩包、Markdown 等类型使用不同图标和颜色,提升知识库文件树的可扫读性。
- 继续完成 editor TODO 新增 BUGs: 右键菜单为复制/剪切/粘贴补充快捷键并接入 `Ctrl/Cmd+C/X/V`; 文件 tab 固定宽度且文件名左对齐; 移除 editor toolbar 按钮; dirty 文件在文件树右侧显示红点; 关闭 Electron 窗口前提示是否保存所有未保存文件; 移除文件树 header 中无语义的状态图标; Electron 下复制/剪切文件会把真实文件路径写入系统剪贴板,同时保留文件树内部粘贴能力。
- 完成 TODO 中剩余 editor BUGs: 文件 tab 关闭按钮固定到条目右侧且文件名保持左对齐; 新增 `Ctrl/Cmd+M` 对当前选中文件或文件夹进入重命名; 右键菜单增加快捷键提示并将“复制路径”拆成复制文件名、绝对路径和相对路径; 文件树根目录栏改为知识库名与完整路径两行显示; 放大根目录切换/新建/上传图标; Edit/Preview/Split 选中态改为蓝色并加过渡; Vditor 内部捕获 `Ctrl/Cmd+S` 保存当前文件。
- 为多知识库配置增加可编辑的知识库显示名: `PUT /settings/profile/knowledge-dir` 与 gRPC `UpdateUserKnowledgeDir` 支持可选 `name`,editor 文件树标题栏和 Settings 页面可保存 active 知识库名称; 同一路径切换回来时可通过名称确认后端恢复了原有知识库记录。
- 为 editor 文件树和编辑器增加内置快捷键: `Ctrl/Cmd+S` 保存当前文件,`Ctrl/Cmd+N` 在当前选中目录或当前文件所在目录新建文件,`Ctrl/Cmd+Shift+N` 新建文件夹,`Ctrl/Cmd+D` 对当前选中文件/文件夹打开删除确认框,`Esc` 关闭右键菜单/原地编辑/删除确认。快捷键暂不提供用户自定义设置。
- 修复 editor 非 Electron 环境下切换知识库的错误 fallback: 根目录按钮不再退回到 `webkitdirectory` 文件夹上传控件,避免浏览器弹出“上传 N 个文件到此站点”的权限框,也避免前端假切库但后端 active root 仍停留在默认 `resources/knowledge`。当 Electron directory picker 不可用时,文件树底部会显示明确错误。前端 API 客户端现在会读取后端 `detail`,使 422 错误显示具体原因。
- 修复 editor 切换知识库后回落默认 `resources/knowledge` 的问题: 新增 `PUT /settings/profile/knowledge-dir` 与 gRPC `UpdateUserKnowledgeDir`,切换根目录时先持久化 active 知识库设置,再对当前 active root 执行 rebuild; 前端刷新 profile 统一使用完整后端 profile 映射,避免只缓存 `knowledge_dir` 导致 active library 缺失。文件树切换后即使 rebuild 阶段失败也会按已保存的 active root 重新加载,新建文件会落到当前 active 知识库目录。
- 增强用户知识库设置恢复逻辑: 当历史数据库中存在知识库配置但缺少 active 标记时,`SettingsService` 会恢复最近更新的库为 active,避免后端重启后使用默认 knowledge 目录重建 active 配置。
- 调整 editor 文件树交互: 新建文件/文件夹不再使用浏览器输入框,而是在文件树中插入临时条目并原地输入,提交后再调用后端创建接口; 重命名改为在当前文件名位置原地编辑; 删除确认改为 editor 自己的 modal,移除浏览器 `prompt` / `confirm`。
- 扩展 editor 文件管理能力: `FileTreePanel.vue` 在知识库根目录右侧新增“新建文件”和“多选文件”按钮,并为文件树节点补充右键菜单,支持新建、复制、剪切、复制路径、粘贴、重命名和删除; `workspace.ts` 新增复制/剪切缓冲、粘贴目标路径去重、重命名后同步已打开 tab 等前端逻辑。
- 补齐文件管理后端接口: `KnowledgeLibraryService`、REST `/knowledge/files/file` 与 `/knowledge/files/copy` 支持新建文件和复制文件/文件夹,重命名不再覆盖已有目标; 同步扩展 `protos/agent_service.proto`、生成的 gRPC 文件和 `servicer.py`,新增 `CreateKnowledgeFile` 与 `CopyKnowledgePath` RPC。
- 完成新 editor 前端后端设施第四步: 扩展 `agent_service/services/knowledge_library_service.py` 与 `agent_service/api/rest/knowledge.py`,新增 active 知识库文件树列表、UTF-8 文本读取/保存、文件夹创建、路径删除、路径重命名和上传接口; 保存编辑器文件只写入磁盘并刷新文件树,不会触发向量灌库,灌库仍只由显式扫描/重建或上传入口触发。
- 同步扩展 `protos/agent_service.proto`、生成的 gRPC Python 文件与 `agent_service/api/grpc/servicer.py`: 为知识库文件树、读写、创建文件夹、删除和重命名补齐 gRPC RPC,保持 REST/gRPC 面板能力一致。
- 完成新 editor 前端后端设施第五步: `knowledge.py` 的文件事件流优先使用 watchdog 监听 active 知识库目录,通过 SSE 通知前端刷新文件树; watchdog 缺失时回退到文件树签名轮询。用户切换根目录时前端重启事件流,等价重启后端 observer。
- 对接 editor 前端文件树与编辑器: 新增 `editor/src/api/knowledge.ts`,扩展 `workspace.ts` 和 `FileTreePanel.vue`,实现从后端加载文件树、点击文件读取真实内容、保存文件落盘、拖拽上传到根目录或目标文件夹、根目录切换后刷新树并重启 watcher。

## 2026-07-06
### 前端 — 新增 editor 知识库编辑器前端骨架

- 在 `editor/` Vite + Vue + TypeScript 脚手架中实现首版知识库工作台: 顶部命令栏、左侧文件树、中间 Vditor 编辑/预览/分屏区域、右侧 Agent 占位对话面板、命令面板、设置页和知识图谱占位页。
- 新增 `editor/src/stores/settings.ts` 和 `editor/src/stores/workspace.ts`: 统一管理主题、知识库路径、模拟文件树、打开标签、编辑内容、索引状态和 Agent 占位消息。
- 新增 `editor/src/router/api_routes.ts` 与 `editor/src/api/client.ts`: 预留后续后端 settings、knowledge files、watchdog events、indexing 和 Agent streaming 接口,前端组件不直接硬编码 API 路径。
- 新增 `editor/src/assets/ui-system.css` 和 `editor/src/assets/main.css`: 按 editor 规范实现 VoltAgent/Cursor 风格的暗色 surface ladder、蓝宝石主色、红色点缀、轻圆角、细边框、响应式三栏布局和 Vditor 基础样式覆盖。
- 更新 `editor/package.json` 增加 `vditor` 与 `lucide-vue-next` 依赖,更新 `editor/package-lock.json`; 构建、类型检查、lint 和单元测试均通过。

### 前端 — editor 增加无边框 Electron 桌面壳

- 新增 `editor/electron/main.cjs`: 创建 `frame: false` 的无边框 `BrowserWindow`,开发模式加载 Vite dev server,生产模式加载 `editor/dist/index.html`,并通过 IPC 支持最小化、最大化/还原、关闭窗口和外部链接打开。
- 新增 `editor/electron/preload.cjs`: 使用 `contextBridge` 暴露 `window.agentEditorDesktop`,保持 renderer 侧 `contextIsolation` 与 `nodeIntegration: false`,避免 Vue 应用直接访问 Node.js。
- 修改 `editor/src/components/editor_workspace/TopCommandBar.vue`: 让顶部栏作为 Electron 拖拽区,仅在桌面环境显示最小化、最大化和关闭按钮,普通 Web 运行时保持原有表现。
- 修改 `editor/src/router/index.ts` 和 `editor/env.d.ts`: Electron 环境使用 hash history,避免打包后 `file://` 路径刷新失效,并补充桌面 preload API 类型。
- 更新 `editor/package.json` 与 `editor/package-lock.json`: 增加 `electron` 开发依赖和 `dev:electron` / `electron` 脚本; 构建、lint、单元测试、Electron CJS 语法检查和 Electron 可执行体版本检查均通过。

### 前端 — editor 修复 Electron CSP 安全警告

- 修改 `editor/vite.config.ts`: 新增仅在生产构建阶段执行的 CSP 注入插件,避免开发模式下 Vite/HMR 被 CSP 误拦导致 Electron 黑屏; 生产产物仍禁止 `unsafe-eval`,限制脚本、图片、字体、worker 和连接来源。
- 修改 `editor/index.html`: 移除开发源码中的 CSP meta,保留页面标题 `AgentService Editor`; 同时固定 Vite dev server 为 `127.0.0.1:5173` 且 `strictPort: true`,避免 Electron 连接到错误端口。
- 构建、lint 和单元测试均通过,并确认源码 HTML 不含 CSP、`dist/index.html` 含生产 CSP。

### 前端 — editor 移除文件树状态标签

- 修改 `editor/src/components/editor_workspace/TreeNode.vue`: 移除左侧文件树中每个文件/目录后的彩色索引状态标签,文件树仅保留展开箭头、文件类型图标和名称,减少导航区视觉噪音。
- 构建、lint 和单元测试均通过。

### 前端 — editor 文件树与编辑器改为 IDE 无缝面板

- 修改 `editor/src/views/EditorWorkspace.vue`: 将左侧文件树和中间编辑器从独立圆角卡片调整为类似 PyCharm 的无缝 IDE 面板,移除两者之间的外部间距和圆角,仅保留细边框分隔; 右侧 Agent 对话区继续保留卡片式独立面板。
- 修改 `editor/src/components/editor_workspace/FileTreePanel.vue` 与 `EditorPane.vue`: 调整面板背景和标签栏/编辑区背景,让文件树与编辑区更像同一个编辑器壳体的一部分。
- 构建、lint 和单元测试均通过。

### 前端 — editor 完成 TODO 中的编辑器视觉细化

- 修改 `editor/src/components/editor_workspace/TreeNode.vue` 与 `FileTreePanel.vue`: 左侧文件树选中态从红蓝渐变圆角块改为无圆角、左右贴边的蓝色细边框条形。
- 修改 `editor/src/components/editor_workspace/EditorPane.vue` 与 `VditorEditor.vue`: 将编辑模式切换和保存按钮移动到文件标签栏右侧,移除独立文件元信息栏; Vditor 工具条默认隐藏,通过标签栏右侧的小按钮展开。
- 修改 `editor/src/views/EditorWorkspace.vue`: 移除工作区背后的红蓝径向渐变,改为与文件树一致的 `canvas-soft` 背景。
- 修改 `editor/src/components/editor_workspace/TopCommandBar.vue`: 顶栏左侧统一显示 `Editor`,移除 `AgentService Editor`、知识库路径和红蓝胶囊标识。
- 修改 `editor/src/assets/ui-system.css` 与 `main.css`: 收敛界面字体和代码字体变量,增强 Vditor 编辑区对全局字体变量的使用。
- 同步将 `TODO.md` 中对应 5 个 editor 子任务标记为完成; 构建、lint 和单元测试均通过。

### 前端 — editor 完成新增编辑器交互 TODO

- 修改 `editor/src/stores/workspace.ts`、`FileTreePanel.vue` 与 `TreeNode.vue`: 新增独立的文件树选中路径,让目录点击也能高亮; 文件树选中态改为浅蓝色细边框条形,并加入 150ms 的短滑动反馈。
- 修改 `editor/src/components/editor_workspace/TopCommandBar.vue`: 将无边框 Electron 顶栏高度和右侧按钮尺寸压缩到更接近编辑器工具条的密度。
- 修改 `editor/src/components/editor_workspace/EditorPane.vue` 与 `editor/src/assets/main.css`: 压缩已打开文件标签栏高度、移除标签栏横向滚动条,并将 Vditor 功能条改为覆盖式显示,避免展开时横向挤压主要编辑区。
- 同步将 `TODO.md` 中新增 5 个 editor 子任务标记为完成。

### 前端 — editor 修复文件树选中蓝条不可见

- 修改 `editor/src/components/editor_workspace/FileTreePanel.vue`: 文件树选中路径增加 `selectedPath` 兜底,避免运行中热更新后的 Pinia store 缺少 `selectedTreePath` 时选中态丢失。
- 修改 `editor/src/components/editor_workspace/TreeNode.vue`: 将选中蓝条改为明确的 3px `::after` 左侧条,并移除 `color-mix()` 依赖,确保文件和文件夹点击后都能稳定显示浅蓝选中条。

### 前端 — editor 移除文件树选中深蓝竖条

- 修改 `editor/src/components/editor_workspace/TreeNode.vue`: 移除文件树选中态左侧 3px 深蓝竖条和对应动画,保留浅蓝背景与细边框作为选中反馈。

### 前端 — editor 实现文件树拖拽导入与根目录切换占位逻辑

- 修改 `editor/src/components/editor_workspace/FileTreePanel.vue`: 移除独立的 `Drop files here` 投放框,改为整个文件树区域接收拖拽文件; 在 `knowledge root` 左侧新增目录切换按钮,通过前端目录选择器更新本地根目录并触发扫描/灌库占位流程。
- 修改 `editor/src/components/editor_workspace/TreeNode.vue`: 为目录节点增加拖拽投放事件,拖到文件夹时阻止冒泡并把文件导入该目录; 拖到普通文件或树空白处时继续由根目录投放逻辑处理。
- 修改 `editor/src/stores/workspace.ts` 与 `settings.ts`: 新增前端 mock 的文件导入、目录扫描、内容预览读取和索引中状态更新逻辑,为后续后端复制文件与灌库 API 接入预留交互入口。

### 前端 — editor 收紧根目录栏

- 修改 `editor/src/components/editor_workspace/FileTreePanel.vue`: 根目录切换按钮改为无边框图标按钮,移除 `KNOWLEDGE ROOT` 标签文案,并将根目录栏竖直高度压缩为更窄的编辑器侧栏标题条。

### 前端 — editor 增加活动栏与可拖拽三栏布局

- 新增 `editor/src/components/editor_workspace/ActivityBar.vue`: 实现类似 PyCharm 的左侧竖向无文字活动栏,包含文件树、Git、Agent、知识图谱和设置图标按钮,并通过原生 tooltip 提示用途。
- 修改 `editor/src/views/EditorWorkspace.vue`: 三栏布局改为可拖拽宽度,文件树和 Agent 两侧栏低于 150px 阈值时自动折叠到旁边; 活动栏文件夹和 Agent 按钮可重新展开对应侧栏,图谱和设置按钮跳转到现有路由。

### 前端 — editor 增加 user_id 入口

- 新增 `editor/src/components/common/UserIdGate.vue`: editor 启动时若未设置 `user_id`,展示简单输入框并阻止进入路由页面。
- 修改 `editor/src/stores/settings.ts` 与 `App.vue`: 将默认 `userId` 改为空,通过 settings store 持久化输入的 `user_id`,并兼容清理旧版 `local-user` 默认值; 同步将 `TODO.md` 中新前端后端设施第一步标记为完成。

### 前后端 — editor user_id 入口接入后端 profile API

- 新增 `agent_service.models.user_settings.UserSettingsRecord`,并扩展 `SettingsService.ensure_user_profile()`: 输入 `user_id` 时初始化用户设置档案,默认知识库目录使用 `AgentConfig.storage.knowledge_dir`。
- 修改 `agent_service/api/rest/settings.py`: 新增 `GET/POST /settings/profile`,供 editor user_id 入口确认或初始化用户档案。
- 修改 `protos/agent_service.proto`、`agent_service/api/grpc/servicer.py` 与生成的 gRPC Python 文件: 同步新增 `EnsureUserProfile` RPC,保持 REST/gRPC 用户设置入口一致。
- 新增 `editor/src/api/settings.ts`,并修改 `UserIdGate.vue` 与 `editor/vite.config.ts`: editor 输入 `user_id` 后先请求后端 profile API,成功后才写入本地 settings 并进入应用; 开发态代理 `/settings` 等 API 到后端 `127.0.0.1:8002`。

### 前端 — console user_id 入口接入统一 profile API

- 修改 `console/src/api/settings.js`、`router/api_routes.js` 与 `composable/useUserId.js`: console 设置 `user_id` 时先调用 `POST /settings/profile`,成功后才写入本地 user_id。
- 修改 `console/src/views/ChatView.vue` 与 `DashboardView.vue`: user_id 输入入口增加后端确认中的 loading 状态和错误提示,与 editor 的用户初始化入口对齐。

### 前端 — 两个前端启动时刷新用户设置

- 修改 `editor/src/stores/settings.ts` 与 `App.vue`: 本地已有 `user_id` 时启动先调用 `/settings/profile` 刷新用户设置,成功后再进入 editor,失败则清空本地 `user_id` 回到入口。
- 修改 `console/src/composable/useUserId.js`、`stores/settings.js` 与 `App.vue`: console 启动时用本地 `user_id` 刷新后端 profile,并将用户设置档案保存到 settings store,失败时清空本地入口状态。

### 后端 — 增加用户知识库重建与上传灌库入口

- 新增 `agent_service/services/knowledge_library_service.py`: 提供用户知识库重建函数,按用户设置的 `knowledge_dir` 结构化 Markdown/TXT 文件并写入向量库,同时清理已删除源文件对应的旧 chunk。
- 修改 `frontmatter_bootstrap.py`、`knowledge_ingestion.py` 与 `longterm_memory_service.py`: 支持指定知识库目录、指定 frontmatter 输出目录、按用户写入知识切片和按来源删除旧切片。
- 新增 `agent_service/api/rest/knowledge.py` 并注入 `KnowledgeLibraryService`: 提供 `POST /knowledge/rebuild` 与 `POST /knowledge/files/upload`,上传文件落入用户知识库目录后自动重新灌库。
- 修改 `protos/agent_service.proto`、`agent_service/api/grpc/servicer.py` 与生成的 gRPC Python 文件: 同步新增 `RebuildKnowledge` 和 `UploadKnowledgeFile` RPC。
- 修改 `agent_service/tools/builtin.py` 与 `retrieval_service.py`: 新增 Agent 主动重建知识库工具,并让知识库检索优先读取当前用户的知识切片; 用户尚无切片时回退到默认 `system` 知识库,同时在 Chroma 返回全 0 分候选时回退到 JSON 向量检索。
- 修改 `TODO.md` 与 `agent_service/requirements.txt`: 将新前端后端设施第二步标记完成,并补充上传接口所需的 `python-multipart` 依赖。

### 前后端 — 用户多知识库设置与 editor 根目录切换接入

- 修改 `agent_service/models/user_settings.py` 与 `SettingsService`: 新增 `user_knowledge_libraries` 表,同一用户同一路径生成稳定 `library_id`,profile 响应返回 active 知识库与知识库列表。
- 修改 `KnowledgeLibraryService` 与 `retrieval_service.py`: 灌库和检索按 `user_id + library_id` 隔离知识切片与 frontmatter 目录,避免同一用户不同知识库互相删除或召回。
- 修改 `protos/agent_service.proto`、`agent_service/api/grpc/servicer.py` 与生成的 gRPC Python 文件: 同步扩展 profile/rebuild 响应中的知识库配置字段。
- 修改 `editor/electron/main.cjs`、`preload.cjs` 与 `env.d.ts`: 为无边框 Electron editor 暴露目录选择 IPC,让渲染层能拿到真实本机目录路径。
- 修改 `editor/src/api/settings.ts`、`stores/settings.ts` 与 `FileTreePanel.vue`: 根目录按钮在 Electron 中选择目录后调用 `/knowledge/rebuild`,由后端保存 active 知识库并重灌库,前端刷新 profile 展示新根目录。
- 修改 `TODO.md`: 将新前端后端设施第三步标记为完成。


## 2026-05-17
- 修复 Obs 面板在工具模式下所有卡片数据不完整的问题: `useObsData.js` 中 `currentMessageTraces` 原来只取最后一条 assistant 消息的 trace, 在工具模式下每个图节点 (planner/agent/action/observation) 各自一条 assistant 消息, 导致语言轨迹、节点执行时间线、工具轨迹和运行时路径都只展示最后一个节点的数据。改为从尾部向前扫描, 收集最后一条 user 消息之后的所有 assistant trace, 使语言轨迹/节点时间线/工具轨迹/运行时路径在工具模式下正确聚合整个轮次的数据。(对话模式行为不变)
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
    - 很好,我得到了海洋的知识库知识.这些知识很有用.                    (Observation节点的输出)
    - 接下来我准备使用待办工具来添加待办:                             (Planner节点的输出)
    - （调用待办工具,并展示待办工具的输入和输出）
    - 我已经完成了用户的任务,接下来进行最终回复.                       (Observation节点的输出)
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

## 2026-05-15

### 后端 — Agent 思考轨迹 (trace human_readable)

- 为 `PlannerNode` 的所有 trace 事件增加 `human_readable` 字段,包含人类可读的规划描述（如"我需要分3步来完成这个任务"、"这是一个简单问题,直接作答"等）。
- 为 `ToolCallNode` 拆分工具调用 trace：每个工具调用生成两条独立 trace（`tool_call_start` + `tool_call_end`）,分别描述正在调用哪个工具及参数摘要、以及工具返回结果摘要。同时为 fallback 路径（LangGraph ToolNode 和未注册工具）增加 `human_readable`。
- 为 `ObservationNode` 的所有 trace 事件增加 `human_readable` 字段,根据不同决策（answer/compress/continue）输出不同描述文本。
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

- 将 `ContextBuilder._build_retrieved_context()` 中长期记忆和知识库的检索结果从注入全文改为注入条数提示：`"系统中检索到 N 条与当前问题相关的长期记忆，如需查看具体内容请调用 get_long_term_memory 工具"`。重要事实摘要（CompressNode 输出的压缩上下文）保持全文注入不变。这解决了"模型看到预注入答案后直接复述、跳过工具调用"的问题，迫使模型在需要记忆/知识内容时主动调用工具，从而触发 Planner → ToolCall → Observation 完整思考链路。
- 同步更新 `retrieval_context_system_prompt`：从"参考材料 — 用自己的话总结"改为"上下文索引 — 使用工具获取详细内容"，明确告知模型哪些内容已直接提供、哪些需调工具获取。
- 同步更新主 `system_prompt` 中【核心机制】段落：从"系统自动注入上下文"改为"系统预检索条目数量作为索引提示，详细内容需调工具获取"。

### 前端 — 修复 SSE 中 action 节点内容污染 assistant 气泡

- 修复 `chat.js` 的 `send()` 中 SSE chunk 处理逻辑：当 `chunk.node === 'action'` 且有内容时，将工具返回结果写入独立的 `role: 'tool'` 消息，不再覆盖 assistant 占位气泡。同时 action 节点的 trace（工具调用开始/结束描述）仍附加到 assistant 消息的 trace 数组中供 ThinkingSteps 展示。planner/observation/compress 等纯 trace 节点事件也改为仅附加 trace 而不触发 content 更新。解决了流式过程中工具返回全文在对话框主体闪现、重进后才正确归位到 tool 灰框的同步/异步渲染不一致问题。

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
- 实现知识库图谱基础闭环: 新增 SQLite 点边与抽取状态表、基于 frontmatter sections 的小模型候选抽取服务、证据/白名单校验、知识库入库旁路抽取、图谱 REST 查询接口和 editor 端知识库图谱模式。
- 在 `README.md` 的知识库业务设计中补充知识图谱实体关系抽取方案,明确基于 frontmatter sections 的文字抽取、小模型两阶段候选生成、证据校验、SQLite 点边落库、前端 Canvas 复用和失败降级策略。
- 让 PDF 清洗链路导出页面内图片资产并在 frontmatter section 写入 Markdown 图片: 记录图片顺序、页码、xref、格式、bbox、asset_path 与 public_url, 通过 `/knowledge/assets` 静态挂载供 editor 预览, 不启用 OCR 或图片语义抽取。
- 修复启动全局灌库重复消费用户知识库的问题: 启动 frontmatter 生成和向量入库都会排除已登记在全局 `resources/knowledge` 下的用户知识库子树, 避免手动灌库后又被写入全局 frontmatter/Knowledge owner。
- 兼容历史用户命名空间: 当 `runtime/frontmatter/users/<user>` 存在时, 启动全局灌库会额外跳过 `resources/knowledge/<user>` 和 `runtime/frontmatter/<user>`, 防止默认知识库仍指向全局根时重复消费 editor 用户文件。
- 修复知识图谱未体现灌库规模的问题: 图谱抽取现在先同步 frontmatter 文档节点, 小模型实体关系抽取失败只影响语义边而不再导致文档节点缺失; editor 图谱面板新增 Refresh 按钮用于灌库后重新拉取 Knowledge 图谱。
