# MetaWeave 架构

MetaWeave 是一个智能文档问答系统。用户上传 PDF、Word 等文档后，系统自动解析文本内容并建立索引，随后用户可用自然语言发起提问，系统结合 RAG 检索增强生成与 ChromaDB 向量数据库产出答案，并提供答案溯源、自动摘要和 Agent 思考过程可追溯可视化的完整能力。

---

## 宏观分层

整个系统沿纵轴切为四层，每层只依赖其下一层：

第一层是接入层。FastAPI 提供 REST 接口（端口 8002），gRPC Server 提供等效的 protobuf 接口（端口 50051）。打包模式下 FastAPI 同时托管前端静态文件，无需额外 Web server。两套接口的请求和响应字段保持一致，底层共享同一个 AgentCore 实例。

第二层是编排层。AgentCore 是系统的逻辑心脏，负责接收用户输入、通过 LangGraph 编译的状态图执行 ReAct 循环、管理流式 SSE 事件推送、协调取消中断和部分输出保存。AgentCore 不直接操作数据库，全部持久化通过 MessageService 和 SessionService 完成。图的结构由 AgentGraphBuilder 装配，节点实现在独立的模块中。

第三层是服务层。所有业务能力以 Service 对象的形式提供，通过构造参数显式注入依赖。消息管理（MessageService）负责消息的 CRUD 和已摘要标记，会话管理（SessionService）负责会话生命周期和探索状态持久化，长期记忆（LongTermMemoryService）统一管理 SQLite 关系记录和 ChromaDB 向量写入，上下文构建（ContextBuilder）拼装当前轮的完整 LangChain messages，统一检索（MemoryRetrievalService）执行多路召回重排链路，安全审核（SafetyService）编排三层审核流水线，任务调度（LLMTaskScheduler）管理大小模型池的并发、熔断和重试。

第四层是持久层。关系数据（会话、消息、长期记忆元数据、用户设置）使用 SQLite 存储，通过 SQLModel ORM 访问。向量数据（Embedding 及相似度检索）使用 ChromaDB PersistentClient 管理，集合名 `longterm_memories`。本地模型文件（BGE Embedding、BGE ReRanker）缓存在 `runtime/models/` 下。

---

## ReAct 循环图结构

Agent 的每一次推理都在 LangGraph 编译的状态图中完成。图结构如下：

`safety_input` 是入口节点。如果安全审核服务不可用，入口改为 `planner`。审核通过后进入 `planner`，被拦截则直接结束并返回阻断回复。

`planner` 是策略顾问节点。它用小模型分析用户问题和当前探索进度，产出包含 `covered`（已覆盖主题）、`suggested`（建议方向）、`sufficient`（是否充足）、`hint`（策略提示）的 JSON 计划。这个计划会作为 AgentState 的一部分跨节点流转，并注入到后续 agent 节点的系统提示中。

`agent` 是模型决策节点。它调用主模型（DeepSeek-v4-flash 等），基于拼接好的完整上下文（系统提示 + 检索材料 + 历史消息 + planner 建议 + 用户自定义提示词）决定下一步。如果有 tool_calls 则进入 `action`，如果直接回复则进入 `safety_output`（或直接结束）。

`action` 是工具调用节点。它接收 agent 产生的 tool_calls，通过 ToolExecutor 分发执行。内置工具通过 ToolRegistry 管理，MCP 外部工具在启动时自动发现并注册为同形态的 StructuredTool。执行过程中通过线程本地回调把 trace 实时推送到主循环。

`observation` 是反思节点。它会审视最近一次工具调用的结果，判断信息是否充足。决策标记 `[continue]` 表示继续工具循环，`[answer]` 表示可以生成最终回复。当 LLM 决定继续时，observation 额外检查当前上下文 token 是否超过 `summary_trigger_tokens` 阈值。溢出则路由到 `compress` 先做压缩再回到 `planner`。

`compress` 是上下文压缩节点。它只在 observation 判定溢出时触发。压缩逻辑使用小模型从完整对话历史中提取"重要事实摘要"，将该摘要写入长期记忆表（`important_fact_summary` 类型），然后用 `RemoveMessage` 清空历史消息，重建为"重要事实摘要 SystemMessage + 最近 N 条消息"的紧凑上下文，路由回 `planner`。

`safety_output` 是出口审核节点。对 Agent 的最终回复执行输出安全审核，命中拦截类敏感词时替换为标准安全回复，命中清洗类敏感词时执行脱敏替换。

图的状态载体是 `AgentState`，这是一个 TypedDict，包含 `messages`（Annotated list with add_messages reducer）、`user_id`、`session_id`、`trace`（通过 add reducer 累加）、`plan`（探索状态）和 `observation_decision` 字段。

---

## 记忆系统

MetaWeave 的记忆系统是分层的，不同层次的记忆有不同的生命周期和检索方式。

### 短期记忆（会话上下文）

同一 session 内的消息按时间正序组成短期上下文窗口。ContextBuilder 从 SQLite 加载最近 N 条消息，排除 system 角色，按 LangChain BaseMessage 格式还原后注入 HumanMessage。窗口大小由 `max_context_messages` 控制。

### 重要事实摘要

当上下文 token 超过 `summary_trigger_tokens` 阈值时，CompressNode 触发上下文压缩。压缩使用小模型从完整对话历史中提取关键事实和约束，生成不超过几百字的摘要。该摘要以 SystemMessage 形式置于重置后的上下文顶部，优先于所有其他材料。这一机制在压缩对话和保留核心信息之间取得平衡：历史被丢弃，事实保留。

### 长期记忆

每次 Agent 完成一轮回答后，SummaryNode 会异步触发后台摘要任务。SessionSummaryService 读取当前 session 中尚未标记 `is_summarized` 的消息，用小模型生成自然语言摘要，存入 `session_summary` 类型的长期记忆。

MemoryResolver 紧接着从该摘要中提取结构化事实单元（`session_fact`）。程序规则先按已知 schema 提取（如项目代号、负责模块），未知字段交给 LLM 补充。提取的事实按类别处理：`single_value` 类事实（如项目当前代号）的新值会覆盖旧值（旧记录标记 `superseded`），`multi_value` 类事实的新值会追加去重，`temporal` 类事实按 `valid_until` 到期失效。这一机制的核心洞察是信息会变质。向量相似度无法区分"仍然是当前项目代号"和"已经是历史项目代号"，因此必须由单独的裁决层显式维护事实的 active/superseded/expired 状态。

### 用户自定义记忆

用户可通过 API 手动注入长期记忆。这些记忆以 `user_custom` 类型入库，参与向量检索召回，不受时效性裁决的影响。

### 知识库

`resources/knowledge/` 下的 Markdown 和 TXT 文件在启动时自动进入知识灌库流水线。流水线第一段是 `frontmatter_bootstrap`：扫描原始文件，解析标题、段落、列表、代码块等语义结构，提取 frontmatter 元数据，输出结构化 JSON 到 `runtime/frontmatter/`。流水线第二段是 `knowledge_ingestion`：读取结构化 JSON、按章节切块（chunk）、生成 Embedding、写入 ChromaDB。

文件级哈希锁是灌库的去重保障。相同内容且未变更的文件会被跳过，避免每次重启都重复切块入库。

---

## RAG 检索管道

每次用户提问，ContextBuilder 在构建上下文时执行如下检索管道：

第一步是向量召回。查询文本经过本地 BGE Embedding 模型向量化后，在 ChromaDB 中按余弦相似度检索候选，使用 user_id、tag、memory_type 做元数据过滤。过期记忆（`valid_until < now`）和 `superseded`/`expired` 状态的事实记忆在召回阶段即被滤除。

第二步是关键词召回。HybridRetrievalService 从查询中抽取 ASCII token 和 CJK 片段（并生成 N-gram 子片段），过滤停用词后，用最强的 8 个关键词在 SQLite 中执行 ILIKE 预筛，再对候选做 Python 评分（关键词覆盖率、词频加权、短语奖励）。

第三步是合并去重。两路候选按 memory_id 合并。双通道命中的候选获得 0.05 的 bonus，其 merged_score 计算公式为 `0.6 × max(v, k) + 0.4 × avg(v, k) + 0.05`。单一通道命中的候选直接取向量分或关键词分。

第四步是 ReRank 精排。所有候选送给本地 BGE ReRanker 模型，按 (query, content) 对计算语义相关度分数。

第五步是最终排序。每一条候选的 `final_score = 0.5 × relevance + 0.3 × freshness + 0.2 × authority`。通过 `score_threshold` 过滤后，按 `updated_at DESC` 优先，`final_score DESC` 次排序。最后取 `rerank_top_k` 条注入系统提示。

这一管道的前后快照会在系统消息 metadata 中保留，供前端观测面板展示 ReRank 前后的条目变化和评分对比。

---

## 安全系统

MetaWeave 采用三层递进式安全防线。

第一层是敏感词初检。SensitiveWordChecker 从 `resources/safety/sensitive_words.json` 加载七大类词库（政治、色情、暴力、违法、广告、提示注入、数据窃取），执行精确匹配和正则匹配。high 风险等级命中直接拦截，medium 等级转第二层进一步判断。

第二层是小模型意图审核。IntentAuditor 使用小模型对用户输入做语义级安全判断，输出 pass/block/suspect 三态裁决。审核维度覆盖恶意攻击（越狱/注入）、非法请求、信息窃取、骚扰滥用和正常请求。

第三层是输出审核。OutputAuditor 对 Agent 最终回复执行敏感词扫描。命中拦截类（政治/色情/暴力/违法）直接替换为标准安全回复，命中清洗类（广告/提示注入/数据窃取）执行 `***` 脱敏。

拦截回复是差异化生成的。政治敏感类拦截通过小模型生成立场正确的反驳性回复，一般拦截类通过小模型生成脱敏的礼貌拒绝。小模型不可用时回退到静态后备文案。

---

## 调度与模型路由

LLMTaskScheduler 是统一的任务调度层。所有 LLM 调用必须通过调度器提交，不能直接在节点中实例化 ChatOpenAI 并发起调用。

调度器内部维护三个任务队列（`foreground_agent`、`background_summary`、`background_fact_resolution`）和两个模型池（`large`、`small`）。主推理节点（agent、observation）路由到 large 池，使用主模型配置。策略分析（planner）、上下文压缩（compress）、摘要生成（summary）、事实抽取（MemoryResolver）、安全审核（intent_auditor）路由到 small 池。

如果配置了独立的 `AGENT_SMALL_MODEL_NAME`、`AGENT_SMALL_MODEL_API_KEY` 和 `AGENT_SMALL_MODEL_BASE_URL`，small 池任务将调用独立的小模型实例。未配置时回退到主模型配置，但仍占用 small 池的并发配额。每个模型池受独立的 Semaphore 控制上限。

调度器支持两种执行后端。本地模式使用内存队列和 ThreadPoolExecutor，每个队列有独立的工作线程。Redis 模式（配置 `AGENT_TASK_SCHEDULE_REDIS_URL` 后启用）将请求序列化写入 Redis Stream，由跨进程 worker 消费执行，支持分布式部署和故障恢复。熔断器（CircuitBreaker）按任务类型统计连续失败次数，超过阈值时拒绝新请求并在冷却期后探测恢复。

ChatOpenAI 实例按 `(model_tier, tool_names, temperature, timeout)` 四元组缓存，避免重复构造导致的内存和连接浪费。

---

## 服务间通信

MetaWeave 同时通过 REST 和 gRPC 对外暴露能力，二者底层共享同一个 AgentCore 实例。

REST 使用 FastAPI，SSE 流式对话通过 `GET /agent/stream` 和 `GET /agent/stream-run` 端点提供。非流式调用通过 `POST /agent/run` 和 `POST /agent/run-once` 提供。Session CRUD、消息历史、观测 trace 事件、用户设置各自由独立的路由模块管理。

gRPC 使用 protobuf 定义在 `protos/agent_service.proto` 中。Servicer 实现了一个薄转发层：接收 protobuf 请求，调用 AgentCore 或对应 Service 的方法，将返回值序列化为 protobuf 响应。流式 RPC 与 REST SSE 共用同一个 `_stream_events` 核心方法。

流式推送的核心是一个线程间队列。LangGraph 图在一个 daemon 线程中执行，通过 token callback、trace callback、planner callback、observation callback 和 node event 五种回调将事件 push 到 `queue.Queue`。主线程从队列中消费并 yield SSE 事件或 gRPC ChunkMessage。这一设计解决了 LangGraph 同步执行循环和异步 I/O 推送之间的阻抗不匹配。

---

## 前端架构

前端基于 Vue 3 + Pinia + Vite 构建，整体上是一个单页应用。

状态管理按照领域拆分 store：`chat.js` 管理消息流、流式内容和思考步骤的可见性，`settings.js` 管理主题、配色和用户偏好配置。流式内容使用 50ms 批量写入策略：SSE token 到达时先写入非响应式缓冲 `_pendingContent`，然后由 `setInterval` 定时器每 50ms 将缓冲 flush 到响应式的 `last.content`，将响应链触发从 30~60 次/秒降至约 20 次/秒，和 Vue 的 vdom diff 和 GC 压力解耦。

观测面板（Obs）是 MetaWeave 前端的核心差异化功能。它通过消费后端推送的 SSE 事件（node 事件、tool_trace 事件、system_prompt 事件、context_mirror 事件）重建 Agent 的执行全景。面板内包含以下信息卡片：StateGraph 图及当前活跃节点的实时高亮、节点执行轨迹与工具调用轨迹时间线、以颜色区分来源的上下文拼装视图、长期记忆和知识库召回的前后快照及 ReRank 评分对比、RAG 指标（召回率/命中率/置信度）的环形图、按模型和时刻的 token 用量面积图、单次响应延迟的瀑布图以及 Agent 超参数展示。

前端开发时 Vite dev server 运行在 8003 端口，通过代理将 API 请求转发到后端 8002。打包时 `npm run build` 输出静态文件到 `console/dist/`，PyInstaller 将其作为数据目录一并打入 exe。运行时 FastAPI 通过 `StaticFiles` 中间件托管前端资源，SPA 回退规则确保 Vue Router 的 history 模式正常工作。
