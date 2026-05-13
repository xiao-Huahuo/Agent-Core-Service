# Agent-Core-Service 智能体插件微服务

## 产品定位

##### 项目目标
本项目的目标是设计一个独立于主要软件后台之外的、可定制可编排的通用智能体微服务 `Agent-Core-Service`。

##### 主要服务人群
不是给终端用户直接使用的，而是为能够写代码、追求高度自定义智能体、希望自己搭建智能体能力的开发者准备。

## 项目设计

### 各部分设计

项目设计遵循分布式设计原则，形成可插拔、可定制的独立微服务。

各部分的设计如下：

1. 智能体核心 `AgentCore` 设计：采用 ReAct 思考模式，但不再硬编码节点流，而是形成可配置、可展示、可定制的节点流。
2. 节点设计：除了提供项目自带的节点，还提供用户自己编写节点的能力（继承节点父类），并提供用户节点配置持久化。
   基础节点有以下几种：
   - 输入/输出节点
   - 工具调用节点
   - 安全审核节点
   - 控制节点集，包含：
     - 启动/终止节点
     - 决策/汇合节点
     - 推理规划节点
     - 反思节点
   - 记忆节点集，包含：
     - 上下文压缩与事实持久化节点
     - 跨会话记忆检索节点
     - 知识库检索节点
     - 摘要节点
3. 工具系统设计：采用 **Function Calling** 模式，并对接 **MCP 协议** 接入用户可自定义的工具。除了系统自带的默认工具，还可以实现用户对工具的高度自定义。
4. 数据库设计：必须按照分布式设计规范来制定。关联库 PostgreSQL 只存储智能体相关的内容，向量库采用 pgvector。
5. 服务间调用：完全采用 **gRPC 协议** 函数化接口，只暴露特定的对外接口，如智能体信息流、思考轨迹、数据库调用等。
6. 配置管理：配置一个 `AgentConfig` 类，含有 `Constants`、`StorageConfig`、`ModelConfig`、`MemoryConfig` 等子配置类，配置类应提供外部配置参数的接口 `AgentConfig.load_config(...) -> AgentConfig`。
   调用配置应该从 `AgentCore` 隐式使用 `AgentConfig` 规范为 `agent = AgentCore(config=AgentConfig.load_config(...))` 的显式调用。
7. 可观测性：配置一个前端，观测 Agent 在后台的一切行动，包括节点状态、上下文构建器的 JSON、RAG 召回的条目、召回筛选过程、会话摘要等。配置完备的日志系统，所有的 Agent 行动也应该记录下来，务必保证信息传递过程完全可视化。
   - 前端轨迹面板可以参考 AI Agent Debugger 的思路，消费 LangGraph 节点事件、工具调用事件和状态更新事件来还原智能体行动过程。
8. 输出可定制性：可以根据实际业务定制所需的字段，甚至可以定制 display 模式来控制输出字段。
9. 记忆管理：优化长短记忆的算法和机制。
   - 短期记忆：即会话内上下文管理，不超过上下文长度的直接追加到上下文构建器 `ContextBuilder`，超过 `summary_trigger_tokens` 阈值时会先进入 `compress` 节点,用小模型生成“重要事实摘要”,再把工作上下文重写为 `重要事实摘要 + 最近少量消息`。
   - 会话管理：仍然采用 Session 会话管理机制。每次连续提问就从 PostgreSQL 中读取同 ID 会话并加载到上下文构建器。
   - 长期记忆：采用 RAG 检索增强生成 + pgvector 向量库作为长期记忆提取方式。
     - 跨对话记忆：Tag 为 `Memory`，每次发送 prompt 且内容有用时自动异步提取摘要，存储到用户会话向量库中。
     - 知识库 / 大文本记忆：Tag 为 `Knowledge`，需包含切片来源和时效性有关字段。本地知识库文件采用哈希锁来锁定文件已读状态。原始数据会先进行 `frontmatter_bootstrap` 处理，提取元结构 JSON，然后再进行 `knowledge_bootstrap` 处理得到可操作对象，再进行后续切片。
     - 重要事实摘要记忆：上下文压缩后生成的摘要会写入 `important_fact_summary` 长期记忆,供后续 `ContextBuilder` 优先注入。
     - 用户个性长期记忆：不经过 RAG 流程，置入工具直接提供智能体使用。
   - 提高 RAG 召回率：采用以下策略：
     - 分块策略：按照语义切块，标题、段落、表格、列表分开处理。
     - 切片策略：采用重叠切片，`512 ~ 1024` 个 token 一个 chunk，重叠部分为 `128 ~ 256` 个 token。
     - 混合检索：采用多路召回，RAG 模糊检索与关键词检索并行，各取相关度最高的 5 条（默认），然后合并去重。
     - 重排序：引入本地 ReRank 模型，进行相关度精排序。对于混合检索得到的所有条目，先做 ReRank，再叠加时效性与权威性得到最终 TopK。
10. 注意力优化：上下文拼装优先级为 `短期历史消息 -> important_fact_summary -> 当前 session 的 session_fact / session_summary -> 外部知识库片段`，避免知识库内容覆盖用户刚刚明确给出的事实。
11. 信息时效性：为了保证信息时效性，每条记忆都要含有内容有效性时间戳字段（`created_at`、`updated_at`、`valid_from`、`valid_until`），检索时采用优先新内容、旧内容降权、过期内容直接过滤的算法：
     1. 过滤层：过滤 `valid_until < now` 的过时信息。
     2. 排序层：相关性 + 时效性联合排序，公式：$$Score = 0.5 * relevance + 0.3 * freshness + 0.2 * authority$$
     3. 时效状态管理：配置 `MemoryResolver` 作为独立记忆裁决层，先把自然语言摘要解析为结构化事实单元 `session_fact`，再为事实写入 `active / superseded / expired` 状态。
     4. 事实更新策略：针对单值强排他事实执行新值覆盖旧值，针对多值弱排他事实执行新值追加，针对时序事实执行到期失效处理，不再仅依赖向量检索排序推断新旧关系。
     5. 事实类型裁决：已知 `fact_key` 走 schema 固定类别，未知 `fact_key` 由 LLM 提供候选类别，最终由程序统一裁决，避免同一事实在不同轮次被判成不同类型。
12. 多级队列与并发: 设置一个限流调度器`LLMTaskScheduler`,所有的LLM调用都要通过它.内部存在多级队列调度(按主 Agent、Summary、Fact Extraction 三个等级分配到不同队列),同时增加 `large / small` 双模型池路由,主推理走大模型池,摘要/事实抽取/上下文压缩走小模型池,并分别配备独立并发上限、超时、熔断与重试机制.
   - 大小模型分流机制：调度器先按任务语义决定 `model_tier`,再按 `model_tier` 选择实际模型配置。主回答模型负责复杂推理与最终回答,小模型负责重要事实摘要、长期记忆摘要、事实抽取、分类与轻量语义压缩,以降低主模型的延迟与负载压力。当前默认分配是:
     - `foreground_agent -> large`
     - `compress -> small`
     - `summary -> small`
     - `fact extraction -> small`
   - 物理模型隔离：如果配置 `AGENT_SMALL_MODEL_NAME / AGENT_SMALL_MODEL_API_KEY / AGENT_SMALL_MODEL_BASE_URL`,则 `small` 任务会真正调用独立小模型;未配置时才会回退到主模型配置,但仍占用 `small pool` 的并发配额。
### 项目工作原理流程图
#### 记忆机制
##### 长期记忆 / 知识库入库流程

```mermaid
flowchart TD
    A["write_long_term_memory 工具"] -->|"主模型主动写入"| H["Embedding"]
    B["跨会话记忆工具"] -->|"SummaryNode / CompressNode"| H
    C["知识库 / 原始大文本"] -->|"frontmatter"| G["结构化 JSON"]
    G -->|"bootstrap"| D["语义切块"]
    D --> E["重叠切片"]
    E --> H
    H --> F["pgvector 入库"]
    F --> I["longterm_memory_specs 表"]
```

##### RAG 召回流程

```mermaid
flowchart TD
    A[长期记忆调用工具] --> B[pgvector 检索]
    C[知识库检索工具] --> B
    B -->|N 条| H{过滤过期记忆}
    H -->|及时| D[混合检索 / 多路召回]
    D -->|10 条| E[重排序]
    E -->|3 条| F[召回]
    H -->|过时| G[去除]
```

##### 记忆时效性机制

```mermaid
flowchart TD
    A[会话消息] --> B[Summary 节点生成自然语言摘要]
    B --> C[写入 session_summary]
    C --> D[MemoryResolver 提取 session_fact]
    D --> E[补齐 created_at / updated_at / valid_from / valid_until]
    E --> F{事实类型}
    F -->|单值强排他| G[新值覆盖旧值]
    F -->|多值弱排他| H[新值追加并去重]
    F -->|时序事实| I[按时间失效处理]
    G --> J[旧事实标记 superseded]
    G --> K[新事实标记 active]
    H --> K
    I --> L[过期事实标记 expired]
    K --> M[检索优先召回 active 且未过期的 session_fact]
    J --> N[旧事实不再作为当前答案]
    L --> N
    M --> O[未命中时回退 session_summary]
```
#### 任务调度机制
##### compress 路径: 上下文压缩 / 重要事实摘要流程

```mermaid
flowchart TD
    A["run_session_prompt / action 回到 agent 前"] --> B["compress 节点检查 token 估算"]
    B -->|"未触顶"| C["直接进入 agent"]
    B -->|"超过 summary_trigger_tokens"| D["small model 生成重要事实摘要"]
    D --> E["写入 important_fact_summary 长期记忆"]
    D --> F["当前工作消息重写为: 重要事实摘要 + 最近少量消息"]
    F --> C
    E --> G["后续 ContextBuilder 优先注入 important_fact_summary"]
```

##### summary 路径: 长期记忆摘要流程

```mermaid
flowchart TD
    A["SummaryNode 异步触发 summary job"] --> B["SessionSummaryService 读取未摘要消息"]
    B --> C["small model 生成长期记忆摘要"]
    C --> D["写入 session_summary"]
    D --> E["MemoryResolver 提取并裁决 session_fact"]
    E --> F["旧事实标记 superseded / expired"]
    E --> G["新事实标记 active"]
    D --> H["原始消息标记 is_summarized=true"]
```


##### 模型池

```mermaid
flowchart TD
    A["AgentCore / CompressNode / SummaryService / MemoryResolver 发起任务"] --> B{"调用入口"}
    B -->|"主 Agent 决策"| C["invoke_chat(task_type=foreground_agent, model_tier=large)"]
    B -->|"compress 重要事实摘要"| D["invoke_chat(task_type=foreground_agent, model_tier=small)"]
    B -->|"summary 长期记忆摘要"| E["invoke_chat(task_type=background_summary, model_tier=small)"]
    B -->|"fact extraction"| F["invoke_chat(task_type=background_fact_resolution, model_tier=small)"]
    B -->|"SummaryNode 业务任务"| G["submit_summary_job(...)"]

    C --> H["large pool semaphore"]
    D --> I["small pool semaphore"]
    E --> I
    F --> I

    C -->|"工具调用: write_long_term_memory"| J2["Embedding + DB 直写, 不经 LLM"]

    H --> J{"是否启用 Redis"}
    I --> J
    G --> K{"是否启用 Redis"}

    J -->|"否"| L["本地 chat worker 回退"]
    J -->|"是"| M["Redis Stream: chat request"]
    K -->|"否"| N["本地 summary worker 回退"]
    K -->|"是"| O["Redis Stream: summary job"]

    M --> P["consumer group chat worker 消费"]
    O --> Q["summary job worker 消费"]
    Q --> R["SessionSummaryService.summarize_session(user_id, session_id)"]
    R --> E
    R --> F

    P --> S["global semaphore + timeout + retry + circuit breaker"]
    L --> S
    N --> R
    S --> T["按 model_tier 选择 large/small 实际模型"]
    T --> U["ChatOpenAI.invoke(...)"]
    U --> V["结果回写 Redis result key"]

    M --> W["调用方轮询等待 chat 结果"]
    V --> W
    O --> X["调用方轮询等待 summary job 结果"]
    R --> Y["summary 完成后回写 summary 结果"]
    Y --> X
```



## 技术栈

- 版本：Python 3.12
- 微服务框架：FastAPI + gRPC
- 观测面板：Vue 3 + Pinia
- 反向代理：Vite（开发阶段） / Nginx（生产阶段）
- 智能体编排：LangGraph（可配置工作流 / 节点流转）
- 模型接入：LangChain + OpenAI Compatible API
- 工具协议：MCP
- 关联数据库：PostgreSQL
- 向量数据库：pgvector
- 长期记忆方案：RAG（向量检索 + 关键词检索 + ReRank）
- 配置管理：Pydantic / dataclass 风格 AgentConfig
- 异步任务：asyncio
- 日志与监控：logging / structlog + Prometheus + Grafana
- 容器化部署：Docker + Docker Compose
- 测试与质量：Pytest + Ruff + mypy
