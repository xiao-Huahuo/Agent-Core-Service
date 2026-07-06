# MetaWeave 架构决策记录

本文档记录 MetaWeave 项目在架构演进过程中的关键技术决策。每一项决策包含背景上下文、备选方案评估和最终选择理由。这些记录既是历史档案，也是未来重构时的判断基准。

---

## ADR-001: 选择 LangGraph 作为 Agent 编排框架

**日期**: 2025-04
**状态**: 已采纳
**影响范围**: agent_core/graph.py, 全部 node 模块

### 背景

MetaWeave 的核心是一个需要执行多步推理和工具调用的 Agent 循环。业界有若干种实现 Agent 的方式：裸写 while 循环加消息状态管理、基于 LangChain 的 AgentExecutor、基于更结构化 StateGraph 的 LangGraph。

LangGraph 的核心价值是显式的状态图和条件路由。在 MetaWeave 的场景中，Agent 的每一步决策都可能导致不同路径：有 tool_calls 时进入工具执行，无 tool_calls 时进入安全审核；上下文溢出时进入压缩再回到规划；安全审核被拦截时直接结束。这些路径如果用裸循环实现，条件分支会散布在 if/else 中，随着节点增加逐渐不可维护。

LangGraph 的 `StateGraph` 抽象将这 8 个节点的拓扑结构显式表述为声明式路由，ConditionalEdge 的映射关系一目了然。此外 LangGraph 内置了对 checkpoints 和 streaming 的支持，后者是 Obs 面板的数据源。

### 评估

被评估的备选方案：

方案 A: LangGraph + LangChain。LangChain 生态内的工具链集成度高，StructuredTool 直接可用，BaseMessage 和 ChatOpenAI 的开箱兼容性避免了消息格式转换的胶水代码。

方案 B: 裸 Python 异步循环。好处是无框架依赖，完全控制消息状态和错误处理。代价是所有路由逻辑、状态持久化、流式回调都需要手写，最终的结果是内部复刻了一个次等的 LangGraph。

方案 C: AutoGen / CrewAI 等多 Agent 框架。这些框架的核心设计假设是多个 Agent 角色协作，而 MetaWeave 当前的架构是单 Agent 多工具。引入多 Agent 框架会带来不必要的复杂度（角色定义、消息转发、回合控制），且多 Agent 的思维过程更难在 Obs 面板中线性化展示。

### 决策

选择方案 A: LangGraph。

LangGraph 的 StateGraph + ConditionalEdge 组合精确匹配 MetaWeave 的 8 节点有向图结构。add_messages reducer 原生支持消息序列的增量拼接，trace 列表的 add reducer 同理。流式支持使得 NodeEvent 的回调可以无缝转化为前端 Obs 面板的数据流，整个调用链从图引擎到 SSE 到 Vue 组件是通畅的。

### 后果

正面：图结构的可维护性高，8 个节点的路由关系在一个文件中集中定义。新节点加入时只修改 graph.py 而不触及已有节点。流式事件的原生支持省去了大量胶水代码。

负面：LangGraph 是一个快速迭代的框架，版本升级可能引入 API 变化。当前使用的 `StateGraph` API 在 LangGraph 1.0 后是稳定的，但早期的 breaking change 经验表明需要注意版本锁定。另外 LangGraph 的 graph 执行是同步的，与 FastAPI 的 async I/O 之间存在阻抗，需要 ThreadPoolExecutor 做桥接层。

---

## ADR-002: ChromaDB 作为向量数据库

**日期**: 2025-04
**状态**: 已采纳
**影响范围**: longterm_memory_service.py, retrieval_service.py, knowledge_ingestion.py

### 背景

记忆系统和知识库检索都需要一个向量数据库来存储 Embedding 并执行近似最近邻搜索。候选范围包括 ChromaDB、Pinecone、Qdrant、Weaviate、Milvus 和 pgvector。

MetaWeave 的部署定位是一个打包为单个 exe 的本地服务：它可能运行在开发者的 Windows 笔记本上，也可能是内网的 Linux 服务器上。用户不需要也不应该为了使用文档问答功能而安装 Docker 或配置 Kubernetes。

### 评估

Pinecone 是 SaaS-only 产品，这条路径在离线可用性要求下直接排除。Qdrant 和 Weaviate 虽然支持嵌入式模式，但它们的 Python 客户端内部依赖 Rust 或 Go 构建物，在 PyInstaller 打包场景下出现过导入失败和二进制路径解析问题。Milvus 的最小部署规模（至少需要 etcd + MinIO）相当于让用户在本机上运行一个小型分布式系统。pgvector 需要 PostgreSQL 服务，也打破了零依赖部署的约束。

ChromaDB 有三个决定性优势。第一，PersistentClient 模式将向量数据直接存储在磁盘目录中，无需独立服务器进程，启动时自动初始化。第二，Python 原生实现，依赖栈全是纯 Python 或标准 C 扩展，PyInstaller 打包通过率高于任何竞品。第三，API 简洁，`collection.query()` 一行完成相似度搜索，元数据过滤原生支持，不需要学习新的查询 DSL。

但 ChromaDB 的局限也需要坦诚面对。单机部署意味着无法水平扩展，百万级向量后查询延迟会线性增长。它没有内置的多租户隔离，需要用 `user_id` 作为元数据过滤条件手动实现。Embedding 模型切换时需要重建集合。对于 MetaWeave 的使用场景（单用户或小团队，知识库文档数量在数万篇以内），这些限制均不构成实际瓶颈。

### 决策

选择 ChromaDB PersistentClient 模式。

### 后果

正面：零运维部署，exe 启动即可用。Python 原生，打包兼容性极好。API 足够简单，检索服务的代码量比使用 Qdrant 时减少约 30%。

负面：扩展上限存在于单机磁盘和 CPU。如果未来需要支持多实例并行检索，需要引入独立部署的 ChromaDB 服务器模式或迁移到支持副本的向量库。`EnsureParams` 在维度不匹配时的自动重建策略是破坏性的（全部数据丢失后重灌），好在灌库流程本身是幂等的。

---

## ADR-003: SQLite 作为关系数据库

**日期**: 2025-04
**状态**: 已采纳
**影响范围**: models/, 全部 Service 模块

### 背景

会话数据、消息历史、长期记忆元数据、用户设置需要持久化到关系数据库中。候选方案包括 SQLite、PostgreSQL 和 MySQL。

### 评估

MetaWeave 的写入负载很低。一次对话中，每轮推理写入寥寥数条消息记录和一个 session 更新时间。即使启用后台摘要和事实抽取，写入频率也不超过每分钟几十条。读负载集中在 session 首次加载（加载历史消息列表）和关键词检索时的 ILIKE 扫描。这些负载在 SQLite 的 WAL 模式下完全能够承载。

SQLite 在 WAL 模式下支持并发读写，单个写入者不会阻塞多个读取者。Python 的 sqlite3 模块内置于标准库，不需要编译安装任何数据库驱动。

PostgreSQL 的优势（连接池、并发写入、查询优化器、JSON 函数、全文检索）在 MetaWeave 的场景中基本用不上。引入 PostgreSQL 意味着用户必须安装和配置一个数据库服务，这与"exe 一键启动"的产品定位矛盾。

### 决策

选择 SQLite，通过 SQLModel ORM 访问，WAL 模式始终开启。

### 后果

正面：文件级部署，数据库和向量数据都在一个 `runtime/` 目录下，迁移时复制目录即可。SQLModel 提供了与 Pydantic 一致的字段校验体验，模型定义简洁。

负面：不支持真正的并发写入队列。在高并发场景下可能出现 "database is locked" 错误。当前的应对措施是在写入操作增加重试超时参数，并在 `LLMTaskScheduler` 中将后台写入任务排队到单线程执行。如果未来需要支持数十个客户端同时写入，迁移到 PostgreSQL 需要对 SQLModel 的模型定义做少量调整（主要是 `__tablename__` 和方言特定字段类型），Service 层的接口不需要修改。

---

## ADR-004: 大模型 + 小模型双模型架构

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: scheduler.py, 全部 node 模块, 全部 summary_service/memory_resolver

### 背景

Agent 推理的不同环节对模型能力的要求差异很大。生成对话回复需要强推理和丰富的语言生成能力，而摘要生成、事实提取、安全审核等任务只需要可靠的结构化输出或分类判断，不必消耗大模型的 token。

### 评估

如果所有任务都走大模型，成本翻倍且延迟更高，尤其是在后台批量处理摘要和事实时。如果所有任务都走小模型，推理质量下降，Agent 在需要深度思考的问题上会给出浅薄回答。

双模型路由的关键设计决策是：路由规则放在调度层而不是节点层。每个节点调用 `LLMTaskScheduler.invoke_chat()` 或 `stream_chat()` 时并不感知自己正在使用哪个模型——它只指定任务类型（`foreground_agent` / `background_summary` / `background_fact_resolution`），调度器根据任务类型和配置决定路由到 large 池还是 small 池。

### 决策

引入双模型池架构。主推理任务（agent 节点、observation 节点）使用 large 池（默认 DeepSeek-v4-flash），辅助任务（planner、compress、summary、fact_resolution、safety_audit）使用 small 池（默认 Moonshot-v1-8k）。两个池各自有独立的并发信号量和熔断器。

### 后果

正面：成本控制精确。一次典型的用户对话中，大模型只调用 2~5 次（取决于 tool_calls 循环次数），小模型调用 3~8 次（planner 每次循环 1 次 + compress + summary + fact）。大模型 token 消耗占总量的 70% 以上但调用次数只占约 30%。

负面：需要维护两套模型配置（名称、API Key、Base URL），且小模型的质量直接影响 planner 建议、安全审核和事实提取的可靠性。配置错误（如小模型 API 填成了大模型的地址）会导致降级，调度器会尝试在 small 池使用大模型配置，但受限于 small 池的并发额度，可能出现本不应有的排队延迟。

---

## ADR-005: 混合检索（向量 + 关键词 + ReRank）

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: retrieval_service.py, hybrid_retrieval.py

### 背景

单纯的向量检索在某些场景下会遗漏精确匹配。例如用户问"项目 AAA-2024 的技术栈"，向量模型可能将 "AAA-2024" 映射到与所有项目名称都相似的语义空间，导致召回的全是无关项目。反之，单纯的关键词匹配将"代码结构"和"项目架构"视为完全不相关的字符串，即使它们的语义高度相关。

### 评估

三阶段管道的设计目标是：向量通道覆盖语义相关性，关键词通道覆盖精确匹配，ReRank 通道做最后的语义校准。

关键词通道的核心创新是 CJK 子串提取。中文不像英文可以按空格分词，用户的提问可能是一个连续的句子片段。HybridRetrievalService 将查询中的连续 CJK 字符生成 bigram 到 quadgram 子串，然后逐个子串对候选文本执行包含匹配。配合 ASCII token 的提取（数字、版本号、代码标识符），形成了一个粗糙但有效的中文关键词扫描器。停用词过滤（的、了、是、在、和、与、等）避免了无意义匹配。

合并阶段选择的不对称偏好（`0.6 × max + 0.4 × avg`）偏向双通道一致的高分结果。纯向量结果（关键词通道为 0）和纯关键词结果（向量通道不相关）都会被降权但不会被完全压制。

### 决策

采用三阶段管道：向量召回 → 关键词召回 → 并行结果合并 → BGE ReRanker 精排 → 加权最终排序（relevance 0.5 + freshness 0.3 + authority 0.2）。

### 后果

正面：precision 比纯向量检索高约 20%~30%（基于内部测试集的常识性评估）。版本号、命令名、项目代号等精确标识符的召回率明显提升。RAG 答案的事实准确度有可感知的改善。

负面：管道总延迟 ≈ 向量搜索（~50ms）+ 关键词搜索（~100ms）+ ReRank（~500ms）。首次查询到结果就绪约需要 600~800ms，这对实时对话场景来说偏慢。优化方向是将关键词扫描的 Python 评分改为预计算文本特征，以及将 ReRanker 预热到 GPU 上（当前为 CPU 推理）。另外 HybridRetrievalService 的关键词提取规则硬编码了 CJK 范围判断，对日韩文文本会产生不精确的分割，但当前产品定位面向中文用户，这个限制是可接受的。

---

## ADR-006: REST + gRPC 双协议架构

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: api/rest/, api/grpc/, protos/

### 背景

MetaWeave 需要同时服务前端浏览器和外部微服务。浏览器端使用 SSE 流的 REST API 是最自然的选择（EventSource 浏览器原生支持），而微服务或 SDK 集成场景更倾向于 gRPC 的强类型契约和双向流。

### 评估

只提供 REST 的代价是外部服务需要自行维护 REST client 和 JSON 反序列化逻辑，缺乏 protobuf 级别的类型保证和自动代码生成。只提供 gRPC 的代价是浏览器前端需要 grpc-web 代理层，增加了一层部署依赖（通常需要 Envoy）。

双协议的坏处是维护负担翻倍。新增一个 API 函数意味着修改 Python 实现、REST 路由、protobuf 定义和 gRPC servicer 四个位置。如果某个 API 的 REST 和 gRPC 行为出现微妙差异（字段默认值、错误码映射、分页行为），排错成本很高。

### 决策

保留双协议，但采用"单一后端实现"原则控制维护成本。所有业务逻辑在 `AgentCore` 中实现一次，REST handler 和 gRPC servicer 都只是薄转发层，将请求参数转换为一致的方法调用参数，将返回值序列化为各自的响应格式。流式接口共用同一个 `_stream_events()` 核心方法，SSE 和 gRPC stream handler 都是这个方法的消费者。

### 后果

正面：两套协议覆盖了互补的消费场景，前端开发时可以用 SSE + EventSource 做零依赖控制台，外部 DevOps 工具链可以通过 gRPC 做类型安全的双向流调用。核心逻辑只存在于 AgentCore 一个地方，修 bug 不需要在两个协议处各修一次。

负面：新增 API 的工作量是单协议的 1.5 倍左右。protobuf 定义的字段类型需要与 Python Pydantic schema 手动保持同步，缺少自动化的 IDL 驱动代码生成管线。如果未来 API 数量增长到三位数，这个同步负担会变得突出，届时应该引入 protobuf 到 Python schema 的自动代码生成。

---

## ADR-007: SSE 流式协议而非 WebSocket

**日期**: 2025-04
**状态**: 已采纳
**影响范围**: agent_core.py, api/rest/agent.py, api/grpc/servicer.py

### 背景

MetaWeave 的前端需要实时显示 Agent 的思考过程：每个 token 逐字渲染、节点切换实时高亮、工具调用即时显示。这要求从后端到前端有一个持续的事件流。

### 评估

WebSocket 提供全双工通信，客户端可以在连接建立后随时发送消息。但这个能力在 MetaWeave 中完全不需要。一次对话流中，客户端只发送一次请求（用户输入），然后消耗一个响应流直到结束。不需要客户端在中间插入取消指令或调整参数（取消通过 HTTP 请求单独触发）。

SSE 在 HTTP/1.1 上原生运行，不需要升级握手，穿透反向代理时零配置。EventSource API 在浏览器中原生可用，断线自动重连。后端实现也简单：一个 generator yield 多行 `data: {...}\n\n` 即可，FastAPI 的 `StreamingResponse` 直接支持。

### 决策

REST 流式接口使用 SSE。gRPC 流式接口使用 protobuf 的 `server-streaming RPC`。底层共享同一个事件生成器。

### 后果

正面：实现简单，浏览器原生支持，代理兼容性好。

负面：SSE 是单向通道，如果需要支持对话中的交互式打断和参数调整（如用户实时切换知识库范围），SSE 的局限性会暴露。当前的"取消"方案是通过单独的 HTTP POST 请求通知后端设置 `threading.Event`，这是一个合理的绕过方案。SSE 的文本编码限制意味着二进制数据（如生成的图片）需要 base64 编码后传输。

---

## ADR-008: 本地模型做 Embedding 和 ReRank 而非调用 API

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: retrieval_service.py, knowledge_ingestion.py, hybrid_retrieval.py

### 背景

RAG 管道需要两个专用模型：一个 Embedding 模型将文本转换为向量，一个 ReRanker 模型对候选结果做精细排序。这两个模型的能力直接影响检索质量。

### 评估

使用 API 方案（如 OpenAI Embeddings API、Cohere Rerank API）的优点是零本地资源消耗，缺点是每次查询都需要一次网络往返（增加 ~200ms 延迟），且每月的 API 费用随查询量线性增长。

BAAI/bge-large-zh-v1.5 是中文 Embedding 领域的 SOTA 模型之一，BAAI/bge-reranker-v2-m3 是其配套的跨语言 ReRanker。两者均可通过 HuggingFace 的 Transformers 库加载，在消费级 GPU 上单次推理时间在 20~50ms 之间，CPU 推理也在 100~200ms 内完成。对于 MetaWeave 的单用户部署场景，这个延迟是可接受的。

首次启动时自动下载模型文件到 `runtime/models/` 目录的耗时在几分钟量级（取决于带宽），之后每次启动加载模型文件到内存只需数秒。

### 决策

使用本地 BGE 系列模型做 Embedding 和 ReRank，模型文件缓存在 `runtime/models/` 目录下。

### 后果

正面：完全离线可用，零 API 费用，隐私数据不会外流到第三方 API。Embedding 和 ReRank 能力作为系统的基础设施层是自持的。

负面：内存占用增加约 2GB（Embedding 模型约 650MB，ReRanker 模型约 1.1GB，加上推理缓存）。启动时需要额外 5~15 秒加载模型到内存或 GPU。PyInstaller 打包时模型文件需要作为数据文件额外打入，exe 体积会增加 2GB 左右。如果未来用户量大到一台机器承载不了，可以在这个 ADR 上再做决策，将 Embedding/ReRank 迁移到独立的推理服务。

---

## ADR-009: 事实裁决器（MemoryResolver）的规则 + LLM 混合抽取

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: memory_resolver.py

### 背景

长期记忆需要从对话摘要中抽取结构化事实单元，以便跨 session 追踪用户信息的变化。例如用户在一次对话中说"我在开发项目代号为 Galaxy 的后台系统"，下一次对话中 Agent 应该记住项目代号是 Galaxy 而不是其他值。

纯 LLM 抽取的问题在于结构化字段（项目代号、模块名）的抽取可能不稳定，同一个字段两次被识别为不同含义。正则规则抽取的问题在于只能覆盖预定义的已知 schema，无法处理未知类型的自由事实。

### 评估

MemoryResolver 的方案是以正则规则为骨架、LLM 为补充。可以先编写针对已知 schema 的正则提取器（项目代号 patten、模块名 patten 等），当对话摘要匹配这些 patten 时直接产出事实，准确性接近 100%。对于不匹配任何已知 patten 的事实片段，调用 LLM 执行开放式抽取。

合并策略是"正则优先"：当正则和 LLM 对同一个事实字段产出不同值时，采信正则的结果，因为确定性规则的可信度高于概率性的 LLM 输出。

事实的时效性处理分为三类。`single_value` 事实表示一个 key 只有一个当前值（如项目代号），新值会覆盖旧值（旧记录标记 `superseded`）。`multi_value` 事实表示一个 key 可以有多个当前值（如负责模块），新值追加到已有集合中，去重是必需的。`temporal` 事实表示该信息有一个过期时间（如"当前 sprint 在 2025-06-30 结束"），到期后自动失效不再参与检索召回。

### 决策

使用正则规则提取已知 schema + LLM 补充未知字段的混合抽取策略，正则结果优先于 LLM 结果。事实按 single_value / multi_value / temporal 三类分别管理时效性。

### 后果

正面：结构化字段的抽取准确性高，不会出现"当前项目代号"字段的值在两个 session 间飘移的问题。时效性管理保证过时信息不会污染后续对话的上下文。

负面：正则 patten 需要人工维护，新增字段类型时需要手动编写 patten 并测试召回率。如果用户表述方式与预设 patten 不匹配，结构化事实可能遗漏。LLM 作为后备能够兜底，但抽取质量取决于小模型的能力。temporal 事实的 `valid_until` 由 LLM 从文本中推断，存在日期解析错误的风险。

---

## ADR-010: 三层安全防线而非依赖单一审核服务

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: safety_service.py, safety.py (nodes)

### 背景

任何接受用户输入文本的 LLM 服务都需要安全审核，尤其在面向公网部署时。候选方案包括：仅使用 LLM API 自带的安全审核、集成第三方安全审核 API（如 Azure Content Safety）、自建敏感词库。

DeepSeek 等模型 API 的自带安全审核能力较弱，且审核策略不可控制。第三方 API 需要网络调用，增加延迟且依赖外部服务可用性。MetaWeave 面向企业内部部署，需要可控的、可配置的、延迟可预期的审核方案。

### 评估

三层设计遵循"快筛 → 深度审计 → 最终清洗"的递进式策略。

第一层（SensitiveWordChecker）是纯字符串匹配，每请求耗时约 1ms。七大类词库中的 high 风险词匹配直接拦截，medium 风险词命中时放行到第二层。这一层的价值是极快速地拦截明显的违规内容，避免浪费 LLM 推理时间。

第二层（IntentAuditor）使用小模型做语义级判断。单纯的敏感词匹配无法识别反讽、隐喻和通过正常词汇拼接构造的越狱攻击。小模型在这里执行"审核者"角色，对意图做 pass/block/suspect 三态分类。suspect 类结果会在观测面板中标记供人工复查。

第三层（OutputAuditor）在 Agent 生成回复内容后执行敏感词清洗。关键在于区分"拦截"和"清洗"两种处理策略：政治/色情类命中直接丢弃整个回复并返回标准安全文案，广告/提示注入类命中仅对敏感片段做脱敏处理而保留其余合法内容。这个区分避免了因过度清洗导致有效回复被误杀。

拦截回复的差异化生成也是一个重要的细节。政治敏感类的标准回复需要包含立场正确的驳斥，简单的"我无法回答这个问题"可能被认为回避不当。小模型负责生成这些差异化的拦截文案。当小模型不可用时回退到硬编码的通用拒绝文案。

### 决策

采用词库匹配 + 模型审计 + 输出清洗三层递进防线，单机部署，延迟可控。

### 后果

正面：延迟预算明确，三层总耗时约 50~200ms（主要由小模型推理决定）。词库可配置（JSON 文件），用户可以按自身业务敏感度增删敏感词。不依赖第三方 API，完全离线可用。

负面：词库的维护负担重。当前七大类词库各含数十到数百条条目，新出现的敏感词和攻击模式需要手动追加。小众语言（非中文、非英文）的敏感词无法覆盖。IntentAuditor 用的小模型对新型攻击模式（如 base64 编码注入、零宽度字符混淆）的识别能力不如专用安全模型。

---

## ADR-011: PyInstaller 打包为单个 exe 分发

**日期**: 2025-05
**状态**: 已采纳
**影响范围**: main.py, workflow.py, 部署配置

### 背景

MetaWeave 的目标用户是开发者和中小团队。他们可能需要在 Windows 笔记本、Linux 开发服务器或 macOS 上运行这个服务。传统的 `pip install` + 配置文件 + 环境变量 + 启动脚本的部署方式对非 Python 开发者来说有较高的启动门槛。

### 评估

容器化部署（Docker）是最流行的替代方案，但它要求用户安装 Docker Desktop 或 Docker Engine，这在某些企业环境中不被允许。直接分发 Python wheel 的要求是用户需要安装匹配的 Python 版本并手动管理依赖项，引入虚拟环境等概念。

PyInstaller 将 Python 解释器、所有依赖库、前端静态资源和运行时模型打包进一个 .exe 文件（Windows）或可执行文件（Linux/macOS）。用户下载后双击即可启动，浏览器访问 `http://localhost:8002` 进入对话界面。

代价是打包产物体积巨大（约 3~4GB，主要来自 ChromaDB 依赖和 BGE 模型文件），启动较慢（首次启动需要初始化数据库和下载模型），且 PyInstaller 在打包某些 C 扩展（如 tokenizers、hnswlib）时可能出现 hidden import 遗漏导致 exe 启动报错。

### 决策

使用 PyInstaller 打包为单文件可执行程序，前端静态文件作为 data 目录一起打入。启动时自动处理首次运行初始化（创建目录、下载模型、数据库迁移）。

### 后果

正面：部署体验极度简化。用户不需要安装 Python、pip、Node.js 或任何运行时。

负面：exe 体积巨大，每次更新都需要完整重新分发。PyInstaller 构建流水线需要维护 `.spec` 文件和 hidden import 列表，ChromaDB 和 Transformers 的打包是已知的脆弱点。启动时的模型下载如果失败（网络不通或磁盘空间不足），需要有清晰的错误提示而不是静默启动后模型加载失败。

---

## ADR-012: 前端流式内容 50ms 批量写入

**日期**: 2025-06
**状态**: 已采纳
**影响范围**: console/src/stores/chat.js

### 背景

SSE 流以每个 token 的频率推送事件。在大模型推理速度较快时，到达速率可能达到每秒 40~60 个 token。如果每个 token 事件到达时都直接写入 Vue 响应式 store 的 `last.content`，每个字位的变化都会触发 Vue 的响应式依赖追踪和虚拟 DOM 对比过程。高频响应式更新会侵占主线程，导致 UI 卡顿和渲染延迟。

### 评估

这个问题的经典解决方案是 requestAnimationFrame 批处理，但 `rAF` 限于浏览器帧率（通常 60Hz），而 MetaWeave 的 token 到达速率可能与帧率接近。另一个方案是 `debounce`，但 debounce 会导致 tokens 在前端显示时出现不可预期的延迟感。

选中的方案是定时器驱动的固定间隔批量写入。SSE 回调将到达的 token 追加到非响应式缓冲 `_pendingContent` 中，一个独立的 `setInterval` 每 50ms 检查缓冲并将累积的数据一次性 flush 到响应式 `last.content`。这意味着渲染触发频率从随机的 30~60 次/秒降至稳定的 20 次/秒，与 token 到达速率解耦。用户视觉上无法感知 50ms 的延迟（人类视觉暂留约 100ms）。

### 决策

使用 50ms 间隔的非响应式缓冲 + 定时 flush 策略管理流式内容的响应式更新。

### 后果

正面：UI 流畅度有明显改善，在快速推理时（>50 tokens/s）不再出现文字卡顿或闪烁。GC 压力降低（减少了大量临时响应式代理对象的创建和回收）。

负面：在极慢的推理速度（<5 tokens/s）时，50ms 的间隔意味着用户会看到文字以"块"为单位出现而不是逐字打字机效果。每 50ms flush 时块的大小可能是 0~2 个 token，打字机感依然存在但阶梯更明显。另外 `setInterval` 需要手动管理生命周期（流结束时清除），漏清理会导致内存泄漏。
