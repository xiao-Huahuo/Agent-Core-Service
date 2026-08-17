# MetaWeave 元织 - 个人多模态知识库 Agent

## 产品定位

### 项目目标

MetaWeave（元织）是一个建立在个人文件系统上的多模态知识库与 Agent 工作台。它强调可观测和可溯源：用户不仅能让 Agent 使用知识，还能看到知识来自哪里、如何被处理，以及任务执行到了哪一步。

### 现实痛点

个人资料往往散落在 Markdown、PDF、Office 文档、图片、表格和代码中。传统知识库擅长保存文件，却很难让 Agent 统一检索和操作这些不同结构的知识资产。

MetaWeave 将文件、文献、表格、组件和密码条目放在同一个桌面工作台中，并根据内容类型提供合适的浏览、编辑、检索与 Agent 操作方式。

### 项目简介

MetaWeave 集成多轮对话、工具调用、长期记忆、知识库召回、任务队列和多模式推理，可以完成问答、检索、文档理解与自动化任务。前端同时展示模型用量、节点耗时、召回质量和执行轨迹，便于用户理解 Agent 的行为，而不是只看到最终答案。
![主页](docs/assets/主页.png)

### 主要服务人群

- 希望在个人文件系统上建立 Agent 中枢的知识管理用户。
- 需要统一管理文档、文献、表格和代码等异构资料的用户。
- 希望自行配置模型、工具和工作流的开发者。

### 设计原则

Agent 框架不能消除模型幻觉。MetaWeave 因此优先提供检索、引用、执行轨迹和调试观测，让用户能够核对依据并发现问题。


## 技术栈

* 版本：Python 3.12
* 微服务框架：FastAPI
* 通信与工具协议: gRPC + REST/HTTP + MCP
* 观测面板：Vue 3 + Pinia + TypeScript/JavaScript
* 知识图谱：D3.js + Canvas
* 文档编辑器：CodeEditor + MarkdownPreview + 多模态原件预览器，按文件类型切换编辑、预览、表格或 Markdown 中间层
* 反向代理：Vite
* 智能体编排：LangGraph + LangChain
* 模型接入：支持用户配置的 OpenAI 兼容大小模型接口
* 关联数据库：SQLite
* 向量数据库：ChromaDB
* 长期记忆方案：RAG（向量检索 + 关键词检索 + ReRank）
* 配置管理：Pydantic / dataclass 风格 AgentConfig
* 异步任务：asyncio
* 知识库文件监听: watchdog
* 联网搜索引擎: DuckDuckGo + ddgs
* OCR引擎: PaddleOCR
* 日志与监控：logging / structlog + Prometheus + Grafana
* 测试与质量：Pytest + Ruff + mypy

## 核心文档
### 启动与开发
- 启动,构建与部署: [DEVELOPMENT.md](docs/DEVELOPMENT.md)
- 开发规范: [开发规范.md](开发规范.md)
### 功能
- 详细功能介绍: [FEATURES.md](docs/FEATURES.md)
### 系统设计
- 总体架构设计: [ARCHITECTURE.md](docs/ARCHITECTURE.md)
##### 后端
- 业务领域设计: [SERVICES.md](docs/SERVICES.md)
- 部分业务工作流流程图: [WORKFLOW.md](docs/WORKFLOW.md)
- AGENT设计: [AGENT_DESIGN.md](docs/AGENT_DESIGN.md)
- AGENT工具明细: [TOOLS.md](docs/TOOLS.md)
##### 前端
- 前端UI/UX设计规范: [DESIGN.md](docs/DESIGN.md)
### 变更
- TODO: [TODO.md](TODO.md)
- 变更历史: [CHANGE_HISTORY.md](docs/CHANGE_HISTORY.md)
### 接口与扩展
- OPENAPI文档: [metaweave.openapi.json)](docs/api/metaweave.openapi.json)
- MCP 接入: [MCP.md](docs/MCP.md)
- gRPC: [agent_service.proto](protos/agent_service.proto)

