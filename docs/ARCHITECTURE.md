# MetaWeave(元织) 项目总体架构设计

### 技术栈

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

### 项目结构

项目由 Python 后端服务、Electron/Vue 前端工作台、可编辑资源和运行时数据四部分组成。`dist/`、`build/`、`editor/dist/`、`editor/release/` 和 `runtime/` 属于构建产物或运行时数据，不作为源码结构维护。

```text
MetaWeave/
├── main.py                         # 后端入口
├── AgentService.spec               # PyInstaller 后端构建配置
├── 启动.bat                        # Windows 开发环境一键启动
├── protos/
│   └── agent_service.proto         # gRPC 协议登记
├── agent_service/
│   ├── core/
│   │   └── agent_config.py         # 服务配置与环境变量入口
│   ├── api/
│   │   ├── rest/                   # FastAPI REST 路由
│   │   └── grpc/
│   │       └── servicer.py         # gRPC 服务登记
│   ├── agent_core/
│   │   └── nodes/                  # Agent 状态图、节点与执行循环
│   ├── tools/
│   │   └── mcp/                    # 内置工具和 MCP 接入
│   ├── services/
│   │   ├── memory/
│   │   │   └── rag/                # 上下文、长期记忆与知识检索
│   │   ├── safety/                 # 输入与输出安全审核
│   │   ├── child_agent/            # 子 Agent 生命周期
│   │   ├── scheduler/              # 调度、并发与熔断
│   │   └── terminal/               # 终端沙箱
│   ├── models/                     # SQLModel 数据模型
│   ├── schemas/                    # API DTO 和校验模型
│   ├── scripts/                    # 初始化与维护脚本
│   └── requirements.txt            # Python 依赖
├── resources/
│   ├── mcp/
│   │   └── example.json            # MCP 配置模板
│   ├── safety/                     # 安全规则
│   ├── skills/                     # 内置 Skill
│   └── knowledge/                  # 本地开发默认知识库
├── editor/
│   ├── electron/
│   │   └── main.cjs                # 桌面主进程与内置后端生命周期
│   ├── src/
│   │   ├── main.ts                 # Vue 启动入口
│   │   ├── App.vue                 # 根组件
│   │   ├── views/                  # 页面
│   │   ├── components/             # 业务与通用组件
│   │   ├── floating/               # 悬浮窗口
│   │   ├── supercomponents/        # 复合功能组件
│   │   ├── api/                    # 前端 API 客户端
│   │   ├── router/
│   │   │   ├── index.ts            # 页面路由登记
│   │   │   └── api_routes.ts       # API 路由登记
│   │   ├── stores/
│   │   │   ├── settings.ts         # 用户配置状态
│   │   │   └── workspace.ts        # 工作区状态
│   │   ├── composable/             # 组合式逻辑
│   │   ├── types/                  # 领域类型
│   │   ├── utils/                  # 通用工具
│   │   ├── assets/                 # 图标、字体、图片与样式
│   │   └── __tests__/              # 前端测试
│   ├── scripts/                    # 构建与安装包脚本
│   ├── vite.config.ts              # Vite 与代理配置
│   └── package.json                # 前端依赖和命令
├── runtime/                        # 数据库、缓存、日志和会话上传
├── tests/                          # 后端测试
├── docs/                           # 设计、接口与开发文档
├── agent_graph*.mmd                # Agent 状态图
├── CHANGE_HISTORY.md               # 修改历史
└── README.md                       # 项目说明
```

运行时路径和发布路径需要区分：开发模式默认读取项目根目录的 `resources/`；Electron 安装包首次启动时把默认模板复制到用户数据目录，并通过 `AGENT_PROJECT_ROOT` 和 `AGENT_BASE_DATA_DIR` 指向该目录。`resources/knowledge/`、`runtime/` 和模型文件属于用户数据，不随 `AgentService.exe` 打包。
